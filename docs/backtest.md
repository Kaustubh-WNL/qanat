# The replay engine

The README covers running a backtest and reading the number. This is the rest of how it works.


## Net cannot be ranked on its own

Two runs that earned the same amount are not the same strategy if one of them halved on the way,
and a long-only rule in a rising market is not skill. So `totals` carries the denominator as well
as the numerator:

| field | |
| --- | --- |
| `vol` | sample standard deviation of net per period |
| `sharpe` | that ratio annualised by the rebalance gap, or `null` where it has no meaning |
| `max_drawdown` | worst fall from a high, walked from the compounded path |
| `periods_per_year` | the annualisation used, written down so the Sharpe can be checked |
| `benchmark_net` · `excess_net` | present only when `benchmark:` is set |

**Annualisation comes from the rebalance gap, not from 252.** A period here is a rebalance. A
weekly strategy annualised at 252 would be called five times more volatile than it is, so
`per_year("5d")` is 73 and `per_year("1w")` is 52.14. `qanat report` computes it the same way from
the same string, so the Sharpe drawn on the page and the one written into the run agree.

`sharpe` is `null` rather than `0.0` for a single period or a run that never moved. Reporting
zero would read as a measured result instead of an absent one.

**The t-stat falls out of it**: `t = sharpe × √years`. Which says the plain thing out loud — a
good ratio over three months is not the same evidence as the same ratio over ten years, and only
one of them should survive being divided by the number of things you tried.

## A basket is one cut of a ranking, and the indicator is the whole of it

`qanat backtest --indicator features.momentum:momentum`, or `indicators:` in the `backtest:` block,
scores a column on its own alongside the basket. Repeat the flag for several.

| field | |
| --- | --- |
| `ic` | rank correlation between the column and the return that followed, per as-of date |
| `spread` | the top group's mean return minus the bottom group's, split into `groups:` (default 5) |
| `autocorr` | rank correlation with the same column on the previous as-of date |
| `n` | names that had both a value and a price on both ends of the period |

The rows come back as `indicator_periods`, and `indicator_summary` holds one row per indicator over
the whole window: `ic_mean`, `ic_t`, which is that mean against its own scatter, and `ic_hit`, the
share of dates the correlation was positive. The pair is named the way `periods` and `totals` are. A mean of 0.08 carried by two dates out of forty reads
differently beside a hit rate of 0.5.

**Why it is not the same question as net.** A basket holds the top few names, so it answers what
that one cut paid. The IC asks whether the order was right across everything the column covered, and
the spread asks how far apart its two ends were. A column can rank the universe well and still lose
money in the basket, because the top four happened to be the part that failed, and the reverse
happens just as often with a small `top_n`.

**Correlation is on ranks, not values.** A column is used as an ordering, so one outlier should not
decide whether it worked.

**Both are measured on the period's own two price days.** The same `_price_at` fill rule applies: the
return begins at the first price strictly after the as-of date and ends at the first price strictly
after the next one. The indicator and the basket therefore read the same window, and an indicator
row only ever exists for a period that was priced.

**`ic` is `null` rather than `0.0`** where fewer than three names could be compared, or where the
column or the returns hold one value. Zero would read as a measured relationship of none.

**No spread rather than a narrow one.** With fewer than two names per end, the spread is not
reported and the run says so once, naming the `groups:` value that would fit. Quietly splitting ten
names into five groups of two and calling the ends a top and a bottom decile is how a measure stops
meaning what its name says.

**One sweep is not one trial.** Scoring twenty columns in a replay is twenty attempts at finding
something, and `_qanat_asks` is where that is kept. The engine does not record them for you:
`record_trial` is a call the caller makes, and `bar: {rule: count}` is what divides the significance
by the number of them. Without both, the best IC of twenty is the luckiest of twenty.

## The benchmark is priced on the strategy's own periods

Not on a calendar. A benchmark measured over a different window is a different question wearing
the same label, so `benchmark_returns` walks each period's own `priced_from → priced_to`.

Costs are not charged to it. A benchmark is what you could have held by doing nothing, and doing
nothing does not pay turnover.

`equal_weight` holds one share of everything priced at both ends of a period. A symbol not
trading across that period is dropped rather than counted as a zero return — it was not a
holding.

## There are two floors, and they answer different questions

| `benchmark:` | holds |
| --- | --- |
| a symbol in the prices table | that one thing |
| `equal_weight` | everything the prices table carries, in equal parts |
| `universe_equal_weight` | the run's universe, on each date, in equal parts |

`equal_weight` is the market as far as this project has one. It asks whether the rule beat holding
everything — which a rule that narrowed to a sector that doubled will pass without having picked
anything well.

`universe_equal_weight` asks the harder question. It holds the pool the step was choosing from, so
the gap between it and the run is what all the work *after* choosing the pool was worth: the
screen, the ranking, the weights. If a rule that holds four names out of thirty matches the thirty
held equally, the ranking earned nothing and the sector call earned everything.

