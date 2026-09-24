"""Console API for editing the pipeline."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qanat.api import AppState, create_app
from qanat.project import load
from qanat.runner import run_all
from qanat.scaffold import write_project
from qanat.store import Store


@pytest.fixture
def client(tmp_path: Path):
    write_project(tmp_path, "demo")
    project, root = load(tmp_path)
    store = Store(project.store_url(root))
    state = AppState(store=store, project=project, root=root, sched=None)
    return TestClient(create_app(state), base_url="http://127.0.0.1:8420"), state


def test_get_project(client):
    c, _ = client
    r = c.get("/api/project")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["config"]["project"] == "demo"


def test_add_stage(client):
    c, state = client
    r = c.post("/api/stages", json={
        "id": "enriched",
        "kind": "features",
        "description": "extra layer",
        "before": "weights",
    })
    assert r.status_code == 200
    state.reload()
    ids = [s.id for s in state.project.stages]
    assert "enriched" in ids
    assert ids.index("enriched") < ids.index("weights")


def test_add_source(client):
    c, state = client
    r = c.post("/api/sources", json={
        "id": "extra",
        "to": ["raw.extra_bars"],
        "connector": "synthetic",
        "schedule": "*/10 * * * *",
        "mode": "replace",
        "options": {"series": "bars", "from_universe": "./universes/demo8.csv"},
    })
    assert r.status_code == 200
    state.reload()
    assert any(s.id == "extra" for s in state.project.sources)


def test_add_step_creates_script(client, tmp_path: Path):
    c, state = client
    r = c.post("/api/steps", json={
        "id": "extra_step",
        "from": ["normalized.prices"],
        "to": ["features.extra"],
        "script": "steps/extra.sql",
        "schedule": "*/10 * * * *",
    })
    assert r.status_code == 200
    assert (tmp_path / "steps" / "extra.sql").is_file()
    state.reload()
    assert any(s.id == "extra_step" for s in state.project.steps)


def test_retention_api(client):
    c, state = client
    r = c.put("/api/retention", json={"retention": {"raw.daily_prices": "7d"}})
    assert r.status_code == 200
    state.reload()
    assert state.project.retention["raw.daily_prices"] == "7d"


def test_prune_orphan(client, tmp_path: Path):
    c, state = client
    run_all(state.store, state.project, state.root)
    yaml = (tmp_path / "qanat.yaml").read_text()
    yaml = yaml.replace("  - id: tone\n", "")
    yaml = yaml.replace("features.tone", "features.momentum")
    yaml = yaml.replace("from: [features.momentum, features.risk, features.tone]",
                        "from: [features.momentum, features.risk]")
    (tmp_path / "qanat.yaml").write_text(yaml)
    state.reload()
    r = c.post("/api/prune")
    assert r.status_code == 200
    assert any(d["ref"] == "features.tone" for d in r.json()["dropped"])


def test_ask_lists_every_cli_with_status(client):
    """The picker needs the whole shelf, not just whichever was found first.

    A console that only ever names the winner cannot offer a choice, and a name
    it offers without saying whether it works is worse than no choice at all.
    """
    c, _ = client
    r = c.get("/api/ask")
    assert r.status_code == 200
    body = r.json()
    assert body.get("clis")
    assert "claude" in {row["bin"] for row in body["clis"]}
    for row in body["clis"]:
        assert set(row) >= {"bin", "label", "support", "found", "active", "note"}
        assert row["support"] in {"full", "partial"}
        #  A `partial` entry has to say what is wrong with it. An entry that is
        #  offered without that is the thing this list exists to prevent.
        if row["support"] != "full":
            assert row["note"]
    # at most one can be the one that would actually run
    assert sum(1 for row in body["clis"] if row["active"]) <= 1


def test_agent_choice_lands_in_the_file(client):
    c, state = client
    r = c.put("/api/agent", json={"cli": "claude"})
    assert r.status_code == 200
    state.reload()
    assert state.project.agent is not None
    assert state.project.agent.cli == "claude"
    # and it is readable back through the door the console uses
    assert c.get("/api/ask").json()["chosen"] == "claude"
    # clearing it goes back to first-found
    assert c.put("/api/agent", json={"cli": ""}).status_code == 200
    state.reload()
    assert state.project.agent.cli == ""


def test_agent_choice_refuses_a_cli_we_cannot_drive(client):
    """Better to refuse at the door than to write it and fail at the ask box."""
    c, state = client
    r = c.put("/api/agent", json={"cli": "not-an-agent"})
    assert r.status_code >= 400
    state.reload()
    assert state.project.agent is None or state.project.agent.cli == ""


def test_agent_timeout_is_configurable_and_survives_a_bad_value(client):
    from qanat.api import _agent_timeout
    from qanat.models import Agent

    _, state = client
    assert _agent_timeout(state) == 180.0          # the default, with no agent block
    state.project.agent = Agent(cli="", timeout="30m")
    assert _agent_timeout(state) == 1800.0
    state.project.agent = Agent(cli="", timeout="not a duration")
    assert _agent_timeout(state) == 180.0          # falls back rather than failing an ask


# ---------------------------------------------------------------- sessions
def _seed_session(state, sid="s-1", alpha="alpha_momentum", runs=1):
    state.store.open_session(sid, cli="Claude Code", title="add a momentum strategy")
    state.store.note_ask(sid, cost_usd=0.11, model="claude-opus-5")
    ids = []
    for i in range(runs):
        rid = state.store.start_backtest("2026-01-01", "2026-06-01", "5d", i, f"dig{i}",
                                         alpha=alpha, session_id=sid)
        state.store.end_backtest(rid, "ok", {"net": 0.1 + i / 100, "gross": 0.1, "fees": 0.0,
                                             "slippage": 0.0, "turnover": 1.0, "periods": 10})
        ids.append(rid)
    return ids


def test_a_session_shows_what_it_produced(client):
    c, state = client
    ids = _seed_session(state, runs=2)
    body = c.get("/api/sessions/s-1").json()
    assert body["title"] == "add a momentum strategy"
    assert body["asks"] == 1 and body["cost_usd"] == pytest.approx(0.11)
    assert [r["run_id"] for r in body["backtests"]] == sorted(ids, reverse=True)


def test_a_session_that_replayed_nothing_simply_has_none(client):
    """Most sessions are a question and an answer. An empty list is the truth about
    that session, not a gap in the record or an error state."""
    c, state = client
    state.store.open_session("quiet", title="what is in this project?")
    body = c.get("/api/sessions/quiet").json()
    assert body["backtests"] == []
    listed = {s["session_id"]: s for s in c.get("/api/sessions").json()["sessions"]}
    assert listed["quiet"]["runs"] == 0


def test_an_alpha_lists_the_sessions_it_came_out_of(client):
    """The same join read the other way round."""
    c, state = client
    _seed_session(state, sid="s-1", alpha="alpha_momentum", runs=2)
    _seed_session(state, sid="s-2", alpha="alpha_momentum", runs=1)
    _seed_session(state, sid="s-3", alpha="alpha_low_vol", runs=1)

    rows = c.get("/api/alphas/alpha_momentum/sessions").json()
    assert {r["session_id"] for r in rows} == {"s-1", "s-2"}
    assert {r["session_id"]: r["runs"] for r in rows} == {"s-1": 2, "s-2": 1}
    assert [r["session_id"] for r in c.get("/api/alphas/alpha_low_vol/sessions").json()] == ["s-3"]


def test_a_cli_or_scheduler_replay_belongs_to_no_session(client):
    """Tagging one would invent a conversation nobody had."""
    c, state = client
    rid = state.store.start_backtest("2026-01-01", "2026-06-01", "5d", 0, "d", alpha="a")
    state.store.end_backtest(rid, "ok", {"net": 0.0, "gross": 0.0, "fees": 0.0,
                                         "slippage": 0.0, "turnover": 0.0, "periods": 1})
    row = next(r for r in state.store.backtests() if r["run_id"] == rid)
    assert not row["session_id"]
    assert c.get("/api/sessions").json()["sessions"] == []


def test_starting_a_new_session_closes_the_open_one(client):
    c, state = client
    state._session = "s-1"
    _seed_session(state)
    r = c.post("/api/sessions/new").json()
    assert r["closed"] == "s-1"
    assert c.get("/api/sessions").json()["open"] == ""


def test_a_session_keeps_what_was_said(client):
    """Continuing a session reads the CLI's transcript; reading one reads ours.
    Without this a past session is a card -- a summary and a count -- and nobody
    can see what was actually asked."""
    c, state = client
    state.store.open_session("s-1", title="q one")
    state.store.save_ask("s-1", {
        "question": "how many alphas?", "answer": "five, plus one blend",
        "lines": [{"kind": "read", "text": "reading graph", "detail": "", "at": 0.4},
                  {"kind": "diff", "text": "new step momentum", "detail": "", "at": 6.1}],
        "model": "claude-opus-5", "cost_usd": 0.41, "elapsed": 12.7,
    })
    state.store.save_ask("s-1", {"question": "which was wired?", "answer": "momentum"})

    body = c.get("/api/sessions/s-1").json()
    asks = body["messages"]
    assert [a["question"] for a in asks] == ["how many alphas?", "which was wired?"]
    assert asks[0]["answer"] == "five, plus one blend"
    # the tool log comes back as structure, not as the string it was stored as
    assert [line["kind"] for line in asks[0]["lines"]] == ["read", "diff"]
    assert asks[0]["cost_usd"] == pytest.approx(0.41)
    assert asks[1]["lines"] == []


def test_a_session_from_before_we_kept_messages_still_opens(client):
    """Older sessions have no transcript. That is a thinner card, not an error."""
    c, state = client
    state.store.open_session("old", title="before")
    assert c.get("/api/sessions/old").json()["messages"] == []


def test_the_transcript_does_not_shadow_the_question_count(client):
    """`asks` is how many questions; the messages are a list. One key cannot be
    both, and the spread that builds this response would have made it the list."""
    c, state = client
    state.store.open_session("s-1", title="q")
    state.store.note_ask("s-1", cost_usd=0.2)
    state.store.save_ask("s-1", {"question": "q", "answer": "a"})
    body = c.get("/api/sessions/s-1").json()
    assert body["asks"] == 1
    assert len(body["messages"]) == 1


# ---------------------------------------------------------------- the ledger
def _ok_run(state, digest, alpha="alpha_momentum", net=0.1):
    rid = state.store.start_backtest("2026-01-01", "2026-06-01", "5d", 0, digest, alpha=alpha)
    state.store.end_backtest(rid, "ok", {"net": net, "gross": net, "fees": 0.0,
                                         "slippage": 0.0, "turnover": 1.0, "periods": 10})
    return rid


def test_a_trial_is_a_distinct_question_not_a_run(client):
    """Re-running the same configuration is the same question asked twice: it
    gives the same answer, so it cannot raise the bar the winner has to clear.
    Changing anything the digest covers does."""
    c, state = client
    _ok_run(state, "d1")
    _ok_run(state, "d2")
    _ok_run(state, "d2")                     # same question again
    _ok_run(state, "d3", alpha="alpha_low_vol")

    assert c.get("/api/trials?alpha=alpha_momentum").json()["count"] == 2
    assert c.get("/api/trials").json()["count"] == 3


def test_the_ledger_keeps_what_was_refuted(client):
    """The losers are the count. A ledger holding only winners cannot be divided
    by anything."""
    c, state = client
    first = _ok_run(state, "d1")
    second = _ok_run(state, "d2", net=-0.04)
    r = c.post("/api/trials", json={
        "run_id": second, "hypothesis": "60d lookback instead of 20d",
        "parent_run_id": first, "disposition": "refuted",
        "proposed_by": "claude-opus-5",
    })
    assert r.status_code == 200 and r.json()["count"] == 2

    row = next(t for t in c.get("/api/trials").json()["trials"] if t["run_id"] == second)
    assert row["hypothesis"] == "60d lookback instead of 20d"
    assert row["parent_run_id"] == first
    assert row["disposition"] == "refuted"
    # and it still counts, which is the whole point
    assert c.get("/api/trials?alpha=alpha_momentum").json()["count"] == 2


def test_the_ledger_refuses_a_disposition_it_cannot_mean(client):
    c, state = client
    rid = _ok_run(state, "d1")
    assert c.post("/api/trials", json={"run_id": rid, "disposition": "great"}).status_code == 400
    assert c.post("/api/trials", json={"run_id": 999, "hypothesis": "x"}).status_code == 404


def test_a_report_carries_the_count_it_was_chosen_from(client):
    """A figure shown without it is not yet something anybody can judge."""
    c, state = client
    _ok_run(state, "d1")
    rid = _ok_run(state, "d2")
    body = c.get(f"/api/backtests/{rid}").json()
    assert body["trials"] == 2
    assert body["trials_all"] == 2


# ------------------------------------------------------------------- the bar
def test_the_bar_is_off_until_somebody_sets_it(client):
    c, _ = client
    body = c.get("/api/bar").json()
    assert body["bar"] is None or body["bar"]["rule"] == "none"


def test_setting_the_bar_writes_it_to_the_file(client):
    c, state = client
    r = c.put("/api/bar", json={"rule": "count", "alpha": 0.05, "gate": True})
    assert r.status_code == 200
    state.reload()
    bar = state.project.backtest.bar
    assert bar.rule == "count" and bar.gate is True
    assert c.get("/api/bar").json()["bar"]["rule"] == "count"


def test_loosening_the_bar_is_recorded_as_such(client):
    """Whoever proposes strategies should not be able to quietly lower the line
    that judges them. Not forbidden -- findable."""
    c, _ = client
    c.put("/api/bar", json={"rule": "count", "alpha": 0.01, "gate": True})
    r = c.put("/api/bar", json={"rule": "count", "alpha": 0.20, "gate": True})
    assert r.json()["loosened"] is True

    history = c.get("/api/bar").json()["last_changed"]
    assert history and history[0]["level"] == "warn"
    assert "→" in history[0]["message"]

    # and tightening it back is not a warning
    assert c.put("/api/bar", json={"rule": "count", "alpha": 0.01,
                                   "gate": True}).json()["loosened"] is False


def test_turning_the_gate_off_counts_as_loosening(client):
    c, _ = client
    c.put("/api/bar", json={"rule": "floor", "t_floor": 3.0, "gate": True})
    assert c.put("/api/bar", json={"rule": "floor", "t_floor": 3.0,
                                   "gate": False}).json()["loosened"] is True


def test_the_bar_refuses_a_significance_that_is_not_one(client):
    c, _ = client
    assert c.put("/api/bar", json={"rule": "count", "alpha": 1.5}).status_code >= 400
    assert c.put("/api/bar", json={"rule": "floor", "t_floor": -1}).status_code >= 400
    assert c.put("/api/bar", json={"rule": "nonsense"}).status_code >= 400


def test_a_report_says_what_the_bar_did_to_it(client):
    import json as _json

    c, state = client
    c.put("/api/bar", json={"rule": "count", "alpha": 0.05})
    #  A real replay stores its figures inside the report blob, which is what the
    #  endpoint reads -- so the fixture has to as well, or the verdict has no
    #  totals to judge and quietly reports nothing.
    totals = {"net": 0.1, "gross": 0.1, "fees": 0.0, "slippage": 0.0, "turnover": 1.0,
              "periods": 104, "sharpe": 2.23, "periods_per_year": 52.0}
    rid = state.store.start_backtest("2026-01-01", "2026-06-01", "5d", 0, "d1",
                                     alpha="alpha_momentum")
    state.store.end_backtest(rid, "ok", totals,
                             report=_json.dumps({"totals": totals, "run_id": rid}))
    verdict = c.get(f"/api/backtests/{rid}").json()["bar"]
    assert verdict["rule"] == "count"
    assert verdict["required"] is not None and verdict["t"] is not None


# ------------------------------------------------------------------- the loop
def test_a_pass_picks_the_least_tested_alpha_first(client):
    """An attack is worth most where nobody has attacked yet."""
    from qanat.research import target_alphas

    _, state = client
    for dig in ("a1", "a2", "a3"):
        _ok_run(state, dig, alpha="alpha_momentum")
    _ok_run(state, "b1", alpha="alpha_low_vol")

    assert target_alphas(state.store, state.project, 1) == ["alpha_low_vol"]
    assert target_alphas(state.store, state.project, 2) == ["alpha_low_vol", "alpha_momentum"]


def test_a_pass_refuses_to_invent_something_to_do(client):
    """A project with nothing priced has nothing to falsify, and a pass that woke
    to find that should say so rather than making work up."""
    c, _ = client
    r = c.post("/api/research/run", json={})
    assert r.status_code == 409
    assert "priced" in r.json()["detail"]


def test_the_research_goal_is_one_of_two_safe_ones(client):
    c, state = client
    _ok_run(state, "a1")
    assert c.post("/api/research/run", json={"goal": "search"}).status_code == 400
    assert c.post("/api/research/run", json={"goal": "invent"}).status_code == 400


def test_research_says_what_it_would_pick(client):
    """A schedule whose target nobody can predict is a schedule nobody trusts."""
    c, state = client
    _ok_run(state, "a1", alpha="alpha_low_vol")
    body = c.get("/api/research").json()
    assert body["would_target"] == ["alpha_low_vol"]
    assert body["running"] is None


def test_the_falsify_brief_forbids_improving_the_thing_it_measures(client):
    """A pass that improves what it was measuring has measured nothing."""
    from qanat.research import falsify_brief

    brief = falsify_brief("alpha_momentum", 0.123, 3)
    assert "+12.30%" in brief and "3 recorded" in brief
    assert "not to improve it" in brief
    assert "Do not change the strategy" in brief
    # and it must not be allowed to over-conclude from one bad window
    assert "One losing window is a result for that" in brief
    assert "/api/trials" in brief


def test_a_research_schedule_does_nothing_without_a_door(client):
    """The pass drives an agent over HTTP, so a Scheduler nobody handed an address
    to simply never researches -- rather than failing every minute."""
    from datetime import datetime, timezone

    from qanat.models import Research
    from qanat.scheduler import Scheduler

    _, state = client
    state.project.research = Research(enabled=True, schedule="* * * * *")
    sched = Scheduler(state.store, state.project, state.root)
    assert sched.research_due(datetime.now(timezone.utc)) is False

    sched.research_through(state, "http://127.0.0.1:8420")
    # first call only arms the clock; it does not fire retroactively
    assert sched.research_due(datetime.now(timezone.utc)) is False
    assert sched._research_at is not None


def _priced_run(state, digest, alpha="alpha_momentum", sharpe=0.6, periods=104):
    """A run whose figures live where the endpoint reads them: inside the report."""
    import json as _json

    totals = {"net": 0.1, "gross": 0.1, "fees": 0.0, "slippage": 0.0, "turnover": 1.0,
              "periods": periods, "sharpe": sharpe, "periods_per_year": 52.0}
    rid = state.store.start_backtest("2026-01-01", "2026-06-01", "5d", 0, digest, alpha=alpha)
    state.store.end_backtest(rid, "ok", totals,
                             report=_json.dumps({"totals": totals, "run_id": rid}))
    return rid


def test_the_gate_blocks_calling_a_weak_run_live(client):
    """The one thing worth refusing. A replay is a measurement and measuring is
    always allowed; writing `live` against it is a claim."""
    c, state = client
    c.put("/api/bar", json={"rule": "count", "alpha": 0.05, "gate": True})
    rid = _priced_run(state, "d1", sharpe=0.6)          # t ~ 0.85, nowhere near

    blocked = c.post("/api/trials", json={"run_id": rid, "disposition": "live"})
    assert blocked.status_code == 409
    assert "does not clear the bar" in blocked.json()["detail"]

    # everything else about the same run is still recordable
    assert c.post("/api/trials", json={
        "run_id": rid, "hypothesis": "baseline", "disposition": "candidate",
    }).status_code == 200


def test_the_gate_lets_a_strong_run_through(client):
    c, state = client
    c.put("/api/bar", json={"rule": "count", "alpha": 0.05, "gate": True})
    rid = _priced_run(state, "d1", sharpe=3.0, periods=520)   # t ~ 9.5
    assert c.post("/api/trials", json={"run_id": rid, "disposition": "live"}).status_code == 200


def test_reporting_only_refuses_nothing(client):
    """Off by default, and off means off: the verdict is shown beside the number
    for a person to weigh. A tool that refuses things on day one gets its bar set
    to `none` and left there."""
    c, state = client
    c.put("/api/bar", json={"rule": "count", "alpha": 0.05, "gate": False})
    rid = _priced_run(state, "d1", sharpe=0.6)
    assert c.post("/api/trials", json={"run_id": rid, "disposition": "live"}).status_code == 200


def test_an_unjudgeable_run_is_not_waved_through(client):
    """Too few periods to say anything is not the same as clearing the bar."""
    c, state = client
    c.put("/api/bar", json={"rule": "count", "alpha": 0.05, "gate": True})
    rid = _priced_run(state, "d1", sharpe=None, periods=1)
    r = c.post("/api/trials", json={"run_id": rid, "disposition": "live"})
    assert r.status_code == 409 and "cannot be judged" in r.json()["detail"]


def test_a_cli_we_cannot_drive_is_not_on_the_shelf(client):
    """`cursor-agent` was listed and did not work: it was given only `--print`,
    whose default is plain text, while the stream parser reads JSON lines -- so
    every answer was dropped. It also refuses to start until Workspace Trust is
    granted interactively, which a headless pass cannot do.

    Adding a CLI needs an argv, an event mapping and a tool fence. Until all three
    exist, it does not belong on the list."""
    from qanat.agent import CLIS

    assert {c["bin"] for c in CLIS} == {"claude"}
    c, _ = client
    assert c.put("/api/agent", json={"cli": "cursor-agent"}).status_code >= 400


def test_a_pass_owns_the_replays_it_runs(client):
    """Without this the pass's own trials were filed against the console's session
    or against nothing, so a pass could run seven and its row would say none."""
    from qanat.api import _owning_session
    from qanat.research import Pass

    class Req:
        def __init__(self, ui):
            self.headers = {"x-qanat-ui": "1"} if ui else {}

    _, state = client
    state._session = "human-session"
    assert _owning_session(state, Req(True)) == "human-session"
    assert _owning_session(state, Req(False)) == "human-session"

    state._research = Pass("falsify", ["alpha_momentum"])
    #  A stamped request is a person clicking, even mid-pass.
    assert _owning_session(state, Req(True)) == "human-session"
    #  An unstamped one, while a pass runs, is the pass.
    assert _owning_session(state, Req(False)) == state._research.session_id

    state._research.done = True
    assert _owning_session(state, Req(False)) == "human-session"


def test_a_report_says_which_alpha_it_is(client):
    """The report blob does not carry it, so without this the page had the figures
    and no idea whose they were -- and the ledger beside them nothing to key on."""
    c, state = client
    rid = _priced_run(state, "d1", alpha="alpha_low_vol")
    assert c.get(f"/api/backtests/{rid}").json()["alpha"] == "alpha_low_vol"
