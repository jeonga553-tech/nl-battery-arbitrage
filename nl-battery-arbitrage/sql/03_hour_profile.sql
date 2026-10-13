-- Average price by hour of day and season.
-- Shows the "solar duck curve": cheap midday hours in summer,
-- expensive evening peak. This is the pattern a battery trades on.

SELECT
    HOUR(ts) AS hour,
    ROUND(AVG(CASE WHEN MONTH(ts) IN (4, 5, 6, 7, 8, 9) THEN price_eur_mwh END), 1)   AS summer_avg,
    ROUND(AVG(CASE WHEN MONTH(ts) IN (10, 11, 12, 1, 2, 3) THEN price_eur_mwh END), 1) AS winter_avg
FROM prices
GROUP BY 1
ORDER BY 1;
