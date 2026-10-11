# Scheduled ingest

Two-minute **real HTTP ingest** demo — a source on a `schedule:`, not live trading: a mock
market feed on port **8765**, Qanat polling it, and every downstream step firing on its own
cron line.

From the repo root:

```bash
sh scripts/demo-run.sh
```

What happens:

1. History bootstrap (`bars_seed` → `raw.daily_prices`)
2. The scheduler starts and serves MCP on **http://127.0.0.1:8421/mcp**
3. Live ticks append every minute (`daily_prices` REST source, `mode: append`), and
   `normalize`, `momentum`, `risk` and `portfolio` follow on the same minute

There is no page to open. Point an agent at the MCP endpoint and ask what is landing —
`list_runs` is the one that shows the clock working:

```bash
claude mcp add qanat-demo --transport http http://127.0.0.1:8421/mcp
```

Environment overrides:

| Variable | Default | Meaning |
| --- | --- | --- |
| `DEMO_FEED_PORT` | `8765` | Mock feed port |
| `QANAT_HOST_PORT` | `8421` | Port `qanat serve` listens on |
| `DEMO_DURATION` | `120` | How long to leave the scheduler running (seconds) |

Manual run:

```bash
# terminal 1
python3 ../../scripts/demo-feed.py

# terminal 2
uv run --project ../.. qanat run bars_seed
uv run --project ../.. qanat run news normalize momentum risk tone portfolio
uv run --project ../.. qanat serve --run-now
```
