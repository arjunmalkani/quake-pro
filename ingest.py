import json
import os
import requests
import duckdb

con = duckdb.connect(database='data/earthquake_data.duckdb', read_only=False)

# call api and write to json file
def ingest_data():
    url = os.environ.get(
        "USGS_FEED",
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/1.0_hour.geojson"
    )

    try:
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching data: {e}")
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error: {e}")
    except requests.exceptions.Timeout as e:
        print(f"Request timed out: {e}")

# extract json data and write to duckdb
def extract_json(json_path):
    with open(json_path, "r") as json_file:
        data = json.load(json_file)

    rows = []
    for feature in data["features"]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]
        rows.append((
            feature["id"],
            props["mag"],
            props["place"],
            props["time"],
            coords[0],  # longitude
            coords[1],  # latitude
        ))
    return rows

def write_to_duckdb(rows):
    con.execute("""
        CREATE TABLE IF NOT EXISTS earthquakes (
            id VARCHAR PRIMARY KEY,
            magnitude FLOAT,
            place VARCHAR,
            time BIGINT,
            longitude FLOAT,
            latitude FLOAT
        )
    """)
    con.executemany("""
        INSERT OR IGNORE INTO earthquakes VALUES (?, ?, ?, ?, ?, ?)
    """, rows)
    print(f"Inserted {len(rows)} rows (duplicates skipped)")


if __name__ == "__main__":
    api_data = ingest_data()
    if api_data:
        with open("data/raw/earthquake_data.json", "w") as json_file:
            json.dump(api_data, json_file, indent=4)
        print("Data ingested and saved to earthquake_data.json")    
        rows = extract_json("data/raw/earthquake_data.json")
        write_to_duckdb(rows)
    