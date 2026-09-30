#!/bin/sh
# One backtest on one world is one number. This runs the same project on five other
# worlds and prints what changed.
#
#   sh seed/dispersion.sh
#
# Each run gets its own seed, its own data and its own store, in a temporary
# directory that is deleted afterwards. The committed data is never touched.
#
# It exists because the headline in README.md is a single draw, and the only honest
# way to say so is to make checking it one command.
set -e
HERE=$(cd "$(dirname "$0")/.." && pwd)
QANAT=$(cd "$HERE/../.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

printf '%-6s %-12s %-12s %-12s %-12s %-12s %s\n' \
       seed net benchmark excess in-sample out-of-s sharpe
for s in 11 22 33 44 55; do
  d="$WORK/s$s"
  mkdir -p "$d"
  cp "$HERE/qanat.yaml" "$d/"
  cp -r "$HERE/seed" "$HERE/steps" "$HERE/universes" "$d/"
  rm -rf "$d"/seed/__pycache__ "$d"/steps/__pycache__
  (
    cd "$d"
    uv run --project "$QANAT" python seed/make_data.py "$s" >/dev/null
    uv run --project "$QANAT" qanat run >/dev/null 2>&1
    uv run --project "$QANAT" qanat backtest --from 2017-06-30 --to 2026-06-30 \
        --rebalance 60d --split 2022-01-01 2>&1 |
      awk -v s="$s" '
        $1 == "net"       && $2 ~ /%/     { net = $2 }
        $1 == "benchmark" && $2 ~ /%/     { bm  = $2 }
        $1 == "excess"    && $2 ~ /%/     { ex  = $2 }
        $1 == "in"        && $2 == "sample" { is  = $3 }
        $1 == "out"       && $2 == "of"     { oos = $4 }
        $1 == "sharpe"                      { sh  = $2 }
        END { printf "%-6s %-12s %-12s %-12s %-12s %-12s %s\n", s, net, bm, ex, is, oos, sh }'
  )
done
