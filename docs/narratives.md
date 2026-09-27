# The narrative page

**This is a design, not a description.** Nothing here is built yet. Each section says what
existing machinery it reuses, because most of it is reuse — what actually has to be written is the
page itself, the ingestion, and three steps: `valuation`, `exposure` and the one that picks the
weights.

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

## A stance is several industries, not a list of names

"Tech keeps spending on AI" reaches semiconductors, utilities, data-centre REITs, cooling and
networking -- and cuts the other way for the hyperscalers writing the cheques. One stance, six
industries, and one of them with the opposite sign.

That matters because each industry is valued differently. Semis on earnings or revenue, utilities on
yield, REITs on rental income. So a margin of safety computed in one is not comparable with a margin
of safety computed in another, and a single ranked list across the stance would be comparing
measuring sticks. Worse, the loosest method wins it: looser assumptions produce larger discounts, so
the industry whose fair value rests on the shakiest estimate looks like it holds all the bargains.

This is not an edge case to handle later. Every stance has it.

So a **book** -- one stance's portfolio -- is built in two levels:

| level | decided by |
| --- | --- |
| how much of the book each industry gets | the `exposure` table: semis react harder than utilities, so semis get more |
| which names inside an industry | margin of safety, ranked **within that industry only** |

A stance still has exactly one universe file. It carries a `sector` column, which `qanat init`
already ships, so the book step groups by it and never has to rank across groups:

```
symbol,name,sector,from,to
NVDA,Nvidia,SEMI,,
VST,Vistra,UTIL,,
EQIX,Equinix,REIT,,
```

One universe, one step, one script per stance -- not a step per industry.

A name may sit in two stances' universes; a utility can belong to both `keeps spending` and
`unchanged`. It is valued identically in both, because the method is keyed on its sector and never
on the stance. That is what keeps a comparison between two stances a comparison of theses rather
than of two different valuation models.

## The probabilities score a portfolio; they are not the weights

There is one vector summing to 100 and it is the reading's. It is used in exactly one place: to
weight the stances when a candidate portfolio is being scored.

```
score(w) = p_yes · R_yes(w)  +  p_same · R_same(w)  +  p_no · R_no(w)
```

where `R_s(w)` is what the portfolio returns if stance `s` arrives, read off the `exposure` table.

Splitting the money across the three books in the proportions 55/30/15 is *a candidate* -- the one
you get by ignoring the floor -- and not the answer. Calling it the allocation was the mistake an
earlier draft of this file made, and it invents a second three-number vector that reads like a second
set of probabilities. There is no second vector. There is one belief, and a portfolio that gets
scored against it.

Worked, with $1,000 and three books of two names each:

```
book_yes    NVDA 50 · VST 50        book_same   KO 60 · PG 40        book_no   GLD 70 · TLT 30
```

| candidate | split | if yes | if same | if no | score |
| --- | --- | --- | --- | --- | --- |
| the probabilities | 550 / 300 / 150 | +12.6% | +1.5% | **-12.4%** | +5.5% |
| | 500 / 250 / 250 | +11.0% | +1.3% | -10.3% | +4.9% |
| **chosen** | **480 / 270 / 250** | +10.5% | +1.4% | **-9.7%** | **+4.7%** |
| | 450 / 300 / 250 | +9.7% | +1.4% | -8.7% | +4.4% |

With a floor of -10%, the first two are infeasible however well they score. NVDA's weight in the
chosen candidate is `480/1000 × 0.50 = 0.24`, which is all the arithmetic there is: a share of the
money, times a share of the book.

The search is over portfolios, not over beliefs. The split across books is a parameterisation of the
portfolio and an internal detail of the step -- what the user is shown is the belief, the resulting
weights, and what the floor cost:

```
    you believe    55 / 30 / 15
    average         +5.5%  ->  +4.7%      the floor cost 0.8%
    worst case     -12.4%  -> -9.7%       and bought 2.7%
```

## Why the search is a grid, and why it is not `combine`

Restricting candidates to mixes of three books leaves a two-dimensional space. At 1% steps that is
about 5,000 candidates, each three dot products -- exhaustive with numpy, no new dependency, and
**deterministic**, which the replay rules require of anything that has to reproduce.

Exhaustive also means the infeasible cases are honest. If no candidate clears the floor, the answer
is *no combination of these three books survives your limit* -- which says the negative-stance book
is not hedging anything. A solver would have returned the least-bad vector and said nothing.

The limit is real and worth stating: a mix of three books cannot invent a position none of them
holds. That is the right constraint. A holding that appears in no stance's thesis would have no
account of itself.

