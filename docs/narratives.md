# The narrative page

**This is a design, not a description.** Nothing here is built yet. Each section says what
existing machinery it reuses, because most of it is reuse — the parts that need writing are the
tables, the ingestion, and one weighting step.

The narrative page is where a hypothesis comes from. It is deliberately **outside the alpha
pipeline**: no narrative table feeds a weights table, and no alpha reads a probability. News here
is not a signal. It is what a person reads before deciding what to test, and the page exists to
make that decision recorded, dated and answerable instead of remembered.

## A narrative is a question the user wrote

The user writes it. The agent never does.

```yaml
narratives:
  - id: ai_capex
    question: "Will tech companies keep increasing spend on AI and data centres?"
    resolution: "reported capex up more than 10% year over year"
    schedule: "0 6 * * *"          # optional. Without it, readings happen when asked for
```

Ingestion is a `Source` in everything but name: one connector, one table of rows with a time column,
and a `schedule:` that may be absent. That is not an analogy for convenience — it is why the
scheduler, `qanat plan`'s drift detection, the run log, the as-of views and the lookahead check all
apply to news without being written twice.

## Two modes, because most people have no machine that stays on

`schedule:` unset is the default, and the scheduler already behaves correctly for it: it collects
`[j for j in project.jobs if j.schedule]`, so a narrative without one is not skipped by accident but
by design. A person triggers a reading when they want one, and `fire(job_id, actor=...)` already
records who asked — a manual reading and a six-in-the-morning reading are distinguishable in the log
without a new field.

| | scheduled | asked for |
| --- | --- | --- |
| who fires it | the cron line | a person |
| gaps | none, while live | whatever the person leaves |

Gaps need no separate accounting, because **a dot is drawn where a reading exists and nowhere
else**. Three weeks of silence is three weeks of empty chart, so a stretch nobody watched cannot be
mistaken for a stretch that held steady. The two modes differ in how evenly the dots fall, not in
how honestly they read.

Every dot opens. Click one and it shows that reading: the agent's text, the three probabilities, and
the reason it gave for each. That is what the append-only rule is for — nothing is ever overwritten,
so every point on the chart is still answerable months later, and a person can ask *what did this
look like at the time* without taking anybody's word for it.

Dots that produced a checkpoint are marked differently from dots that did not. The chart then shows
two things at once: what was believed, and where a belief turned into a position.

What a reading does carry beyond its numbers is `n_articles`, which is about strength rather than
timing — three articles and three hundred produce dots of identical height. And `covers_from` /
`covers_to`, for the one case the dots cannot show: an ingest that could not reach all the way back
to the previous reading. A gap the API refused to answer for leaves a hole *inside* a dot, which is
the only thing here that hides.

**Prices can be backfilled; news cannot.** This is the asymmetry that decides how much manual mode
costs. A person who skips three weeks of price history loses nothing: the prices are still there
when they next run a pass, and a replay over that window prices it correctly whenever it happens.
News is not like that. A gap in ingestion is a hole in the corpus, because news APIs stop looking
back after a while and what a search still surfaces months later is the articles that turned out to
matter — which is survivorship bias, arriving through the corpus rather than the universe.

So a manual trigger ingests **the whole gap since the last reading**, not the day it was pressed,
and says so when the gap runs past what the source can still answer for. The reading that follows a
long silence is the one to distrust.

A narrative is `live` or not. Live means it ingests — on its schedule if it has one, on request if
it does not. Not live means nothing runs, rather than the page being hidden while the bill
continues.

## The three stances are fixed by the question

A narrative has exactly three, always: the question answered **yes, unchanged, no**. Positive,
neutral, negative.

Nothing generates them and nothing replaces them, because the question already defines them. For
the narrative above, positive means they keep increasing spend — there is no description to write,
and therefore none to quietly rewrite later.

This is the whole reason the page can be trusted over months. An earlier draft of this design had
the agent authoring scenario text and superseding it when the world moved, which meant a strategy
saved in March could later show reasoning nobody had read when they saved it. Fixed stances make
that unrepresentable rather than merely discouraged.

**The question is immutable too.** Editing "will they keep increasing spend" into "will spend peak
in 2027" leaves the chart running while the thing it measures changes underneath, and six months of
history becomes unreadable. An edit is a new narrative.

## A reading is appended, never replaced

One reading per narrative per as-of date: what the agent makes of the news so far, and for each
stance a probability and the reason for it.

