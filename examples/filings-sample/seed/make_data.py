"""Make the two files this example runs on. Every number in them is invented.

    uv run python seed/make_data.py            # the committed files
    uv run python seed/make_data.py 11         # a different world, same shape

It writes `data/filings.csv.gz`, `data/prices.csv.gz` and `universes/companies.csv`,
and it is deterministic: the same seed gives the same bytes, so the committed files
can be checked against a fresh run. `seed/dispersion.sh` uses the seed argument to
show what one backtest on one world is worth.

Why generate instead of downloading something real: a filings panel is the one thing
this project needs that cannot be shipped from a public source without deciding whose
licence covers it. So the shape is real and the values are not, and every surface says
so.

What is modelled on purpose, because each one breaks a naive pipeline:

**A filing has two dates.** `period_end` is the quarter it describes. `filed_at` is the
day it became public, 35 to 100 days later. A factor built on `period_end` knows a
number weeks before anybody could read it.

**Filings get restated.** About one in twelve quarters is filed again later as an
amendment with a different profit, usually lower. The first number was what the market
had; the second is what turned out to be true. A table keyed on the quarter alone
silently keeps only the second.

**Companies arrive and leave.** Four list during the window and six delist. The
universe file carries `from` and `to` so a backtest holds the names that existed on the
day it was deciding, not the ones that survived to the end.
"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260930
START = pd.Timestamp("2016-01-01")
END = pd.Timestamp("2026-06-30")
N = 30

SECTORS = ["industrial", "software", "materials", "consumer", "health"]
ROOT = Path(__file__).resolve().parent.parent

# How strongly a cheap stock drifts up, per day, per cross-sectional standard
# deviation of earnings yield. 2e-5 is about half a percent a year, which is small
# on purpose. A synthetic panel can be given any edge at all, so a big one would
# only be teaching that the author picked a big number.
#
# It was 8e-5 first. Concentrated in six names and compounded over nine years that
# came out as +205% over the pool, which is not a finding, it is this constant.
KAPPA = 2e-5


def companies(rng: np.random.Generator) -> pd.DataFrame:
    """Thirty invented companies, four of them listing late and six leaving early."""
    rows = []
    for i in range(N):
        rows.append({
            "symbol": f"SY{i + 1:02d}",
            "name": f"Synthetic Company {i + 1:02d}",
            "sector": SECTORS[i % len(SECTORS)],
            "quality": float(rng.normal()),
            "scale": float(np.exp(rng.normal(6.0, 0.8))),   # revenue, millions
            "margin0": float(np.clip(rng.normal(0.09, 0.05), -0.04, 0.24)),
            "shares0": float(np.exp(rng.normal(4.0, 0.5))),  # millions
            "lag": int(rng.integers(35, 76)),
            "listed": START,
            "delisted": pd.NaT,
        })
    df = pd.DataFrame(rows)

    # Two chronic late filers. Real ones exist and they are the reason a pipeline
    # cannot assume a fixed lag.
    for i in rng.choice(N, size=2, replace=False):
        df.loc[i, "lag"] = int(rng.integers(85, 101))

    late = rng.choice(N, size=4, replace=False)
    for i in late:
        df.loc[i, "listed"] = pd.Timestamp("2017-01-01") + pd.Timedelta(
            days=int(rng.integers(0, 1500)))

    gone = rng.choice([i for i in range(N) if i not in late], size=6, replace=False)
    for i in gone:
        df.loc[i, "delisted"] = pd.Timestamp("2018-06-01") + pd.Timedelta(
            days=int(rng.integers(0, 2500)))
        # A company that leaves has usually been going wrong for a while. Without
        # this the delisted names are indistinguishable and survivorship costs
        # nothing, which is not how it works.
        df.loc[i, "quality"] = float(df.loc[i, "quality"]) - 1.2

    return df


def quarters() -> list[pd.Timestamp]:
    return list(pd.date_range(START - pd.offsets.QuarterEnd(4), END, freq="QE"))


def fundamentals(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """One row per company per quarter: the numbers as they were first reported."""
    qs = quarters()
    out = []
    for c in df.itertuples():
        revenue = c.scale
        equity = c.scale * float(np.exp(rng.normal(0.4, 0.3)))
        margin = c.margin0
        shares = c.shares0
        leverage = float(np.clip(rng.normal(2.1, 0.5), 1.1, 4.0))
        for q in qs:
            # Revenue grows with a drift tied to the company's latent quality, with a
            # mild seasonal pattern so a year-on-year comparison is not the same as a
            # quarter-on-quarter one.
            g = 0.004 + 0.010 * c.quality + rng.normal(0, 0.035)
            season = 1.0 + 0.06 * np.sin((q.quarter - 1) * np.pi / 2)
            revenue = max(revenue * (1.0 + g), c.scale * 0.15)
            # Margin mean-reverts towards a level quality sets, so a good company is
            # not good in a straight line.
            target = 0.06 + 0.035 * c.quality
            margin += 0.25 * (target - margin) + rng.normal(0, 0.018)
            margin = float(np.clip(margin, -0.30, 0.34))
            net = revenue * season * margin
            equity = max(equity + net * 0.65, c.scale * 0.05)
            if rng.random() < 0.06:
                shares *= 1.0 + float(rng.normal(0.03, 0.02))   # issuance
            elif rng.random() < 0.08:
                shares *= 1.0 - abs(float(rng.normal(0.015, 0.01)))  # buyback
            out.append({
                "symbol": c.symbol,
                "period_end": q,
                "revenue": round(revenue * season, 3),
                "net_income": round(net, 3),
                "equity": round(equity, 3),
                "assets": round(equity * leverage, 3),
                "shares_out": round(shares, 4),
            })
    return pd.DataFrame(out)


def filings(fund: pd.DataFrame, df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Turn the quarterly truth into filing events, with lags and amendments.

    One quarter can appear twice: once as it was first reported, and once as an
    amendment with a different profit. Both rows are kept, because which one you
    were allowed to know depends on the day you are asking.
    """
    lag = dict(zip(df["symbol"], df["lag"]))
    listed = dict(zip(df["symbol"], df["listed"]))
    delisted = dict(zip(df["symbol"], df["delisted"]))
    rows = []
    for r in fund.itertuples():
        base = lag[r.symbol] + int(rng.integers(-6, 9))
        filed = r.period_end + pd.Timedelta(days=max(base, 20))
        # A filing that lands before the company listed, or after it left, never
        # happened.
        if filed < listed[r.symbol]:
            continue
        if pd.notna(delisted[r.symbol]) and filed > delisted[r.symbol]:
            continue
        rows.append({
            "symbol": r.symbol,
            "period_end": r.period_end,
            "filed_at": filed,
            "form": "Q" if r.period_end.quarter != 4 else "A",
            "revenue": r.revenue,
            "net_income": r.net_income,
            "equity": r.equity,
            "assets": r.assets,
            "shares_out": r.shares_out,
        })
        if rng.random() < 0.08:
            amended = filed + pd.Timedelta(days=int(rng.integers(45, 151)))
            if pd.notna(delisted[r.symbol]) and amended > delisted[r.symbol]:
                continue
            if amended > END:
                continue
            # Restatements are usually downward. Occasionally they are not.
            f = float(rng.uniform(0.70, 0.97)) if rng.random() < 0.8 \
                else float(rng.uniform(1.02, 1.15))
            rows.append({
                "symbol": r.symbol,
                "period_end": r.period_end,
                "filed_at": amended,
                "form": ("Q" if r.period_end.quarter != 4 else "A") + "/A",
                "revenue": round(r.revenue * (1.0 + (f - 1.0) * 0.3), 3),
                "net_income": round(r.net_income * f, 3),
                "equity": round(r.equity * (1.0 + (f - 1.0) * 0.5), 3),
                "assets": r.assets,
                "shares_out": r.shares_out,
            })
    out = pd.DataFrame(rows).sort_values(["symbol", "period_end", "filed_at"])
    return out[out["filed_at"] <= END].reset_index(drop=True)


