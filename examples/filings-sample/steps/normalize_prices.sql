-- raw -> normalized. Type the date, and drop the rows that are not a price.
--
-- A company that has not listed yet, or has already delisted, has no row here on
-- that day rather than a zero. A zero would be a price, and it would be wrong.
SELECT
    CAST(date AS DATE) AS date,
    symbol,
    close
FROM raw__prices
WHERE close IS NOT NULL AND close > 0
