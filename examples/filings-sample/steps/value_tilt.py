"""features -> weights. The one table in the weights stage is the portfolio.

Hold the highest earnings yields, equally. Long only by default, because the
project's benchmark is `universe_equal_weight` and that floor holds the pool long
only: measuring a market-neutral book against it would subtract the market from one
side of the comparison and not the other, which reads as a verdict on the ranking
and is not one.

`short_n` turns the other shape on. With it set, the book is half long and half
short and the absolute weights still sum to 1 -- and then the benchmark lines in the
report stop being the right question to ask of it.

Two filters before the ranking, and both are hygiene rather than alpha:

**The universe, as of the day being decided.** `ctx.universe()` returns the members
of that day, so a company that had not listed yet is not held, and one that had
already delisted is not either. Without the dates in the file this would be today's
list applied to the past, and the six companies that left would be missing from
every backtest.

**Two ages.** A name whose newest filing is older than `max_staleness_days` is
dropped, because its yield is a profit from a year ago over today's price. A name
whose last price is more than `max_price_age_days` old is dropped too: it has
stopped trading, and a yield struck on a price that no longer exists looks exactly
like a live one. The universe dates already catch the delisted names, so this is
the second of two independent guards rather than the only one.

No budget appears here. The weights say what share of a portfolio each name is.
"""

import pandas as pd


def run(ctx):
    val = ctx.read("features.value")
    allowed = set(ctx.universe()["symbol"])
    cols = ["symbol", "weight", "earnings_yield", "staleness_days",
            "price_age_days", "as_of"]

    long_n = int(ctx.options.get("long_n", 6))
    short_n = int(ctx.options.get("short_n", 0))
    max_stale = int(ctx.options.get("max_staleness_days", 210))
    max_price_age = int(ctx.options.get("max_price_age_days", 10))

    val = val[val["symbol"].isin(allowed)].dropna(subset=["earnings_yield"])
    gone = val[val["price_age_days"] > max_price_age]
    val = val[val["price_age_days"] <= max_price_age]
    if len(gone):
        ctx.log(f"{len(gone)} name(s) dropped for not trading in {max_price_age} days: "
                f"{', '.join(sorted(gone['symbol']))}")

    stale = val[val["staleness_days"] > max_stale]
    val = val[val["staleness_days"] <= max_stale]
    if len(stale):
        ctx.log(f"{len(stale)} name(s) dropped for filing more than {max_stale} days ago: "
                f"{', '.join(sorted(stale['symbol']))}")

    if len(val) < long_n + short_n:
        ctx.log(f"only {len(val)} names ranked, need {long_n + short_n} — holding nothing",
                "warn")
        return pd.DataFrame(columns=cols)

    ranked = val.sort_values("earnings_yield", ascending=False)
    longs = ranked.head(long_n).copy()
    if short_n:
        # Each side carries half the book, so the absolute weights sum to 1 and
        # neither side can quietly grow larger than the other.
        shorts = ranked.tail(short_n).copy()
        longs["weight"] = 0.5 / long_n
        shorts["weight"] = -0.5 / short_n
        out = pd.concat([longs, shorts])
        ctx.log(f"long {', '.join(longs['symbol'])} · short {', '.join(shorts['symbol'])}")
    else:
        longs["weight"] = 1.0 / long_n
        out = longs
        ctx.log(f"long {', '.join(longs['symbol'])}")
    return out[cols].reset_index(drop=True)
