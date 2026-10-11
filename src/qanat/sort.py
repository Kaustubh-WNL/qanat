"""One sort, parameterised, so a project has something to replay on day one.

The four scripts this file replaced were momentum, reversal, low_vol and
neutral_momentum, and each of them did the same three things after computing one
number per symbol: rank the universe, keep the top few, weight them equally. The
number was the only difference between them -- a trailing return, a standard
deviation, a shorter trailing return -- and a number per symbol per date is an
**indicator**, which belongs in the features stage with every other computed
column.

So there is no catalogue here. There is one step that reads an indicator column
and turns it into a basket, and the variation lives in `options.column` rather
than in a different script. That is also the honest shape for what the engine is
for: testing whether an indicator meant anything requires building a paper basket
from it on each rebalance date, and the procedure for doing that never changes.

The sort is deliberately plain. It is a rule you could write on a napkin, because
the point is to have something real to replay on day one, not to hand anybody an
edge.
"""

from __future__ import annotations

from pathlib import Path

#: The step that turns one indicator column into a basket. `column` says which
#: column to sort on, `high_is_good` says which end is the good end, and `top_n`
#: says how many to hold. Weights are equal and sum to 1, so no budget appears
#: anywhere in it.
SORT = '''"""Sort on one indicator, hold the top names, weight them equally.

Reads a table with one row per symbol per date and a column to sort on. Writes a
basket: a weight per symbol, summing to 1, with the score it was picked on and
the date it was picked.

options:
  reads         the table to sort, e.g. features.momentum
  column        the column to sort on
  high_is_good  true when a high value is the good end (default true)
  top_n         how many names to hold (default 4)
"""
import pandas as pd


def run(ctx):
    o = ctx.options
    sym = o.get("symbol_column", "symbol")
    date = o.get("date_column", "date")
    col = o["column"]
    top_n = int(o.get("top_n", 4))
    high_is_good = bool(o.get("high_is_good", True))

    rows = ctx.read(o["reads"])
    if rows.empty:
        ctx.log(f"{o['reads']} is empty, so there is nothing to sort", "warn")
        return pd.DataFrame(columns=["symbol", "weight", "score", "as_of"])

    # One row per symbol: the newest reading each one has. A sort compares names
    # on the same date, and the as-of views have already hidden anything newer.
    rows = rows.sort_values(date).groupby(sym, as_index=False).last()

    held = ctx.universe()
    allowed = set(held[sym if sym in held.columns else "symbol"])
    rows = rows[rows[sym].isin(allowed)]
    rows = rows[rows[col].notna()]

    if len(rows) < top_n:
        ctx.log(f"only {len(rows)} symbols have a {col}, and {top_n} were asked for", "warn")
        return pd.DataFrame(columns=["symbol", "weight", "score", "as_of"])

    picked = (rows.nlargest(top_n, col) if high_is_good else rows.nsmallest(top_n, col)).copy()
    picked["weight"] = 1.0 / len(picked)
    out = picked.rename(columns={sym: "symbol", col: "score", date: "as_of"})
    return out[["symbol", "weight", "score", "as_of"]].reset_index(drop=True)
'''

#: One indicator to sort on, so `qanat init --demo` has a column before it has a
#: basket. Trailing return over `lookback` days, which is the plainest indicator
#: there is and the one the old momentum script computed inline.
INDICATOR = '''"""Trailing return over `lookback` days: one number per symbol per date.

An indicator, not a basket. It says nothing about what to hold; the sort step
reads this column and decides that.

options:
  reads     a table with a symbol, a date and a price
  lookback  how many days back to measure from (default 20)
"""
import pandas as pd


def run(ctx):
    o = ctx.options
    sym = o.get("symbol_column", "symbol")
    date = o.get("date_column", "date")
    px = o.get("price_column", "close")
    lookback = int(o.get("lookback", 20))

    bars = ctx.read(o["reads"]).sort_values(date)
    rows = []
    for name, g in bars.groupby(sym):
        if len(g) <= lookback:
            continue
        past, now = g[px].iloc[-lookback - 1], g[px].iloc[-1]
        if past and past > 0:
            rows.append({"symbol": name, "date": g[date].iloc[-1],
                         "trailing_return": now / past - 1.0})
    return pd.DataFrame(rows, columns=["symbol", "date", "trailing_return"])
'''


def write_script(root: Path, name: str, body: str) -> str:
    """Write one script under `steps/` and return its project-relative path."""
    steps = Path(root) / "steps"
    steps.mkdir(parents=True, exist_ok=True)
    path = steps / f"{name}.py"
    path.write_text(body)
    return f"steps/{name}.py"
