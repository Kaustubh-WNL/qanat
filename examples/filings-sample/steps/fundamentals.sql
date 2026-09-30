-- normalized -> features. Trailing twelve month profit per company, built only
-- from filings that had been published.
--
-- Two passes, and each one answers a different question.
--
-- `latest` asks: for this quarter, what is the newest thing said about it? An
-- amendment has a later `filed_at` than the original, so it wins here -- but only
-- once the replay has reached the day it was filed. Before that day the original
-- is the newest thing said, and that is the number the market had.
--
-- `known` then takes the four most recent quarters. `HAVING count(*) = 4` drops a
-- company that has not reported four times yet, instead of summing three quarters
-- and calling it a year.
WITH latest AS (
    SELECT
        symbol, period_end, filed_at, net_income, equity, shares_out, is_amendment,
        row_number() OVER (
            PARTITION BY symbol, period_end ORDER BY filed_at DESC
        ) AS rn
    FROM normalized__filings
),
known AS (
    SELECT
        symbol, period_end, filed_at, net_income, equity, shares_out, is_amendment,
        row_number() OVER (PARTITION BY symbol ORDER BY period_end DESC) AS back
    FROM latest
    WHERE rn = 1
)
SELECT
    symbol,
    -- The day this twelve month figure became complete. It is the newest filing
    -- date among the four quarters, so it can never be after the day the step ran.
    max(filed_at)                                  AS as_of,
    max(period_end)                                AS newest_period,
    sum(net_income)                                AS net_income_ttm,
    sum(CASE WHEN is_amendment THEN 1 ELSE 0 END)  AS restated_quarters,
    arg_max(equity, period_end)                    AS equity,
    arg_max(shares_out, period_end)                AS shares_out
FROM known
WHERE back <= 4
GROUP BY symbol
HAVING count(*) = 4