`combine` cannot do this job, and not only because it ignores the floor. When two alphas hold
opposite sides of a name it nets them off **and spreads the freed money over what is left** -- so a
hedge in the negative book, held against a long in the positive book, is cancelled and reinvested
into the long. It is the one function in the engine actively hostile to surviving a scenario. So the
blend happens in a step, over `features` tables, and only the finished books reach the weights
stage.

## The two alphas, and the three questions they answer

```
features.book_yes ┐
features.book_same├─► weights.blend    probabilities as the split, no floor
features.book_no  ┘
                  └─► weights.target   the candidate that clears the floor
```

Both read the same features, which is what makes them comparable -- the condition the `alphas`
docstring already sets for two alphas in one project. Three commands, and each answers one question:

| | asks |
| --- | --- |
| `--alpha target` | the strategy |
| `--alpha blend` | what the floor cost |
| `--alpha target --universe u_base` | whether the narrative was worth anything |

And with `benchmark: universe_equal_weight` each of those also reports whether ranking by margin of
safety beat holding the stance's universe outright. See [attribution.md](attribution.md).

## Where the judgement enters, and where it does not

The agent's whole reading of the world is about fifteen rows, and a person can disagree with all of
them in ten seconds:

| stance | industry | direction |
| --- | --- | --- |
| keeps spending | semis | strong + |
| keeps spending | utilities | + |
| keeps spending | hyperscalers | - |
| unchanged | staples | small + |
| breaks | gold | + |
| breaks | semis | strong - |

Everything downstream of that is measured. `betas` come from regressing asset returns on driver
series over history; `exposure` is those betas against the stance's driver moves; `valuation` is a
per-sector method over reported fundamentals. An asset whose betas carry t-stats near zero has no
measured exposure to the drivers at all, and putting it in a stance portfolio is pretence -- the
step reports it rather than ranking it.

This is the line the whole design turns on. Fifteen numbers a person can argue with, and five
hundred that were measured. An agent that asserts the five hundred produces weights that look
identical and mean nothing.

## Which page each step belongs to

**Narrative page.** The question, the schedule, the readings, the chart, and the checkpoint. It
produces three probabilities and nothing else the pipeline can see. No step reads a table from here.

**Build page.** Everything the agent proposes, in the order a person should review it:

| | new? |
| --- | --- |
| the drivers, and which way each moves per stance | the fifteen rows above |
| the sources those drivers need -- cost, key, **and how far back they go** | approval |
| three universes, dated, each with a `sector` column | |
| `valuation` -- fair value and margin of safety, method by sector | new, built once, reused by every narrative |
| `betas`, then `exposure` | new |
| three books -- industry split by exposure, names by margin of safety | one script, three universes |
| `blend`, then `target` | new |

It ends on the screen the original plan called screening: the ranked names with their weights, and
the belief-against-holding line above them.

**Backtest page.** The replay, the three comparisons, and the label that matters -- *in sample*,
because the reading was written by an agent that had read news about these years. What it is good
for is higher fees, empty periods and the drawdown path. Then `live: true`, and the number that
counts starts from the checkpoint date.

**Back to the narrative page.** That reading's dot is now marked as one that became a position, and
carries what the strategy has earned since.

Most of the second and third pages is the console that already exists. What is actually new is the
first page, and three steps.

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

Nine, and each means one thing.

| Word | What it is |
| --- | --- |
| **narrative** | A question the user wrote, ingesting news on a schedule or when asked. Live or not. Never edited. |
| **stance** | One of the three futures a narrative has: positive, neutral, negative. Fixed by the question. Nothing authors them and nothing replaces them. |
| **reading** | Where a narrative stands at one moment: the agent's text, a probability with a reason for each stance, and the window of news it read. Appended, never replaced. The three sum to 100. |
| **checkpoint** | A reading and the run it produced. What ties a strategy back to what was believed when it was built, and the frontier for everything that run is measured on. |
| **resolution** | The rule that decides whether the positive or negative future happened. Written once, at creation. What makes a reading scoreable. |
| **driver** | An observable series a stance moves: semiconductor billings, power demand, reported margins. Ingested like any other source. What the agent chooses; not what it estimates. |
| **exposure** | What an asset returns if a stance arrives. Betas measured against drivers over history, applied to the stance's driver moves. Used twice: the industry split inside a book, and the floor check at the end. |
| **book** | One stance's portfolio. Industries weighted by exposure, names inside an industry ranked by margin of safety. Three books to a reading, in `features` -- only the finished portfolios reach the weights stage. |
| **floor** | The worst a portfolio may return under any stance. A candidate that breaks it is infeasible however well it scores. |

`topic` and `deck` are gone: a narrative is the container, and one word is enough. `snapshot` is not
used here — `plan.snapshot()` already holds it for the job-spec state.
