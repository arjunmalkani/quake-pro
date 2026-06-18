CREATE OR REPLACE TABLE cleaned_earthquakes AS
    SELECT
        id,
        magnitude,
        place,
        epoch_ms(time) AS time,
        longitude,
        latitude,
        CASE
            WHEN place LIKE '%, %' THEN split_part(place, ', ', 2)
            ELSE place
        END AS region
    FROM earthquakes