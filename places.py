import os
import random
from typing import List, Dict, Optional, Tuple, Set
import requests

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Центр Одеси
CENTER_LAT = 46.482952
CENTER_LON = 30.712481

INITIAL_RADIUS = 700
MAX_RADIUS = 700

# Базові типи для рандомних прогулянок
ALLOWED_TYPES = [
    "art_gallery", "museum", "park", "zoo", "church", "synagogue", "library",
    "movie_theater", "restaurant", "cafe", "tourist_attraction", "amusement_park",
    "aquarium", "book_store", "bowling_alley", "cemetery", "hindu_temple",
    "mosque", "night_club", "shopping_mall", "stadium", "university",
    "city_hall", "train_station", "subway_station", "light_rail_station",
    "fountain", "plaza", "sculpture", "historical_landmark", "campground"
]

# Нові тематичні типи
HOTEL_TYPES = ["lodging"]
GASTRO_TYPES = ["restaurant", "cafe", "bar", "bakery"]

def get_photo_url(photo_reference: str, maxwidth: int = 800) -> str:
    if not GOOGLE_API_KEY or not photo_reference:
        return ""
    return (
        "https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth={maxwidth}&photoreference={photo_reference}&key={GOOGLE_API_KEY}"
    )

def _place_from_item(item: Dict) -> Dict:
    plat = item["geometry"]["location"]["lat"]
    plon = item["geometry"]["location"]["lng"]

    photo = None
    if item.get("photos"):
        photo_ref = item["photos"][0].get("photo_reference")
        if photo_ref:
            photo = get_photo_url(photo_ref)

    return {
        "name": item.get("name", "Без назви"),
        "lat": plat,
        "lon": plon,
        "url": f"https://maps.google.com/?q={plat},{plon}",
        "rating": item.get("rating"),
        "reviews": item.get("user_ratings_total", 0),
        "address": item.get("vicinity", "") or item.get("formatted_address", ""),
        "photo": photo,
        "place_id": item.get("place_id"),
    }

def get_random_places(
    n: int = 3,
    allowed_types: Optional[List[str]] = None,
    start_lat: Optional[float] = None,
    start_lon: Optional[float] = None,
    excluded_ids: Optional[Set[str]] = None,
) -> List[Dict]:
    if not GOOGLE_API_KEY:
        return []

    excluded_ids = excluded_ids or set()
    types_pool = allowed_types or ALLOWED_TYPES
    all_places: List[Dict] = []
    used_ids = set()
    used_types = set()

    base_lat = start_lat if start_lat is not None else CENTER_LAT
    base_lon = start_lon if start_lon is not None else CENTER_LON

    current_lat, current_lon, radius = base_lat, base_lon, INITIAL_RADIUS
    attempts = 0

    while len(all_places) < n and attempts < 40:
        attempts += 1
        choices = list(set(types_pool) - used_types) or types_pool
        t = random.choice(choices)
        used_types.add(t)

        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={
                "location": f"{current_lat},{current_lon}",
                "radius": radius,
                "type": t,
                "key": GOOGLE_API_KEY,
            },
            timeout=10,
        ).json()

        candidates = resp.get("results", [])
        random.shuffle(candidates)

        picked = False
        for item in candidates:
            pid = item.get("place_id")
            if not pid or pid in used_ids or pid in excluded_ids:
                continue
            if item.get("user_ratings_total", 0) <= 0:
                continue

            place = _place_from_item(item)
            all_places.append(place)
            used_ids.add(pid)
            current_lat, current_lon = place["lat"], place["lon"]
            picked = True
            break

        if not picked and radius < MAX_RADIUS:
            radius = min(radius + 100, MAX_RADIUS)

    return all_places[:n]

def get_random_place_near(
    lat: float,
    lon: float,
    radius: int = 700,
    allowed_types: Optional[List[str]] = None,
    excluded_ids: Optional[Set[str]] = None,
) -> Optional[Dict]:
    if not GOOGLE_API_KEY:
        return None

    excluded_ids = excluded_ids or set()
    types_pool = allowed_types or ALLOWED_TYPES
    used_types = set()
    attempts = 0

    while attempts < 30:
        attempts += 1
        choices = list(set(types_pool) - used_types) or types_pool
        t = random.choice(choices)
        used_types.add(t)

        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={
                "location": f"{lat},{lon}",
                "radius": radius,
                "type": t,
                "key": GOOGLE_API_KEY,
            },
            timeout=10,
        ).json()

        candidates = resp.get("results", [])
        random.shuffle(candidates)

        for item in candidates:
            pid = item.get("place_id")
            if not pid or pid in excluded_ids:
                continue
            if item.get("user_ratings_total", 0) <= 0:
                continue
            return _place_from_item(item)
    return None

def get_directions_image_url(places: List[Dict]) -> Tuple[Optional[str], Optional[str]]:
    if not places:
        return None, None

    origin = f"{places[0]['lat']},{places[0]['lon']}"
    
    if len(places) == 1:
        maps_link = f"https://www.google.com/maps/search/?api=1&query={origin}"
        static_url = f"https://maps.googleapis.com/maps/api/staticmap?center={origin}&zoom=15&size=640x400&markers={origin}&key={GOOGLE_API_KEY}" if GOOGLE_API_KEY else None
        return maps_link, static_url

    dest = f"{places[-1]['lat']},{places[-1]['lon']}"
    wayp = "|".join(f"{p['lat']},{p['lon']}" for p in places[1:-1])
    
    maps_link = f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={dest}&travelmode=walking"
    if wayp: maps_link += f"&waypoints={wayp}"

    if not GOOGLE_API_KEY:
        return maps_link, None

    markers = [f"size:mid|label:{i+1}|{p['lat']},{p['lon']}" for i, p in enumerate(places)]
    path = "color:0x0000ff|weight:4|" + "|".join(f"{p['lat']},{p['lon']}" for p in places)
    static_url = f"https://maps.googleapis.com/maps/api/staticmap?size=640x400&" + "&".join(f"markers={m}" for m in markers) + f"&path={path}&key={GOOGLE_API_KEY}"

    return maps_link, static_url
