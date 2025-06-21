# places.py

import random
import requests
import os

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

ALLOWED_TYPES = [
    "art_gallery", "museum", "park", "zoo", "church", "synagogue", "library",
    "movie_theater", "restaurant", "cafe", "tourist_attraction", "amusement_park",
    "aquarium", "book_store", "bowling_alley", "cemetery", "hindu_temple",
    "mosque", "night_club", "shopping_mall", "stadium", "university",
    "city_hall", "train_station", "subway_station", "light_rail_station",
    "fountain", "plaza", "sculpture", "historical_landmark", "campground"
]

CENTER_LAT, CENTER_LON = 46.4825, 30.7233
INITIAL_RADIUS = 3000
STEP_RADIUS = 500

def get_photo_url(photo_reference: str) -> str:
    return (
        f"https://maps.googleapis.com/maps/api/place/photo?"
        f"maxwidth=800&photoreference={photo_reference}&key={GOOGLE_API_KEY}"
    )

def get_random_places(n: int = 3, allowed_types: list[str] | None = None) -> list[dict]:
    types_pool = allowed_types or ALLOWED_TYPES
    all_places, used_ids, used_types = [], set(), set()
    current_lat, current_lon, radius = CENTER_LAT, CENTER_LON, INITIAL_RADIUS
    attempts = 0

    while len(all_places) < n and attempts < 30:
        choices = list(set(types_pool) - used_types) or types_pool
        t = random.choice(choices)
        used_types.add(t)

        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={"location": f"{current_lat},{current_lon}", "radius": radius, "type": t, "key": GOOGLE_API_KEY}
        ).json()
        candidates = resp.get("results", [])
        random.shuffle(candidates)

        for item in candidates:
            pid = item["place_id"]
            if pid in used_ids:
                continue

            lat = item["geometry"]["location"]["lat"]
            lon = item["geometry"]["location"]["lng"]
            photo = None
            if item.get("photos"):
                photo_ref = item["photos"][0].get("photo_reference")
                photo = get_photo_url(photo_ref) if photo_ref else None

            all_places.append({
                "name": item["name"],
                "lat": lat, "lon": lon,
                "url": f"https://maps.google.com/?q={lat},{lon}",
                "rating": item.get("rating"),
                "address": item.get("vicinity", ""),
                "photo": photo
            })
            used_ids.add(pid)
            current_lat, current_lon = lat, lon
            radius = STEP_RADIUS
            break

        attempts += 1

    return all_places[:n]


def get_random_place_near(lat: float, lon: float, radius: int, allowed_types: list[str] | None = None) -> dict | None:
    """
    Возвращает одну случайную локацию из Google Places API в радиусе radius метров от точки (lat, lon).
    """
    types_pool = allowed_types or ALLOWED_TYPES
    used_types = set()
    attempts = 0

    while attempts < 30:
        choices = list(set(types_pool) - used_types) or types_pool
        t = random.choice(choices)
        used_types.add(t)

        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={"location": f"{lat},{lon}", "radius": radius, "type": t, "key": GOOGLE_API_KEY}
        ).json()
        candidates = resp.get("results", [])
        random.shuffle(candidates)

        for item in candidates:
            plat = item["geometry"]["location"]["lat"]
            plon = item["geometry"]["location"]["lng"]
            photo = None
            if item.get("photos"):
                photo_ref = item["photos"][0].get("photo_reference")
                photo = get_photo_url(photo_ref) if photo_ref else None

            return {
                "name": item["name"],
                "lat": plat,
                "lon": plon,
                "url": f"https://maps.google.com/?q={plat},{plon}",
                "rating": item.get("rating"),
                "address": item.get("vicinity", ""),
                "photo": photo
            }

        attempts += 1

    return None
