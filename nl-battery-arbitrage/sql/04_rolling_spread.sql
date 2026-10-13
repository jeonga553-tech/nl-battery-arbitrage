-- 30-day rolling average of the daily spread, using a window function.
-- Smooths out day-to-day noise so the trend is visible.

SELECT
    day,
    spread,
    AVG(spread) OVER (
        ORDER BY day
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) AS spread_30d_avg
FROM daily
ORDER BY day;
