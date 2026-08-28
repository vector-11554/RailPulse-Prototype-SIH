import requests


def get_hourly_arrays(lat: float, lon: float, date_str: str):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,precipitation",
        "timezone": "Asia/Kolkata",
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    hourly = data.get("hourly", {})

    hours = hourly.get("time", [])
    temperature_array = hourly.get("temperature_2m", [])
    rainfall_array = hourly.get("precipitation", [])

    return hours, temperature_array, rainfall_array


if __name__ == "__main__":
    print("Enter location and date:")
    lat = float(input("Latitude: "))
    lon = float(input("Longitude: "))
    date_str = input("Date (YYYY-MM-DD): ")

    hours, temperature_array, rainfall_array = get_hourly_arrays(
        lat, lon, date_str)

    if not hours:
        print("No data returned. Check your inputs.")
    else:
        print(f"\nTemperature array (°C): {temperature_array}")
        print(f"Rainfall array (mm):    {rainfall_array}")

        print("\nHourly Data:")
        for i in range(len(hours)):
            hour_label = hours[i].split("T")[1]
            print(
                f"{hour_label}  |  Temp: {temperature_array[i]}°C  |  Rain: {rainfall_array[i]} mm")
