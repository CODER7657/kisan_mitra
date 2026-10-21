"""Three-day forecast from Open-Meteo (free, no key), so spraying and irrigation advice
can account for rain. Returns None on any failure; the answer then says no forecast
was available."""

import httpx

URL = "https://api.open-meteo.com/v1/forecast"


def forecast(lat: float, lon: float, timeout: float = 6.0) -> dict | None:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    params = {
        "latitude": round(lat, 3), "longitude": round(lon, 3), "timezone": "auto", "forecast_days": 3,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "precipitation_probability_max,wind_speed_10m_max",
    }
    try:
        r = httpx.get(URL, params=params, timeout=timeout)
        r.raise_for_status()
        d = r.json()["daily"]
    except Exception:
        return None
    days = [
        {"date": d["time"][i], "max_c": d["temperature_2m_max"][i], "min_c": d["temperature_2m_min"][i],
         "rain_mm": d["precipitation_sum"][i], "rain_chance_pct": d["precipitation_probability_max"][i],
         "wind_kmh": d["wind_speed_10m_max"][i]}
        for i in range(len(d["time"]))
    ]
    return {"source": "Open-Meteo forecast", "days": days}
