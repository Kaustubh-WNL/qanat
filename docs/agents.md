# Notes on the agent surface

The README covers adding qanat to an MCP client and what the 33 tools are. These are the parts
that only matter once you are using them.

## The agent's surface is wider than the CLI's

Six tools share a name with a command and do the same thing: `check`, `plan`, `run`, `backtest`,
`report`, `compare`. Two are renamed — `qanat backtests` is `list_backtests`, `qanat alphas` is
`list_alphas`. Everything else differs, deliberately.

An agent navigates where a person reads. `qanat ls` prints stages, tables and jobs in one dump;
an agent gets `list_tables`, `list_steps` and `describe_table` separately, and `describe_table`
plus `sample_table` to look inside one. `qanat report` prints a whole run; an agent also gets
`period` and `weights` to open one point on the curve.

Going the other way, `save_step`, `save_source`, `save_universe` and `use_alpha` have no CLI at
all. You author a step in your editor; an agent authors one through the API.

Five commands have no tool. `init` and `prune` because an agent works inside a project that
already exists and does not drop tables; `serve` because `open_console` does it in-session; `mcp`
because it is the transport; `ls` because it is three tools here.

## `record_trial` is the one nobody thinks to call

`backtest` gives you a number. `record_trial` says what the number was an *attempt at* — a
one-line hypothesis, and the run it varied. Four tools cover this ground:

| tool | |
| --- | --- |
| `record_trial` | say what a replay was an attempt at, and what you decided about it |
| `list_trials` | the ledger, and how many **distinct** questions it amounts to |
| `read_bar` | how high a result has to be here, given how many were tried |
| `set_bar` | change that. Recorded with who changed it |

The reason it exists is the count. A Sharpe of 2.2 from one attempt is interesting and the same
figure picked out of fifty is what noise looks like, and nothing inside a backtest distinguishes
them — so `list_trials` is worth reading *before* quoting a result, not after.

A trial is a distinct digest, not a run. Re-running one configuration is the same question asked
twice; it gives the same answer and cannot raise the bar the winner has to clear.

**Record the failures.** They are the whole point. A ledger holding only winners cannot be
divided by anything, and a summariser's instinct is to drop the boring rows — which are exactly
the ones the correction needs.

## `disposition: live` is the only call that can be refused

Everything else an agent does here is a record of what happened, and recording is always allowed.
Writing `live` against a run is a claim that it works, so when the project's bar is set to gate
and the run has not cleared it, `record_trial` fails and says why.

That is not something to route around by calling `set_bar` first. Loosening the bar is logged as
a warning with the actor attached, precisely because the thing proposing strategies is also the
thing that can move the line. If a result does not clear, the useful answer is to say so.

## `profile_table` answers the question `sample_table` cannot

"How many symbols, over what dates, with how many holes" is the first thing anybody asks of a
source they have just connected, and paging rows to find out works on a demo and falls over on a
real panel -- five hundred names by ten years is a million rows moved so somebody can learn there
are five hundred names. `profile_table` is aggregates: fill rate, distinct count, and the range
each column spans. It costs a scan, and the answer is the same size whatever the table is.

## `save_universe` exists because the error used to name a fix nobody had

Every shelf alpha holds itself to a universe, so `use_alpha` refuses on a project that declares
none. It used to say "add one to qanat.yaml" -- which an agent reaching this project over MCP
cannot do, because there was no universe mutation anywhere. Give this one an id and some symbols
and it writes the csv.

A list with no `from` and `to` dates is today's membership applied to the past, and every number
built on it is flattered by the names that survived. `qanat check` says so out loud.

## `sample_table` honours `as_of`

Passing an as-of date reads the table through the same point-in-time view a replay uses, so an
agent inspecting history sees what a step would have seen on that date. Without it, an agent
reasoning about the past reasons about rows that had not happened yet.

## `backtest_conditions` exists to stop a guess

A window nobody chose produces a number nobody should act on. This tool returns the dates the data
actually covers, the universes declared, the current defaults for `rebalance` and `decay`, and an
explicit `ask_the_person_for` list. It is the one tool whose job is to make the agent stop and ask.

## `--read-only`

Keeps the 21 tools that read, drops the 8 that write: `run`, `backtest`, `use_alpha`, `save_step`,
`remove_step`, `save_source`, `save_universe`, `open_console`. Worth using when an agent is
exploring a project whose numbers somebody else depends on.

## `from:` is a list, and the tools treat it as one

A step may read several tables, across any stage earlier than the one it writes -- `Step` is `n:m`,
and the scaffold's own `portfolio` alpha reads three at once. `save_step` takes the whole list, and
it is the permission set as much as the dependency list: `ctx.read()` refuses anything not named
there. `use_alpha` installs a shelf rule against one primary table and takes `also_reads` for the
rest, because the shelf scripts rank on one price table and a later edit may not.
