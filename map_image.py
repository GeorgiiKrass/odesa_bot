import os
import requests

def generate_static_map(locations):
    api_key = os.environ["GOOGLE_MAPS_API_KEY"]
    base_url = "https://maps.googleapis.com/maps/api/staticmap?"

    # Створюємо мітки (наприклад: "color:red|label:1|46.4825,30.7233")
    markers = [f"color:red|label:{i+1}|{lat},{lng}" for i, (lat, lng) in enumerate(locations)]
    marker_str = "&".join([f"markers={m}" for m in markers])

    # Центруємо на першій точці
    center = f"{locations[0][0]},{locations[0][1]}"

    params = (
        f"center={center}&zoom=14&size=600x400&maptype=roadmap&{marker_str}&key={api_key}"
    )
    full_url = base_url + params

    # Завантажуємо зображення
    response = requests.get(full_url)
    if response.status_code == 200:
        with open("map.png", "wb") as f:
            f.write(response.content)
        return "map.png"
    else:
        print("❌ Не вдалося завантажити мапу")
        return None