Membership is read as of the day the portfolio was decided, not the day it was priced — the floor
has to be the pool the step could actually see. So it moves as the pool moved, and a universe whose
file has no `from`/`to` dates makes the floor carry the same survivorship bias the strategy does.
The run says so in a note rather than leaving the comparison looking cleaner than it is.

Which universe is the run's: the one passed to the run if there was one, otherwise the steps' own
`universe:`. Two priced together that name different universes get the same refusal they get
for disagreeing about `rebalance` — a book spanning two pools has no single pool to be measured
against. A run with no universe at all gets no benchmark lines and a note saying why, because the
market is not a stand-in for a pool that was never chosen.

Where the prices table and the universe are the same list, the two floors are the same number. They
come apart as soon as a project prices more than it is willing to hold — which is any project whose
hypotheses choose between sectors. [attribution.md](attribution.md) is what the pair is for.

## Point-in-time universes

A universe csv may carry `from` and `to` columns. When it does, `ctx.universe()` returns the
members **of the day the step is deciding**. Never a name before it was listed, never one that had
already been delisted. A blank `from` means since always, a blank `to` means still in.

Without those columns you get the same list every day. That is today's list applied to the past,
which is survivorship bias. The names that went bust are missing, so every number looks better
than it really was.

`qanat check` warns when a universe has no dates, and `qanat init` ships them.

## How the clock is enforced

Before each pass, every table is shadowed by a view holding only the rows that existed at that
moment, and the search path puts those views first. A step reads the past without knowing it is
being replayed, so a step that forgot to filter still cannot see the future.

A step that writes a row stamped after its own as-of date **fails**, rather than returning a
good-looking number.

## Net compounds

Each period is earned on what the last one left, so `net` agrees with the equity curve. The report
prints `sum of periods` beside it. Gross, fees and slippage are per-period amounts, and that
summed line is the one they reconcile against.

## Opening a single rebalance

`qanat report` gives you the periods. The `period` MCP tool gives you one of them
in full: what was held, what each name returned, and what was traded to get there.

The contributions add up to that period's gross, because the server recomputes them from what the
run recorded. It does not keep a second copy that could drift.

## It reports as it goes

A period needs only the portfolio decided at one stop and a price at both ends, so the replay
closes each period the moment the next pass finishes. The curve grows a point per rebalance
instead of appearing at the end.

A run that takes a minute is readable from the first few seconds, and `_qanat_bt_periods` has the
rows while it is still running. A test checks that scoring as it goes gives the same numbers as
scoring the whole set afterwards.

## A step can say how it wants to be run

`rebalance:` and `decay:` on the step are that step's own defaults. A five-day reversal and a
sixty-day momentum are not asking for the same gap.

What the run asks for wins, then the step's own, then the project's. Two priced in one basket
that disagree raise an error naming both, rather than letting one of them win silently.

## Costs are conditions of the run

`--fee-bps`, `--slippage-bps`, `--purge` and `--embargo` override `qanat.yaml` for one replay, and
they move the run's digest. Raising the fee until the edge dies is how you find out how much of the
edge was real.

## A replay puts the tables back

Each pass rewrites the derived tables from a slice of the past, so the last thing a backtest does
is one ordinary pass to restore them. A backtest never leaves your data truncated.

## Periods that held nothing are counted, and said so

A lookback longer than the warm-up, or a feature table that starts late, leaves a run holding
nothing for a stretch. Those periods are real and they belong in the money -- flat is a result.
They are not decisions, though, and averaging over them buries that: the hit rate counts them as
misses and the per-period figure divides a few real returns over many empty slots.

So `totals` carries `held_periods` and `flat_periods` alongside `hit_rate_held` and
`net_per_held_period`, and every surface that quotes the headline can qualify it. The report says
both, and neither figure is quoted
without the other. One step here reported `net +5.61%` and a `6.1%` hit rate having held a
portfolio in three periods out of thirty-three; both numbers mislead, in opposite directions.

## Scoring forward

A replay prices a window that already happened. Live scoring keeps going: `qanat serve` runs a pass
each time the data reaches the next as-of date on the rebalance grid, so `rebalance: 10d` gives a
result every ten days.

```yaml
backtest:
  live: true
  live_steps: [sort_momentum]       # which one, or which ones, to price
```

`live_steps` is not optional once a project holds more than one weights table. Pricing two together is a
third strategy, so the choice is not the scheduler's to make -- a project that cannot say gets one
error and stops trying, rather than failing every thirty seconds into a log nobody has open.

`live_from` is stamped by qanat, once, on the first pass that lands. It is the last date the data
held when scoring was switched on, and everything after it is a return nobody could have looked at
while choosing the step. Worked out fresh each time it would move forward daily and mean nothing;
stamped by a pass that then failed it would name a moment nothing was ever scored at, which is why
it is written after the run rather than before.

That is the one sense of out-of-sample that cannot be arrived at by looking. An out-of-sample half
was measured on rows that were already on disk when the step was picked: the data did not argue
back through the fitting, but it argued back through the person, because you knew how that year
went. `report` gives the forward return and the rate that half implied, and the gap between
them is the number worth reading.

Live produces a portfolio. It does not place an order.
