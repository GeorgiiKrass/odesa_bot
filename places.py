import random
import requests
import os

ALLOWED_TYPES = [
    "art_gallery", "museum", "park", "zoo", "water_park", "church", "synagogue",
    "library", "movie_theater", "opera_house", "concert_hall", "historical_landmark",
    "tourist_attraction", "plaza", "cultural_center", "event_venue", "botanical_garden",
    "stadium", "university", "market", "cafe", "restaurant", "coffee_shop", "bakery",
    "meal_takeaway", "amusement_park", "amphitheatre"
]

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CENTER_LAT, CENTER_LON = 46.4825, 30.7233  # Центр Одеси
RADIUS = 3000

def get_random_places(n=3):
    places = []
    used_ids = set()
    tries = 0

    while len(places) < n and tries < 20:
        place_type = random.choice(ALLOWED_TYPES)
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

            places.append({"name": name, "lat": lat, "lon": lon, "url": url})
            used_ids.add(place_id)

            if len(places) == n:
                break

        tries += 1

    return places
