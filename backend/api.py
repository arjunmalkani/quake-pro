from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import duckdb
import numpy as np
import groq
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
claude = groq.Groq(api_key=os.environ["GROQ_API_KEY"])

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "../data/earthquake_data.duckdb"


def fit_gutenberg_richter(magnitudes):
    threshold_counts = {1.0: 0, 2.0: 0, 3.0: 0, 4.0: 0, 5.0: 0}
    for m in magnitudes:
        for t in threshold_counts:
            if m >= t:
                threshold_counts[t] += 1
    valid = {t: c for t, c in threshold_counts.items() if c > 0}
    if len(valid) < 2:
        return None, None
    thresholds = np.array(list(valid.keys()))
    log_counts = [np.log10(c) for c in valid.values()]
    b, a = np.polyfit(thresholds, log_counts, 1)
    return a, -b


def forecast_probability(a, b, magnitude_threshold, days):
    N = 10 ** (a - b * magnitude_threshold) * days
    return float(1 - np.exp(-N))


SYSTEM_PROMPT = """You are a seismology assistant embedded in QuakePro, a real-time earthquake analytics dashboard.
You help users understand how the data and forecasts are calculated. Be concise and clear.

Key methods used in this app:
- Data source: USGS GeoJSON feed (hourly), stored in DuckDB
- Deduplication: PRIMARY KEY on earthquake id with INSERT OR IGNORE
- Region extraction: parsed from USGS place strings (e.g. "10km NE of City, Region")
- Gutenberg-Richter law: log10(N) = a - b*M, fit via linear regression on exceedance counts at M1–M5 thresholds
- Poisson probability: P = 1 - e^(-N), where N = 10^(a - b*M) * days
- Forecasts are computed live per user-selected threshold and time window
- Regions with fewer than 20 earthquakes are excluded from forecasting

Answer questions about these methods, what the numbers mean, and how to interpret the map and forecasts.
Keep answers under 150 words unless the user asks for more detail."""


class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
def chat(req: ChatRequest):
    def generate():
        stream = claude.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=300,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": req.message},
            ],
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    return StreamingResponse(generate(), media_type="text/plain")


@app.get("/earthquakes")
def get_earthquakes(min_magnitude: float = Query(default=1.0)):
    con = duckdb.connect(DB_PATH, read_only=True)
    rows = con.execute("""
        SELECT id, magnitude, place, time, longitude, latitude
        FROM cleaned_earthquakes
        WHERE magnitude >= ?
        ORDER BY time DESC
        LIMIT 1000
    """, [min_magnitude]).fetchall()
    con.close()
    return [
        {"id": r[0], "magnitude": round(r[1], 2), "place": r[2], "time": str(r[3]), "longitude": r[4], "latitude": r[5]}
        for r in rows
    ]


@app.get("/region-centroids")
def get_region_centroids():
    con = duckdb.connect(DB_PATH, read_only=True)
    rows = con.execute("""
        SELECT region, AVG(latitude) AS lat, AVG(longitude) AS lng
        FROM cleaned_earthquakes
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY region
    """).fetchall()
    con.close()
    return {r[0]: {"lat": r[1], "lng": r[2]} for r in rows}


@app.get("/forecasts")
def get_forecasts(threshold: float = Query(default=5.0), days: int = Query(default=30)):
    con = duckdb.connect(DB_PATH, read_only=True)
    regions = con.execute("SELECT region FROM regional_activity").fetchall()

    results = []
    for (region,) in regions:
        rows = con.execute("""
            SELECT magnitude FROM cleaned_earthquakes
            WHERE region = ? AND magnitude IS NOT NULL
        """, [region]).fetchall()
        magnitudes = [r[0] for r in rows]

        if len(magnitudes) < 20:
            continue

        a, b = fit_gutenberg_richter(magnitudes)
        if a is None:
            continue

        prob = forecast_probability(a, b, threshold, days)
        results.append({"region": region, "probability": prob})

    con.close()
    results.sort(key=lambda x: x["probability"], reverse=True)
    return results


app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