| | |
| --- | --- |
| `narrative` | which question |
| `as_of` | when this reading was taken -- a cron firing, or the moment somebody asked |
| `text` | the agent's reading of the news up to here |
| per stance | `probability`, `reason`, `n_articles` |

Rules that hold without exception:

* **Three stances, every reading.** A reading holding two is not a partial reading, it is a broken
  one — and a strategy built from it would rest on a missing future.
* **The probabilities are whole numbers summing to 100.** Not 0.55. Three floats do not sum to
  exactly 1.0, and three probabilities summing to 1.2 are not close enough to anything; they are
  meaningless. Whole percents make the check exact: `sum == 100`. An even split is 34/33/33.
* **One reading per as-of.** `as_of` is a moment rather than a date, so two readings on one
  afternoon are two readings -- a person who asks again after fresh news has asked a second
  question, and only a re-run of the same firing is the same one asked twice.
* **Nothing is ever updated or deleted.** The chart is the history, so the history is the storage.
  A user can open any past date and see the text, the numbers and the reasons that were there.

The three probabilities and the reading are one write. A stance's number cannot move without the
other two moving, so they cannot be saved separately.

## What can be scored, and what cannot

A probability is only a claim if something can decide whether it happened. That is what
`resolution` is for, written once when the narrative is created, and best written against a number
the project can actually ingest — reported capex, shipments, rig counts. Then the page can ask the
question that matters: *on the days this narrative read 70% or higher for positive, what did capex
do over the following quarter?*

No deadline is needed. A rolling window over a stable stance does the same work, which is a second
thing fixed stances buy.

Readings that were asked for rather than scheduled are a biased sample: people check in when
something is happening. So a calibration figure carries its mode alongside its count, and figures
from the two modes are not pooled. A narrative watched daily by a cron and one visited whenever the
news looked dramatic have not answered the same question about their agent.

Two things that must not be presented as a score:

**A stance's later probability is not its answer.** Comparing January's 55% against June's 80% grades
the agent against its own later output. If it reads this narrative badly, both numbers are wrong and
may still agree. It measures self-consistency, and self-consistency is not accuracy.

**Calibration without a count is not a figure.** A stance that said 30% and happened once is not a
mistake; 30% things happen. Nothing may print an accuracy number without the number of resolved
readings beside it — the same rule as `1 of 8 trials` and `held_periods` beside `flat_periods`.

Where a narrative has no `resolution`, the page says it cannot be scored rather than showing
something that looks like a score.

## Neutral is a hiding place

An agent that is unsure can park probability in neutral and never be wrong. Over months neutral
climbs, the other two flatten, and the page reads as informative while saying nothing.

So it is watched: a narrative whose neutral stance holds above roughly 60% across many readings has
a question too vague to answer, and the page says so — an information icon on the chart, explaining
that the fix is a sharper question rather than a better agent.

Cheap to compute, and it is the one diagnostic that catches the failure the whole page is most
prone to.

## A checkpoint is the pre-registration

The user picks a reading and asks for a strategy. The agent builds the universe and the steps, and
what gets recorded is a **checkpoint**: that reading, and the run it produced.

This is the object that was missing from every earlier version of this plan — a hypothesis written
down before anything was tested, with a date on it, that cannot be edited afterwards. It does not
have to be enforced here, because everything it points at is already append-only. A checkpoint
opened in a year shows the exact text, the exact three numbers, the reasons, and the articles that
were visible on that date.

The trial ledger already carries `hypothesis` and `parent_run_id`. A checkpoint is what those two
fields were reaching for.

## A strategy built from a reading is in-sample by construction

All of it. Not partly.

The reading was written on date T from news up to T. The agent reads it and writes the universe and
the steps. The replay then prices history — which is entirely **before** T. The agent knows how that
period went, and not through the data: the as-of views handle the data. It knows through the reading,
which was written by a model that had read news about exactly those years.

This is the case `live_from` already names in its own docstring: *the data did not argue back through
the fitting, but it argued back through the person.* Here it argues back through the agent.

So a checkpoint's `as_of` **is** the frontier for every run derived from it, and the backtest is an
examination rather than a test: does it break at higher fees, does it hold anything, what does the
drawdown path look like. Useful, and not evidence.

The good part is structural. A narrative manufactures its own out-of-sample by nothing more than
time passing: checkpoint on Tuesday, and a month later there are forward periods nobody could have
looked at. `live: true` and `live_from` already produce and stamp exactly this.

