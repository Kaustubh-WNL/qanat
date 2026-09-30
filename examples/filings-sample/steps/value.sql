-- features -> features. What the trailing profit is worth against today's price.
--
-- Two ages, and a name can be wrong in either direction.
--
-- `staleness_days` is the gap between the newest filing used and the price it is
-- divided by. A filing is quarterly and a price is daily, so this is almost never
-- zero, and it grows when a company stops filing.
--
-- `price_age_days` is the gap between this name's last price and the newest price
-- in the whole panel. A company still trading has 0 or 1. A delisted one has
-- however long ago it left, and its yield is a live-looking number struck on a
-- price that no longer exists. `max(date)` is read through the as-of view like
-- everything else, so during a replay "newest" means newest by then.
WITH panel AS (
    SELECT max(date) AS newest FROM normalized__prices
),
ranked AS (
    SELECT symbol, date, close,
           row_number() OVER (PARTITION BY symbol ORDER BY date DESC) AS back
    FROM normalized__prices
),
last_price AS (
    SELECT symbol, date, close FROM ranked WHERE back = 1
)
SELECT
    f.symbol,
    p.date                                            AS as_of,
    f.as_of                                           AS fundamentals_as_of,
    date_diff('day', f.as_of, p.date)                 AS staleness_days,
    date_diff('day', p.date, panel.newest)            AS price_age_days,
    f.newest_period,
    p.close,
    f.shares_out,
    p.close * f.shares_out                            AS market_cap,
    f.net_income_ttm,
    f.equity,
    f.net_income_ttm / (p.close * f.shares_out)       AS earnings_yield,
    f.equity / (p.close * f.shares_out)               AS book_to_market,
    f.restated_quarters
FROM features__fundamentals f
JOIN last_price p ON p.symbol = f.symbol
CROSS JOIN panel
WHERE p.close * f.shares_out > 0
