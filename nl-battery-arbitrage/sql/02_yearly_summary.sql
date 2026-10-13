-- Year-by-year summary: is the market getting more volatile?
-- More negative-price hours and wider spreads mean more value for storage.

SELECT
    YEAR(day)                              AS year,
    COUNT(*)                               AS days,
    ROUND(AVG(avg_price), 1)               AS avg_price,
    ROUND(AVG(spread), 1)                  AS avg_daily_spread,
    ROUND(MEDIAN(spread), 1)               AS median_daily_spread,
    SUM(negative_hours)                    AS negative_hours,
    ROUND(MIN(min_price), 1)               AS lowest_price
FROM daily
GROUP BY 1
ORDER BY 1;
