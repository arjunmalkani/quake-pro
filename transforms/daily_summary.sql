CREATE OR REPLACE TABLE daily_summary AS
    SELECT 
        DATE_TRUNC('day', time) AS day,
        COUNT(*) AS total_earthquakes,
        AVG(magnitude) AS average_magnitude
    FROM cleaned_earthquakes
    GROUP BY day
    ORDER BY day;