def prices(fil: pd.DataFrame, df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """A daily close per company, drifting slightly towards what it earns.

    The drift uses the earnings yield **as filed on that day**, not the quarter's
    final number, because that is what anybody could have seen. It is what gives the
    factor its small edge, and it is small on purpose.
    """
    days = pd.bdate_range(START, END)
    syms = list(df["symbol"])
    listed = dict(zip(df["symbol"], df["listed"]))
    delisted = dict(zip(df["symbol"], df["delisted"]))

    # Latest known trailing profit per symbol, walked forward one day at a time.
    events = {s: g[["filed_at", "period_end", "net_income", "shares_out"]]
              .sort_values("filed_at").to_dict("records")
              for s, g in fil.groupby("symbol")}
    cursor = {s: 0 for s in syms}
    known: dict[str, dict[pd.Timestamp, float]] = {s: {} for s in syms}
    ttm: dict[str, float] = {}
    shares: dict[str, float] = dict(zip(df["symbol"], df["shares0"]))

    px = {s: float(np.exp(rng.normal(3.2, 0.5))) for s in syms}
    beta = {s: float(np.clip(rng.normal(1.0, 0.3), 0.3, 1.8)) for s in syms}
    rows = []
    for d in days:
        market = float(rng.normal(0.0003, 0.009))
        # Refresh what each company has told the market by today.
        for s in syms:
            evs = events.get(s, [])
            while cursor[s] < len(evs) and evs[cursor[s]]["filed_at"] <= d:
                e = evs[cursor[s]]
                known[s][e["period_end"]] = e["net_income"]
                shares[s] = e["shares_out"]
                cursor[s] += 1
            last4 = sorted(known[s])[-4:]
            if len(last4) == 4:
                ttm[s] = sum(known[s][p] for p in last4)

        live = [s for s in syms
                if listed[s] <= d and (pd.isna(delisted[s]) or d <= delisted[s])]
        ey = {}
        for s in live:
            if s in ttm and px[s] * shares[s] > 0:
                ey[s] = ttm[s] / (px[s] * shares[s])
        if len(ey) > 4:
            v = np.array(list(ey.values()))
            mu, sd = v.mean(), v.std()
            z = {s: (ey[s] - mu) / sd if sd > 0 else 0.0 for s in ey}
        else:
            z = {s: 0.0 for s in ey}

        for s in live:
            drift = 0.0002 + KAPPA * float(np.clip(z.get(s, 0.0), -3, 3))
            r = drift + beta[s] * market + float(rng.normal(0, 0.013))
            px[s] = max(px[s] * (1.0 + r), 0.4)
            rows.append({"date": d, "symbol": s, "close": round(px[s], 2)})
    return pd.DataFrame(rows)


def write_gz(df: pd.DataFrame, path: Path) -> None:
    """Gzip with no timestamp in the header, so the bytes are reproducible."""
    body = df.to_csv(index=False).encode()
    with open(path, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(body)


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else SEED
    rng = np.random.default_rng(seed)
    df = companies(rng)
    fund = fundamentals(df, rng)
    fil = filings(fund, df, rng)
    px = prices(fil, df, rng)

    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "universes").mkdir(exist_ok=True)
    write_gz(fil, ROOT / "data" / "filings.csv.gz")
    write_gz(px, ROOT / "data" / "prices.csv.gz")

    uni = df[["symbol", "name", "sector", "listed", "delisted"]].copy()
    uni["from"] = uni["listed"].dt.strftime("%Y-%m-%d").where(
        uni["listed"] > START, "")
    uni["to"] = uni["delisted"].dt.strftime("%Y-%m-%d").fillna("")
    uni[["symbol", "name", "sector", "from", "to"]].to_csv(
        ROOT / "universes" / "companies.csv", index=False)

    amended = int(fil["form"].str.endswith("/A").sum())
    print(f"filings   {len(fil):>7,} rows, {amended} of them amendments")
    print(f"prices    {len(px):>7,} rows")
    print(f"companies {len(uni):>7,}  "
          f"{int((uni['from'] != '').sum())} listed late, "
          f"{int((uni['to'] != '').sum())} delisted")
    print(f"window    {px['date'].min().date()} → {px['date'].max().date()}")
    if seed != SEED:
        print(f"seed      {seed}, not the committed {SEED}")


if __name__ == "__main__":
    main()
