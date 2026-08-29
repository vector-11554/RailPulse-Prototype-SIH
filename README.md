# RailPulse — Dynamic ETA Forecast for Coaching Trains

**Smart India Hackathon 2026 — Problem Statement 28**
*Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains*

RailPulse is a working prototype that recomputes a train's expected arrival at
each upcoming station using **live running status**, **real-time weather
conditions**, and **actual historical timestamps from the same journey** —
instead of relying only on the static timetable and current delay, the way
most existing ETA displays do.

> ⚠️ **Prototype status:** This is an early-stage build submitted for the SIH
> internal round. It demonstrates a working end-to-end pipeline on real data
> sources, with several simplifications documented under [Known
> Limitations](#known-limitations) and a clear [Roadmap](#roadmap) for the
> full SIH round.

---

## The Problem

Indian Railways currently estimates ETA using static schedules, current
delay, and built-in recovery time. This doesn't reflect real-world factors
like weather-related slowdowns, segment-by-segment running speed, or how a
train's pace is actually trending during its journey — leading to inaccurate
predictions for passengers, station staff, and downstream logistics.

## Our Approach

Instead of a single static delay number, RailPulse recalculates ETA
station-by-station along the route, combining:

- **Live position & delay** — pulled from real-time train tracking, refreshed
  on demand (not a cached/stale schedule lookup).
- **Real weather along the route** — actual temperature and rainfall (mm) at
  each upcoming station, at the predicted time of arrival, used to apply a
  physically-grounded slowdown factor (heavier rainfall → lower effective
  speed).
- **Real dwell time** — station halt duration computed from actual
  arrival/departure timestamps where the train has already passed, with a
  reasonable default for stations still ahead.
- **Segment-level speed comparison** — effective running speed derived from
  real consecutive-station timestamps, compared against the scheduled
  sectional speed, to catch segments where the train is falling behind pace.

## Features Implemented

| Feature | Status |
|---|---|
| Live delay & running status | ✅ Working |
| Real weather-based speed adjustment (temperature + rainfall) | ✅ Working |
| Real dwell-time calculation from actual timestamps | ✅ Working |
| Segment-by-segment speed factor from real timestamps | ✅ Working |
| Multi-day journey day-offset display (Day 1 / Day 2 / Day 3) | ✅ Working |
| Web dashboard (train number input → live forecast table) | ✅ Working |
| Historical-pattern probability meter | 🔜 Roadmap (see below) |
| Congestion / train-priority hierarchy | 🔜 Roadmap (see below) |

## Tech Stack

- **Backend:** Python, Flask, Flask-CORS
- **Live train data:** [RailRadar API](https://railradar.in) (live running
  status, schedule, route geometry)
- **Weather data:** [Open-Meteo API](https://open-meteo.com) (hourly
  temperature + precipitation, no API key required)
- **Frontend:** Plain HTML/CSS/JS dashboard

## Setup

### 1. Clone and install dependencies

```bash
git clone <this-repo-url>
cd railpulse
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install flask flask-cors requests python-dotenv
```

### 2. Add API keys

Create a `.env` file in the project root:

```
RAILRADAR_API_KEY=your_railradar_key_here
```

Get a free RailRadar sandbox key at
[railradar.in/developers](https://railradar.in/developers) (free tier: 1,000
requests/month). No key is needed for the Open-Meteo weather calls.

### 3. Run the backend

```bash
python3 app.py
```

This starts the Flask API on `http://localhost:5000`.

### 4. Open the frontend

Open `index.html` in a browser (or serve it with any static file server),
enter a 5-digit train number, and click **Compute**.

## API Reference (internal)

`GET /api/forecast?train_number=<number>&date=<YYYY-MM-DD>`

| Param | Required | Description |
|---|---|---|
| `train_number` | Yes | 5-digit Indian Railways train number |
| `date` | No | Exact journey start date. See [Known Limitations](#known-limitations) — recommended for multi-day trains |

Returns train name, category, source/destination, current delay, and a
station-by-station list of scheduled vs. dynamically predicted arrival and
departure times, temperature, rainfall, and dwell time.

## Known Limitations

- **Multi-day journey date ambiguity:** RailRadar's live endpoint
  auto-detects which day's departure instance is "currently running" when no
  `date` is passed. For long-duration trains still mid-journey from an
  earlier start date, this can occasionally resolve to the wrong instance.
  Passing the `date` parameter explicitly avoids this; a date-picker in the
  frontend is planned to make this seamless for end users.
- **No public live signal/block-occupancy data exists** for Indian Railways,
  so congestion is not modeled from real signaling data in this prototype.
- **Live GPS-derived speed (`speedKmh`)** is intermittently available
  depending on crowd-sourced telemetry coverage; we derive effective speed
  from real consecutive-station timestamps instead, which is consistently
  available.
- **No historical delay archive** is publicly available for Indian Railways
  trains, so a true statistical delay-probability model isn't yet feasible —
  see Roadmap.

## Roadmap (Post-Selection / Full SIH Round)

- **Historical delay probability meter:** build a proper historical dataset
  by polling live status over time, then train a lightweight statistical or
  ML model to output a genuine "likelihood of delay" estimate per train/route,
  replacing today's real-time-only calculation.
- **Congestion modeling:** incorporate a train-category priority hierarchy
  (e.g. Rajdhani/Vande Bharat > Superfast > Express > Passenger) as a proxy
  for block-section congestion, refined with mentor/domain-expert input.
- **Date picker in UI** for explicit journey-date selection.
- **Multi-train dashboard** instead of single train lookup.
- **Public API layer** for integration with station displays and mobile
  apps, as envisioned in the original problem statement.

## Team

Built by a first-year team at IIT Dharwad for Smart India Hackathon 2026.
Lead - Aditya Biradar - ce26bt001@iitdh.ac.in
Members - Varenya Maheshwari - ep26bt002@iitdh.ac.in
          Jyotsna - cs26bt048@iitdh.ac.in
          Tijil Sharma - cs26bt006@iitdh.ac.in
          Hrushikesh Rao - ce26bt007@iitdh.ac.in
          Saumay Jaiswal - ee26bt018@iitdh.ac.in
