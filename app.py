import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()
RAILRADAR_API_KEY = os.getenv("RAILRADAR_API_KEY")

app = Flask(__name__)
CORS(app)

MAX_WEATHER_LOOKUPS = 999


def get_hourly_arrays(lat, lon, date_str):
    weather_url = "https://api.open-meteo.com/v1/forecast"
    w_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,precipitation",
        "timezone": "Asia/Kolkata",
        "past_days": 92
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


def predict_arrivals(route):
    results = []
    accumulated_weather_delay = 0.0
    now = datetime.now()

    current_station_found = False

    origin_date = now.date()
    if len(route) > 0:
        origin_str = route[0].get(
            "scheduledDeparture") or route[0].get("scheduledArrival")
        if origin_str:
            origin_date = datetime.fromisoformat(
                origin_str).replace(tzinfo=None).date()

    for i in range(1, len(route)):
        station_prev = route[i - 1]
        station_curr = route[i]

        sch_arr_str = station_curr.get("scheduledArrival")
        sch_dep_str = station_curr.get("scheduledDeparture")
        act_arr_str = station_curr.get("actualArrival")
        act_dep_str = station_curr.get("actualDeparture")

        if not sch_arr_str:
            continue

        sch_arr_dt = datetime.fromisoformat(sch_arr_str).replace(tzinfo=None)
        sch_dep_dt = datetime.fromisoformat(sch_dep_str).replace(
            tzinfo=None) if sch_dep_str else sch_arr_dt

        base_act_arr_dt = datetime.fromisoformat(act_arr_str).replace(
            tzinfo=None) if act_arr_str else sch_arr_dt
        base_act_dep_dt = datetime.fromisoformat(act_dep_str).replace(
            tzinfo=None) if act_dep_str else base_act_arr_dt

        temp, rain = (None, None)
        if i < MAX_WEATHER_LOOKUPS and station_curr.get("lat") and station_curr.get("lng"):
            temp, rain = get_temp_rainfall_at_time(
                station_curr["lat"], station_curr["lng"], base_act_arr_dt)

        is_covered = base_act_arr_dt < now

        if is_covered:
            final_act_arr_dt = base_act_arr_dt
            final_act_dep_dt = base_act_dep_dt
        else:
            weather_factor = weather_factor_from_rainfall(rain)
            if weather_factor < 1.0:
                prev_dep_str = station_prev.get(
                    "scheduledDeparture") or station_prev.get("scheduledArrival")
                if prev_dep_str:
                    prev_dep_dt = datetime.fromisoformat(
                        prev_dep_str).replace(tzinfo=None)
                    scheduled_segment_min = (
                        sch_arr_dt - prev_dep_dt).total_seconds() / 60.0

                    if scheduled_segment_min > 0:
                        dynamic_segment_min = scheduled_segment_min / weather_factor
                        accumulated_weather_delay += (
                            dynamic_segment_min - scheduled_segment_min)

            final_act_arr_dt = base_act_arr_dt + \
                timedelta(minutes=accumulated_weather_delay)
            final_act_dep_dt = base_act_dep_dt + \
                timedelta(minutes=accumulated_weather_delay)

        delay_arr = (final_act_arr_dt - sch_arr_dt).total_seconds() / 60
        delay_dep = (final_act_dep_dt - sch_dep_dt).total_seconds() / 60
        dwell = max(
            (final_act_dep_dt - final_act_arr_dt).total_seconds() / 60, 0)

        is_current = False
        if not current_station_found and final_act_dep_dt > now:
            is_current = True
            current_station_found = True

        exp_day_arr = (sch_arr_dt.date() - origin_date).days + 1
        exp_day_dep = (sch_dep_dt.date() - origin_date).days + 1
        act_day_arr = (final_act_arr_dt.date() - origin_date).days + 1
        act_day_dep = (final_act_dep_dt.date() - origin_date).days + 1

        results.append({
            "station": station_curr.get("stationName", "Unknown"),
            "expected_arrival": sch_arr_dt.strftime("%H:%M"),
            "expected_departure": sch_dep_dt.strftime("%H:%M") if sch_dep_str else "--:--",
            "actual_arrival": final_act_arr_dt.strftime("%H:%M"),
            "actual_departure": final_act_dep_dt.strftime("%H:%M") if act_dep_str or sch_dep_str else "--:--",
            "exp_day_arr": exp_day_arr,
            "exp_day_dep": exp_day_dep,
            "act_day_arr": act_day_arr,
            "act_day_dep": act_day_dep,
            "delay_arr_min": round(delay_arr),
            "delay_dep_min": round(delay_dep),
            "temp_c": temp,
            "rain_mm": rain,
            "dwell_min": round(dwell, 1),
            "is_current": is_current
        })

    return results


@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    train_number = request.args.get('train_number')
    journey_date = request.args.get('date')

    if not train_number:
        return jsonify({"error": "Please provide a train number"}), 400

    try:
        url = f"https://api.railradar.in/v1/trains/{train_number}/live"
        params = {
            "includeCoordinates": "true",
            "haltsOnly": "true",
            "authoritative": "true"
        }
        if journey_date:
            params["date"] = journey_date

        headers = {"Authorization": f"Bearer {RAILRADAR_API_KEY}"}

        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        if not data.get("success"):
            return jsonify({"error": data.get("error", "Failed to fetch train data")}), 404

        d = data["data"]
        route = d.get("route", [])

        source_stn = route[0].get("stationName", "Origin") if len(
            route) > 0 else "Origin"
        dest_stn = route[-1].get("stationName",
                                 "Destination") if len(route) > 0 else "Destination"

        response_data = {
            "trainName": d.get("trainName", "Unknown Train"),
            "category": d.get("train", {}).get("category", "EXPRESS"),
            "sourceStation": source_stn,
            "destinationStation": dest_stn,
            "startDate": d.get("startDate"),
            "computedAt": datetime.now().strftime("%d %b %Y, %H:%M:%S IST"),
            "currentDelay": d.get("delayMinutes", 0),
            "predictions": predict_arrivals(route)
        }
        return jsonify(response_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
