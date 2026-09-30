# A filings panel, and a value factor on top of it

**Every number in this example is invented.** No real company appears, no real
filing, no real price. `seed/make_data.py` writes the two data files and it is the
only source of them. What is real is the *shape*: how a filings table is keyed, what
it hides, and what a pipeline gets wrong when it ignores that.

Nothing here touches the network. `examples/fx-bundled` is the opposite trade — real
ECB rates, a simpler question — and the two are meant to be read together.

```sh
uv run qanat run
uv run qanat backtest --from 2017-06-30 --to 2026-06-30 --rebalance 60d --split 2022-01-01
```

## Why it is synthetic when fx-bundled is not

Filings are free from DART and SEC, so the data is not the problem. The problem is
that shipping a copy inside a public repository is *storing* it, and whether we may
do that depends on terms nobody here has read yet. So the choice was a real panel
with an open question over it, or an invented one that says so on every surface. This
is the second.

## The one thing this example is for

**A price has one date. A filing has two.**

| column | what it means |
| --- | --- |
| `period_end` | the quarter the numbers describe |
| `filed_at` | the day those numbers became public, 35 to 100 days later |

A factor keyed on `period_end` knows a company's profit weeks before anyone could
read it. The backtest that comes out looks good and means nothing.

Qanat shadows every table with an as-of view during a replay, so a step reads the
past without knowing it is being replayed. But it has to be told **which column is
the clock**, and neither of these two names is one it recognises:

```yaml
time_columns:
  raw.filings: filed_at
  normalized.filings: filed_at
```

**Without those two lines the table has no clock at all**, and a table with no clock
is not filtered — every replay would read every filing ever made. It does not fail
and it does not warn at `qanat check`. It just quietly answers the wrong question.

What the two lines are worth, measured on this data:

```
as of 2023-06-30
  quarters ended by then      : 856
  filings published by then   : 826
  ended but not yet published :  30   <- one quarter, thirty companies
  rows the as-of view shows   : 826
```

## Three other things in the data on purpose

**Filings get restated.** 85 of the 1,148 rows are amendments: the same quarter filed
again later with a different profit, usually lower. Both rows stay in the table,
because which one you were allowed to know depends on the day you ask.

```
symbol period_end   filed_at form  net_income
  SY02 2023-03-31 2023-05-09    Q      16.550   <- what the market had
  SY02 2023-03-31 2023-09-13  Q/A      15.606   <- what turned out to be true
```

A table keyed on `(symbol, period_end)` alone keeps only the second row and loses the
four months when the first one was the truth. That is why the source key is
`[symbol, period_end, filed_at]`.

The cost of keeping both is that **`normalized.filings` is one row per filing event,
not one row per quarter**, and a reader that sums `net_income` over it double counts
every restated quarter. `fundamentals.sql` dedupes first, and anything else reading
that table has to as well. An agent pointed at this project over MCP spotted exactly
this on its second question, which is the argument for the column being called
`is_amendment` rather than being left implicit in the form code.

**Companies arrive and leave.** Four of the thirty list during the window and six
delist. `universes/companies.csv` carries `from` and `to`, so a backtest holds the
names that existed on the day it was deciding. Without those columns it would be
today's list applied to the past, and the six that left would be missing from every
number.

**The filing lag is not a constant.** It runs 35 to 100 days and two companies are
chronically late. A pipeline that shifts the quarter by a fixed 45 days is early for
some names and late for others.

## The pipeline

```
raw.filings ─┐                              (clock: filed_at)
             ├─→ normalized.filings ─→ features.fundamentals ─┐
raw.prices ──┴─→ normalized.prices ──────────────────────────┴─→ features.value
                                                                      │
                                                          weights.value_alpha
```

| step | what it does |
| --- | --- |
| `normalize_filings` | types both dates, and turns `lag_days` and `is_amendment` into columns you can see |
| `fundamentals` | trailing twelve month profit. Per quarter it takes the newest filing it can see, then the four newest quarters, and `HAVING count(*) = 4` refuses to call three quarters a year |
| `value` | divides that by market cap. Carries `staleness_days` and `price_age_days`, which are the two ways a name can be wrong |
| `value_tilt` | holds the six highest yields, equally. Long only, so the benchmark means what it says |

## The result, and what it is worth

```
net            +288.461%  compounded
benchmark      +153.504%  the universe, equally
excess         +134.958%  what the rule added

in sample       +23.583%  28 periods,  +0.966% each
out of sample  +214.332%  26 periods,  +4.729% each

sharpe             0.98   over 54 periods
max drawdown    -35.586%
```

**Do not read that as a working factor.** Two things in the block above say it is
not, and both are visible without leaving the report.

The out-of-sample half earned five times as much per period as the in-sample half. A
real edge does not do that. Noise does.

And a Sharpe of 0.98 over nine years is a t-stat of about 2.9, which is one number
from one try of one rule. Divided by the number of rules a person would try before
stopping here, it is not evidence of anything.

So the honest check is to run the same rule on other worlds. `seed/dispersion.sh`
does that, and this is what it prints:

```
seed   net          benchmark    excess       in-sample    out-of-s     sharpe
11     +307.141%    +412.960%    -105.819%    +133.508%    +74.358%     1.10
22     +1105.564%   +604.483%    +501.081%    +165.747%    +353.651%    1.55
33     +102.887%    +204.444%    -101.558%    +30.165%     +55.869%     0.59
44     +65.930%     +138.741%    -72.811%     -10.833%     +86.089%     0.54
55     +359.259%    +252.030%    +107.229%    +133.039%    +97.074%     0.96
```

Three of the five are negative. The spread runs from −106% to +501%. **The committed
+134.958% is one draw out of that, and the factor has no reliable edge in this data.**
Six names picked from a pool of about twenty-four, rebalanced six times a year, has
enormous dispersion, and nine years of it is still a small sample.

That is the point of the example rather than a flaw in it. The plumbing is what is
being demonstrated: the clock, the restatements, the universe dates, and the two
floors. A demo that printed a clean win would have taught that the author picked a
good seed.

One number in `seed/make_data.py` was picked and then changed, and it is written down
there: `KAPPA`, how strongly a cheap name drifts up, started at `8e-5` and printed
+205% over the pool. That is the constant, not a finding, so it is `2e-5` now — which
barely moved the result, which is itself the evidence that the drift was never what
was driving it.

## Reproducing the data

```sh
uv run python seed/make_data.py         # rewrites the committed files, byte for byte
uv run python seed/make_data.py 11      # a different world, same shape
sh seed/dispersion.sh                   # five worlds, one line each
```

The gzip header carries no timestamp, so the same seed gives the same bytes and the
committed files can be checked against a fresh run.

## What this example does not do

- **No sector or size neutrality.** The ranking is raw, so a sector that did well can
  carry it. `docs/attribution.md` is what the two benchmark floors are for.
- **No 주석, no corporate actions, no survivorship-free universe beyond the dates in
  the file.** Those are the hard rows, and they are the paid layer rather than the
  demo.
- **No live mode.** `backtest.live` is off. The same project runs forward by swapping
  the clock, and that is `docs/backtest.md`.

---

Nothing here is investment advice, and none of these companies exist.
