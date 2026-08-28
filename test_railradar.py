import requests
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

load_dotenv()
api_key = os.getenv("RAILRADAR_API_KEY")

train_number = "19484"

url = f"https://api.railradar.in/v1/trains/{train_number}/live"
params = {"includeCoordinates": "true",
          "haltsOnly": "true", "authoritative": "true"}
headers = {"Authorization": f"Bearer {api_key}"}

response = requests.get(url, headers=headers, params=params)
data = response.json()

MIN_SAFE_SPEED_KMPH = 5.0
MAX_WEATHER_LOOKUPS = 10


def get_hourly_arrays(lat, lon, date_str):
    weather_url = "https://api.open-meteo.com/v1/forecast"
    w_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,precipitation",
        "timezone": "Asia/Kolkata",
    }
    w_response = requests.get(weather_url, params=w_params, timeout=10)
    w_response.raise_for_status()
    w_data = w_response.json()
    hourly = w_data.get("hourly", {})
    return hourly.get("time", []), hourly.get("temperature_2m", []), hourly.get("precipitation", [])


def get_temp_rainfall_at_time(lat, lon, target_dt):
    try:
        date_str = target_dt.strftime("%Y-%m-%d")
        hours, temps, rains = get_hourly_arrays(lat, lon, date_str)
        if not hours:
            return None, None
        target_label = target_dt.strftime("%Y-%m-%dT%H:00")
        if target_label in hours:
            idx = hours.index(target_label)
        else:
            idx = min(range(len(hours)), key=lambda i: abs(
                int(hours[i].split("T")[1].split(":")[0]) - target_dt.hour))
        return temps[idx], rains[idx]
    except Exception:
        return None, None


def weather_factor_from_rainfall(rain_mm):
    if rain_mm is None or rain_mm == 0:
        return 1.0
    elif rain_mm <= 2.5:
        return 0.9
    elif rain_mm <= 7.5:
        return 0.8
    else:
        return 0.65


def expected_dwell_min(station):
    if station.get("isHalt"):
        if station.get("actualArrival") and station.get("actualDeparture"):
            t1 = datetime.fromisoformat(station["actualArrival"])
            t2 = datetime.fromisoformat(station["actualDeparture"])
            return max((t2 - t1).total_seconds() / 60, 0)
        return 2.0
    return 0.0


def predict_arrivals(route, start_time, start_delay_min):
    results = []
    current_time = start_time + timedelta(minutes=start_delay_min)

    for i in range(len(route) - 1):
        station_a = route[i]
        station_b = route[i + 1]

        distance_km = station_b["distance"] - station_a["distance"]
        speed_limit = station_a.get("speedToNextStationKmph", 60)

        temp, rain = (None, None)
        if i < MAX_WEATHER_LOOKUPS and station_b.get("lat") and station_b.get("lng"):
            temp, rain = get_temp_rainfall_at_time(
                station_b["lat"], station_b["lng"], current_time)

        weather_factor = weather_factor_from_rainfall(rain)
        effective_speed = max(
            speed_limit * weather_factor, MIN_SAFE_SPEED_KMPH)
        travel_time_min = (distance_km / effective_speed) * 60

        current_time += timedelta(minutes=travel_time_min)
        dwell = expected_dwell_min(station_b)
        current_time += timedelta(minutes=dwell)

        results.append({
            "station": station_b["stationName"],
            "predicted_arrival": current_time.strftime("%H:%M"),
            "temp_c": temp,
            "rain_mm": rain,
            "dwell_min": round(dwell, 1)
        })

    return results


if data.get("success"):
    d = data["data"]
    print(f"Train: {d['trainName']} | Category: {d['train']['category']}")
    print(
        f"Current status: {d['status']} | Current delay: {d['delayMinutes']} min")

    route = d["route"]
    predictions = predict_arrivals(route, datetime.now(), d["delayMinutes"])

    print("\nPredicted arrivals:")
    for p in predictions:
        weather_str = f"{p['temp_c']}°C, {p['rain_mm']}mm rain" if p['temp_c'] is not None else "not checked"
        print(
            f"  {p['station']}: {p['predicted_arrival']} | weather: {weather_str} | dwell: {p['dwell_min']} min")
else:
    print(f"Error: {data.get('error')}")
