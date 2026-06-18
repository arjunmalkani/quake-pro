CREATE OR REPLACE TABLE regional_activity AS
    SELECT 
        region,
        COUNT(*) AS total_earthquakes,
        AVG(magnitude) AS average_magnitude
    FROM cleaned_earthquakes
    GROUP BY region
    ORDER BY total_earthquakes DESC;