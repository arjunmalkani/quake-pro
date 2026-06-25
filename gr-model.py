import numpy as np
import duckdb
# gutenberg richter model function 

def fit_gutenberg_richter(magnitudes):
    # hard-coded thresholds for magnitudes
    threshold_counts = {1.0: 0, 2.0: 0, 3.0: 0, 4.0: 0, 5.0: 0}

    # Count the number of earthquakes above each threshold
    for m in magnitudes:
        for threshold in threshold_counts.keys():
            if m >= threshold:
                threshold_counts[threshold] += 1
    # populate valid dict with nonzero counts
    valid = {t: c for t, c in threshold_counts.items() if c > 0}
    thresholds = np.array(list(valid.keys()))
    if len(thresholds) < 2:
        print("Not enough data to fit Gutenberg-Richter model.")
        return None, None
    
    log_counts = [np.log10(c) for c in valid.values()]

    # find the best fit line using numpy's polyfit function
    b, a = np.polyfit(thresholds, log_counts, 1)
    return a, -b

def forecast_probability(a, b, magnitude_threshold, days):
    # expected number of earthquakes above the threshold in the given time period
    N = 10**(a - b * magnitude_threshold) * days
    # probability of at least one earthquake above the threshold in the given time period
    P = 1 - np.exp(-N)
    return P

if __name__ == "__main__":
    con = duckdb.connect('md:quake_pro')

    regions = con.execute("SELECT region FROM regional_activity").fetchall()

    con.execute("""
        CREATE TABLE IF NOT EXISTS forecasts (
            region VARCHAR,
            probability FLOAT,
            magnitude_threshold FLOAT,
            forecast_date TIMESTAMP,
            days INTEGER
        )
    """)


    for region in regions:
        # extract magnitudes for the region and unpack the list of tuples into a flat list
        magnitudes = con.execute("SELECT magnitude FROM cleaned_earthquakes WHERE region = ? AND magnitude IS NOT NULL", [region[0]]).fetchall()
        magnitudes = [row[0] for row in magnitudes]    

        if len(magnitudes) < 20:
            continue # Skip regions with insufficient data 

        a, b = fit_gutenberg_richter(magnitudes)
        if a is None:
            continue # Skip regions with insufficient data

        probability = forecast_probability(a, b, magnitude_threshold=5.0, days=30)

        con.execute("""
            INSERT INTO forecasts VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, [region[0], probability, 5.0, 30])
    

