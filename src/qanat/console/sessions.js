/* Past sessions: what was worked on, and what came of it.
 *
 * The rail held exactly one conversation and dropped it when the next question
 * arrived, so asking twice was two strangers and everything the agent worked out
 * died with the answer. The engine kept none of it either -- a truncated line in
 * the event log was the whole record.
 *
 * What a row carries is deliberately two different kinds of thing. The summary is
 * prose, written by the session about itself, and is allowed to be lossy. The
 * replays beside it are rows out of the backtest table, joined by session id, and
 * are not: they are what actually ran, with the numbers it actually returned. A
 * session that replayed nothing shows nothing there, which is the truth about that
 * session rather than a gap in the record -- most sessions are a question and an
 * answer.
 *
 * Continuing one hands the id back to the CLI as `--resume`, which reads the
 * CLI's own transcript. The one shown here is ours, written as each answer lands:
 * two copies of the same conversation for two different jobs, because the CLI's
 * is what the model re-reads and cannot be rendered, and ours is what a person
 * re-reads and cannot be resumed from.
 */
(function () {
  'use strict';

  function el(id) { return document.getElementById(id); }
  function esc(t) {
    return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function pct(x, dp) {
    if (x == null || isNaN(x)) return '—';
    return (x >= 0 ? '+' : '') + (x * 100).toFixed(dp == null ? 2 : dp) + '%';
  }
  function sign(x) { return x == null ? '' : x > 0 ? ' up' : x < 0 ? ' down' : ''; }
  function day(s) { return s ? String(s).slice(0, 10) : '—'; }
  function money(x) {
    return (x == null || !x) ? '' : '$' + Number(x).toFixed(2);
  }

  async function api(path, opts) {
    var r = await fetch(path, opts || undefined);
    if (!r.ok) throw new Error((await r.text()) || r.statusText);
    return r.json();
  }

  //  The session the next question should continue. Set by picking one out of the
  //  history; cleared once it has been sent, because after that the server holds
  //  the open session and every later question continues it without being told.
  var RESUME = '';
  var OPEN = '';

  function continuing() { return RESUME; }
  function sent() { RESUME = ''; }

  //  The unattended pass, at the top of the history -- because a pass *is* a
  //  session, and the thing you want to know about it is the same thing: what it
  //  worked on and what came of it.
  //
  //  `would work on` is shown whether or not it is switched on. A schedule whose
  //  target nobody can predict is a schedule nobody trusts, and somebody deciding
  //  whether to enable this wants to see the answer before they do.
  function research(d) {
    var cfg = d.research, run = d.running, last = d.last;
    var would = (d.would_target || []).join(', ');
    if (!cfg && !run && !would) return '';
    var head = run
      ? '<span class="rspin"></span>working on ' + esc((run.targets || []).join(', '))
      : cfg && cfg.enabled
        ? esc(cfg.goal) + ' · ' + esc(cfg.schedule)
        : 'off';
    var body = run
      ? '$' + (run.spent || 0).toFixed(2) + ' of $' +
        ((cfg && cfg.budget_usd) || 0).toFixed(2) + ' spent'
      : last
        ? 'last pass: ' + esc((last.targets || []).join(', ')) + ' · $' +
          (last.spent || 0).toFixed(2)
        : would
          ? 'would work on ' + esc(would)
          : 'nothing priced yet, so nothing to attack';
    return '<div class="rbox">' +
      '<div class="rhead">research<span class="grow"></span>' +
        (run
          ? '<button type="button" class="chip" id="res-stop">stop</button>'
          : would
            ? '<button type="button" class="chip" id="res-run">run a pass</button>'
            : '') +
      '</div>' +
      '<div class="rnow">' + head + '</div>' +
      '<div class="rwhy">' + body + '</div></div>';
  }

  // ------------------------------------------------------------------- render
  function line(s) {
    //  The summary if it has one, the first question if it does not. A list of
    //  timestamps is not a history anybody reads.
    var text = s.summary || s.title || 'no summary';
    var runs = Number(s.runs || 0);
    return '<button type="button" class="sessrow" data-sid="' + esc(s.session_id) + '">' +
      '<div class="sesswhen">' + day(s.started_at) +
        (s.session_id === OPEN ? '<em class="sessnow">open</em>' : '') + '</div>' +
      '<div class="sesstext">' + esc(text) + '</div>' +
      '<div class="sessmeta">' +
        (s.asks ? s.asks + (s.asks === 1 ? ' question' : ' questions') : 'no questions') +
        //  Zero is not worth dressing up as a number. A session that replayed
        //  nothing simply did not, and saying "0 replays" invites somebody to
        //  read it as a failure.
        (runs ? ' · ' + runs + (runs === 1 ? ' replay' : ' replays') : '') +
        (money(s.cost_usd) ? ' · ' + money(s.cost_usd) : '') +
      '</div></button>';
  }

  //  The thread as it was. Rendered with the live thread's own markdown, so a
  //  past answer looks exactly as it did when it arrived rather than going
  //  through a second renderer that drifts from the first.
  //
  //  Tool lines sit between the question and the answer, which is where they
  //  happened. They are the part worth re-reading: the answer says what the agent
  //  concluded, these say what it looked at to get there.
  function thread(asks) {
    if (!asks || !asks.length) {
      return '<p class="sessnone">No messages were kept for this session. It ran ' +
             'before the console started keeping them.</p>';
    }
    var md = (window.Thread && window.Thread.md) || esc;
    return '<div class="sessthread">' + asks.map(function (a) {
      var lines = (a.lines || []).filter(function (l) { return l.kind !== 'think'; });
      return '<div class="cm me"><p>' + esc(a.question) + '</p></div>' +
        (lines.length
          ? '<ul class="sessdid">' + lines.map(function (l) {
              return '<li class="k-' + esc(l.kind) + '">' + esc(l.text) + '</li>';
            }).join('') + '</ul>'
          : '') +
        (a.error
          ? '<div class="cm agent bad"><p>' + esc(a.error) + '</p></div>'
          : '<div class="cm agent">' + md(a.answer || '') + '</div>') +
        '<div class="sessfoot">' + (a.elapsed ? a.elapsed.toFixed(1) + 's' : '') +
          (a.cost_usd ? ' · ' + money(a.cost_usd) : '') +
          (a.model ? ' · ' + esc(a.model) : '') + '</div>';
    }).join('') + '</div>';
  }

  function detail(d) {
    var bt = d.backtests || [];
    var rows = bt.map(function (b) {
      return '<tr><td class="mono">' + esc(b.alpha || '—') + '</td>' +
        '<td class="mono faint">' + day(b.from_date) + ' → ' + day(b.to_date) +
          ' · ' + esc(b.rebalance || '') + '</td>' +
        '<td class="num' + sign(b.net) + '">' + pct(b.net) + '</td></tr>';
    }).join('');
    return '<div class="sessdet">' +
      '<button type="button" class="sessback" id="sess-back">← all sessions</button>' +
      '<div class="sesshead">' + esc(d.title || 'session') + '</div>' +
      '<p class="sesssum">' + esc(d.summary || 'No summary yet. It is written when the ' +
        'session is closed, by asking the session itself what happened.') + '</p>' +
      (bt.length
        ? '<table class="sesstab"><thead><tr><th>alpha</th><th>window</th>' +
          '<th class="num">net</th></tr></thead><tbody>' + rows + '</tbody></table>'
        : '<p class="sessnone">Nothing was replayed in this session.</p>') +
      thread(d.messages) +
      '<button type="button" class="sesscont" id="sess-cont">' +
        (d.open ? 'this is the open session' : 'continue this session') + '</button>' +
      '</div>';
  }

  async function paintList() {
    var box = el('cr-hist');
    if (!box) return;
    box.hidden = false;
    box.innerHTML = '<div class="sessload">reading…</div>';
    var d, res = {};
    try { d = await api('/api/sessions'); }
    catch (e) { box.innerHTML = '<div class="sessload">' + esc(e.message) + '</div>'; return; }
    try { res = await api('/api/research'); } catch (e) { res = {}; }
    OPEN = d.open || '';
    var rows = d.sessions || [];
    box.innerHTML =
      '<div class="sesstop"><span>Sessions</span><span class="grow"></span>' +
        '<button type="button" class="chip" id="sess-new">new</button>' +
        '<button type="button" class="chip" id="sess-close">close</button></div>' +
      research(res) +
      (rows.length ? rows.map(line).join('')
        : '<div class="sessload">No sessions yet. Ask something.</div>');

    var rr = el('res-run');
    if (rr) rr.onclick = async function () {
      rr.disabled = true;
      rr.textContent = 'starting…';
      try {
        await api('/api/research/run', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ base: location.origin }),
        });
      } catch (e) { rr.textContent = e.message || 'could not start'; return; }
      paintList();
    };
    var rs = el('res-stop');
    if (rs) rs.onclick = async function () {
      try { await api('/api/research', { method: 'DELETE' }); } catch (e) { /* re-read below */ }
      paintList();
    };

    var nb = el('sess-new');
    if (nb) nb.onclick = async function () {
      //  Closing summarises in the background, so this returns at once and the
      //  row it just closed fills in its own description a little later.
      try { await api('/api/sessions/new', { method: 'POST' }); } catch (e) { /* shown on reload */ }
      RESUME = '';
      paintList();
    };
    var cb = el('sess-close');
    if (cb) cb.onclick = close;
    Array.prototype.forEach.call(box.querySelectorAll('.sessrow'), function (b) {
      b.onclick = function () { show(b.getAttribute('data-sid')); };
    });
  }

  async function show(sid) {
    var box = el('cr-hist');
    if (!box) return;
    var d;
    try { d = await api('/api/sessions/' + encodeURIComponent(sid)); }
    catch (e) { box.innerHTML = '<div class="sessload">' + esc(e.message) + '</div>'; return; }
    box.innerHTML = detail(d);
    el('sess-back').onclick = paintList;
    var cont = el('sess-cont');
    cont.disabled = !!d.open;
    cont.onclick = function () {
      RESUME = sid;
      close();
      var q = el('ask-q');
      if (q) { q.focus(); q.placeholder = 'continuing · ' + (d.summary || d.title || sid); }
    };
  }

  function close() {
    var box = el('cr-hist');
    if (box) { box.hidden = true; box.innerHTML = ''; }
  }

  function toggle() {
    var box = el('cr-hist');
    if (!box) return;
    if (box.hidden) paintList(); else close();
  }

  function wire() {
    var t = el('cr-sessions');
    if (t) t.onclick = toggle;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire);
  } else {
    wire();
  }

  window.Sessions = { toggle: toggle, close: close, continuing: continuing, sent: sent };
})();
