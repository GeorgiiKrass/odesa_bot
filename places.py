import random
import requests
import os

ALLOWED_TYPES = [
    "art_gallery", "museum", "park", "zoo", "church", "synagogue",
    "library", "movie_theater", "restaurant", "cafe", "tourist_attraction"
]

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CENTER_LAT, CENTER_LON = 46.4825, 30.7233  # Центр Одеси
RADIUS = 3000

def get_random_places(n=3):
    all_places = []
    used_ids = set()
    attempts = 0

    while len(all_places) < n and attempts < 20:
        place_type = random.choice(ALLOWED_TYPES)
        print(f"[DEBUG] Used API key: {os.getenv('GOOGLE_API_KEY')}")
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={
                "location": f"{CENTER_LAT},{CENTER_LON}",
                "radius": RADIUS,
                "type": place_type,
                "key": GOOGLE_API_KEY
            }
        )
        data = response.json()

        print(f"👉 type: {place_type}, status: {data.get('status')}, results: {len(data.get('results', []))}")

        candidates = data.get("results", [])
        random.shuffle(candidates)

        for place in candidates:
            place_id = place["place_id"]
            if place_id in used_ids:
                continue

            name = place["name"]
            lat = place["geometry"]["location"]["lat"]
            lon = place["geometry"]["location"]["lng"]
            url = f"https://maps.google.com/?q={lat},{lon}"

            all_places.append({"name": name, "lat": lat, "lon": lon, "url": url})
            used_ids.add(place_id)

            if len(all_places) >= n:
                break

        attempts += 1

    print(f"🔍 Зібрано унікальних локацій: {len(all_places)}")
    for p in all_places:
        print(p["name"], p["lat"], p["lon"])

    return all_places[:n]