Without a machine that stays on, that evidence is **discovered late rather than lost**. The prices do
not care when the pass ran: a replay over the forward window, run whenever the person next opens the
project, prices those periods exactly as a nightly `qanat serve` would have. What a person on a
laptop gives up is knowing sooner, and a stamped `live_from` that begins where they started rather
than where they eventually looked -- which is why it is stamped on the first pass that lands, not
computed fresh.

Which is the opposite of the news side, and worth holding both in mind at once: forward price
evidence survives being ignored, and forward news does not.

## The probabilities are the allocation

One alpha per stance — each stance implies its own universe and its own tilt — and the three priced
together as one book, split by the probabilities:

```python
run_backtest(alpha=["ai_capex_yes", "ai_capex_same", "ai_capex_no"],
             allocation={"ai_capex_yes": 55, "ai_capex_same": 30, "ai_capex_no": 15})
```

`_shares` normalises whatever it is given, so the percentages go in raw with no conversion. The
result is one `alphaset` with one PnL table, and the split lands in the run's `conditions` and in
its digest — so a run permanently records which probabilities produced it, and changing them is a
different question rather than the same one re-answered.

Nothing has to be built for this. It is the multi-alpha book that already exists.

## Blending averages the portfolio; it does not make it survive

Read `combine`: when two alphas hold opposite sides of a name they net off, **and the money that
frees up is spread over what is left**. So a hedge held by the negative stance against a long held
by the positive stance is cancelled, and the proceeds are reinvested into the long.

Probability-blending gives the *expected* portfolio. Surviving whichever future arrives is a
different requirement, and the blend is actively hostile to it.

Two steps, in this order:

1. **Blend by probability.** Free today.
2. **Clear the floor.** A step that reads the combined book, prices it under each stance using the
   exposure table, and adjusts until the worst stance is above a stated limit.

Two steps rather than one optimiser, deliberately. Every intermediate table stays open: the three
stance portfolios, the blend, and the adjustment that put the hedge back. One solver would return a
weight vector and no account of itself, which is the opposite of what this project is for.

The exposure table — how each asset fares under each stance — is the largest piece of work in the
plan and the place it can most easily become fiction. Weights computed from numbers the agent
asserted look identical to weights computed from sensitivities measured against history. Measure
them.

## Pinned, or floating

A live narrative's probabilities move daily, so a strategy built from one has to say which it
follows.

**Pinned** holds the checkpoint's numbers. One digest, one strategy, forward performance that means
something. The default.

**Floating** re-allocates as readings arrive. It is arguably the point of a live narrative, and it is
a different thing: every day is a different allocation, so no two days are the same strategy and
there is no "this" for a return to belong to. Its forward record measures a method, not a rule, and
the trial count would climb by one a day — making the bar unpassable for reasons that have nothing
to do with searching.

So floating is a mode a person chooses knowingly, labelled as what it measures.

It is less unruly on a narrative nobody schedules. Readings arrive when somebody asks for one, so a
floating allocation moves a handful of times a quarter rather than nightly, and the count of distinct
strategies stays small enough to mean something. The mode that makes floating dangerous is the one
that ingests on a cron.

## A new source needs its window shown, not just its price

The agent may propose sources, and a person confirms. What the confirmation shows: the connector,
the endpoint, the schedule, whether a key is needed, what it costs — and **how far back it goes**.

That last one is not a detail. A source enrolled today has no past, so a strategy depending on it can
only be replayed over what the source covers. Approving a source is approving a backtest window, and
nobody can see that unless it is on the screen. The alternative is worse: an agent that backfills by
searching now for old news collects only what today's index still surfaces, which is the articles
that turned out to matter. That is survivorship bias in the corpus, and it lands on the narrative.

Abandoned narratives leave tables nothing reads. `qanat plan` already has the word for that —
`orphan` — and needs a path to clear them.

## The words

Five, and each means one thing.

| Word | What it is |
| --- | --- |
| **narrative** | A question the user wrote, ingesting news on a schedule or when asked. Live or not. Never edited. |
| **stance** | One of the three futures a narrative has: positive, neutral, negative. Fixed by the question. Nothing authors them and nothing replaces them. |
| **reading** | Where a narrative stands at one moment: the agent's text, a probability with a reason for each stance, and the window of news it read. Appended, never replaced. The three sum to 100. |
| **checkpoint** | A reading and the run it produced. What ties a strategy back to what was believed when it was built, and the frontier for everything that run is measured on. |
| **resolution** | The rule that decides whether the positive or negative future happened. Written once, at creation. What makes a reading scoreable. |

`topic` and `deck` are gone: a narrative is the container, and one word is enough. `snapshot` is not
used here — `plan.snapshot()` already holds it for the job-spec state.
