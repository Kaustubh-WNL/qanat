# Which part of it earned the money

A backtest answers one question: did this strategy make money over this window. It does not
answer the question anyone actually has, which is *which part of it did*.

A run that starts from a news story and ends in a weights table has two claims inside it. One is
about the world — chip export rules will lift domestic substitute makers. The other is arithmetic
— hold the top decile of six-month momentum, weighted by the inverse of price to earnings. The
replay tests the arithmetic. The person reads the result as a verdict on the world.

Usually it is not. Momentum and value pay on most groups of stocks, so the formula can return
`+14%` on semiconductors for reasons that have nothing to do with export rules. The number is
honest and the credit goes to the wrong claim, which is worse than no number at all: a strategy
that cannot be tested stalls, and one that passes for the wrong reason gets funded.

Separating the two is not extra machinery. It is a consequence of where each one already lives.

## The idea lives in the universe, the arithmetic lives in the step

A **universe** is the list a portfolio is allowed to hold, point-in-time when its file carries
`from` and `to` — see *Point-in-time universes* in [backtest.md](backtest.md). A **step** points at
one by name and picks from inside it.

```
universe  ->  these 300 names are holdable on this date
step      ->  of those, hold these 20, at these weights
```

So a hypothesis that names a sector, a theme, or a supply chain is a statement about **which
universe**. Everything the hypothesis claims is spent the moment the universe is written down, and
nothing downstream needs to know where it came from.

That is what makes it measurable. A universe is already a swappable argument: `run_backtest` takes
one, it moves the run's digest, and the result carries `universe overridden to 'X' for this run`.
Swap it, hold everything else, and the difference between the two nets is what the idea about the
world was worth.

## An agent writing a pipeline must write a universe, never a list in the script

The failure is quiet and it is the one to design against. Given a news story, the obvious thing for
an agent to emit is the filter inline:

```python
df = df[df.symbol.isin(["NVDA", "TSM", "AMD", "ASML"])]     # no
```

Two separate things break.

**The names are today's.** A list chosen now, applied to 2016, holds the companies that turned out
to win and omits the ones that went bust. That is survivorship bias, and here it lands in the worst
possible place — the profit it invents is attributed to the idea about the world, which is the exact
quantity the comparison exists to measure. A universe csv with `from` and `to` cannot do this;
`ctx.universe()` returns the members of the deciding day and `qanat check` warns when the dates are
missing.

**The idea stops being swappable.** A filter inside a script is invisible to the universe override,
so the two runs the comparison needs are the same run. The hypothesis is still in there, but it can
no longer be turned off, which means it can no longer be priced.

The rule, then: whatever the hypothesis says about which names, goes in a `Universe` with dates, and
the step says `universe:`. An agent that hardcodes symbols has produced a number nobody can
decompose.

## Four runs, and what each one answers

With the idea in one place and the arithmetic in another, both can be switched off independently.

|                          | the universe the idea named | the base universe |
| ---                      | ---                         | ---               |
| **the step's weights**   | `+14.2%`                    | `+13.6%`          |
| **equal weight**         | ?                           | ?                 |

Read across for whether the idea about the world paid. Read down for whether the arithmetic paid.

The bottom left is the cell nobody checks and the one that decides most cases: *what if you had
held the sector the news pointed at, in equal parts, and done nothing else.* If that returns
`+13%`, then the screening added nothing, the narrowing added nothing, and the honest report is
that an index fund and an afternoon off would have matched the whole apparatus.

All four runs must be the same window, the same costs, the same rebalance gap, with exactly one
thing varied. Otherwise the difference between two numbers is a difference between two questions.

## How to run each of the four

| cell | how |
| --- | --- |
| step × named universe | an ordinary run |
| step × base universe | `--universe base`, which needs a base universe declared in the project |
| equal weight × named universe | `benchmark: universe_equal_weight` |
| equal weight × base universe | `benchmark: equal_weight` |

The bottom two are the two floors, and they were not always both there. `_price_frame` reads the
prices table whole and `benchmark_returns` averages every column in it, so `equal_weight` holds
everything *priced* rather than everything *holdable*. Where a project prices exactly one index
those are the same list, and describing `equal_weight` as the whole universe in equal parts is true
by accident. Where a project prices several sectors so a hypothesis can choose between them, they
are not, and that benchmark answers about a wider pool than the run was allowed to hold — which
moves the sector call's contribution into the floor and hides exactly what this page is for.

`universe_equal_weight` is the one that follows the run: the override if the run had one, otherwise
the alphas' own `universe:`, with membership read as of each decision date. Redefining
`equal_weight` would have fixed the grid and changed the meaning of every number already recorded
under that name, so it keeps its behaviour and the second spec keeps its own.

A rule that narrows to a pool owes an answer to both. Beating `equal_weight` and losing to
`universe_equal_weight` is a specific, common, diagnosable result: the pool was the whole edge and
everything after it was decoration.

## These runs are not a search

The trial ledger exists because a number picked from fifty attempts is not the number it appears to
be, and `bar: count` raises the threshold as the count climbs. An ablation is the opposite activity.
It varies one input in order to take credit away from a result that already exists, and it cannot
produce a better number to keep — switching the idea off does not give you a new strategy, it gives
you a smaller claim about the old one.

Counted as attempts, they make the bar stricter for having been more careful, which is a rule that
teaches people to be less careful. Whatever field eventually separates a test from an examination,
these belong on the examination side.

## What it is worth printing

One run already prints the vertical half of the grid, and says which floor it is reading:

```
    net                +14.2%  compounded
    benchmark          +13.1%  the universe, equally
    excess              +1.1%  what the rule added
```

The horizontal half takes the second run, and it is the line worth adding:

```
    same rule, base universe     +13.6%
    the pool was worth            +0.6%
```

Together they say the thing a backtest on its own cannot: the ranking added `+1.1%` over holding the
pool, and choosing the pool added `+0.6%` over holding the market. Both small. Most of the `+14.2%`
was the market, and the honest report says so in two lines that cost one extra replay.

Every other backtester stops at whether the rule worked. And this settles an argument about the
product rather than leaving it to taste: if that last line sits near zero across a few hundred
hypotheses, then the news story on the front page is decoration, and the thing that says so is the
tool's own output.
