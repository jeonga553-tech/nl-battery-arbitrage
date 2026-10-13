-- Daily price statistics for the Dutch day-ahead market.
-- The daily spread (max - min price) is the simplest measure of how much
-- a battery could earn by charging cheap and discharging expensive.

CREATE OR REPLACE TABLE daily AS
SELECT
    CAST(ts AS DATE)                                  AS day,
    COUNT(*)                                          AS hours,
    ROUND(AVG(price_eur_mwh), 2)                      AS avg_price,
    MIN(price_eur_mwh)                                AS min_price,
    MAX(price_eur_mwh)                                AS max_price,
    MAX(price_eur_mwh) - MIN(price_eur_mwh)           AS spread,
    SUM(CASE WHEN price_eur_mwh < 0 THEN 1 ELSE 0 END) AS negative_hours
FROM prices
GROUP BY 1
ORDER BY 1;
