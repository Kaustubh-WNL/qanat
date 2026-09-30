-- raw -> normalized. Both dates typed, and the two things a filing table hides
-- made into columns you can see.
--
-- `lag_days` is how long the market waited for this number. It is 35 to 100 days
-- here and it is not the same for every company, which is why a pipeline cannot
-- assume a fixed lag and shift the quarter by a constant.
--
-- `is_amendment` marks a filing that restates a quarter already reported. Both
-- rows stay. Which one you were allowed to know depends on the day you ask, and
-- that is the as-of view's job, not this step's.
--
-- So this table is **one row per filing event, not one row per quarter**. A reader
-- that sums `net_income` over it double counts every restated quarter. Deduping is
-- the first thing `fundamentals.sql` does, and anything else reading this table has
-- to do it too.
SELECT
    symbol,
    CAST(period_end AS DATE)                              AS period_end,
    CAST(filed_at AS DATE)                                AS filed_at,
    form,
    form LIKE '%/A'                                       AS is_amendment,
    date_diff('day', CAST(period_end AS DATE), CAST(filed_at AS DATE)) AS lag_days,
    revenue,
    net_income,
    equity,
    assets,
    shares_out
FROM raw__filings
WHERE net_income IS NOT NULL
  AND shares_out IS NOT NULL
  AND shares_out > 0
