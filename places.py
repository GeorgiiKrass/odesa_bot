import json
import os
import random
from typing import Dict, List, Optional, Set

import requests

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
FEEDBACK_FILE = "place_feedback.json"

# Центр Одеси
CENTER_LAT = 46.482952
CENTER_LON = 30.712481

INITIAL_RADIUS = 700
MAX_RADIUS = 1000

# Базові типи для випадкових прогулянок
ALLOWED_TYPES = [
    "art_gallery", "museum", "park", "zoo", "church", "synagogue", "library",
    "movie_theater", "restaurant", "cafe", "tourist_attraction", "amusement_park",
    "aquarium", "book_store", "bowling_alley", "cemetery", "hindu_temple",
    "mosque", "night_club", "shopping_mall", "stadium", "university",
    "city_hall", "train_station", "subway_station", "light_rail_station",
    "fountain", "plaza", "sculpture", "historical_landmark", "campground"
]

HOTEL_TYPES = ["lodging"]
GASTRO_TYPES = ["restaurant", "cafe", "bar"]
HISTORICAL_TYPES = ["museum", "tourist_attraction", "church", "synagogue"]
SHOP_TYPES = ["store", "shopping_mall", "supermarket", "convenience_store", "liquor_store"]

BAD_GASTRO_WORDS = [
    "магазин", "shop", "store", "market", "маркет", "продукти", "продукты",
    "пиво", "beer", "алкоголь", "liquor", "wine shop", "mini market", "мінімаркет"
]
BAD_HOTEL_WORDS = [
    "котедж", "коттедж", "cottage", "village", "camp", "base", "база", "кемп",
    "villa", "вілла", "садиба"
]


def load_place_feedback() -> Dict:
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_place_feedback(place_id: Optional[str]) -> Dict:
    if not place_id:
        return {}
    data = load_place_feedback()
    return data.get(place_id, {})


def _top_vote(votes: Dict[str, int]) -> Optional[str]:
    if not votes:
        return None
    return max(votes.items(), key=lambda x: x[1])[0]


def get_place_decision(place_id: Optional[str]) -> Optional[str]:
    if not place_id:
        return None
    record = get_place_feedback(place_id)
    return _top_vote(record.get("votes", {}))


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
        "raw_types": item.get("types", []),
    }


def _contains_bad_word(name: str, words: List[str]) -> bool:
    low = (name or "").lower()
    return any(word in low for word in words)


def is_place_allowed(item: Dict, section: Optional[str] = None) -> bool:
    pid = item.get("place_id")
    decision = get_place_decision(pid)
    name = item.get("name", "")

    if decision in {"wrong", "closed"}:
        return False

    if section == "gastro":
        if decision in {"shop", "wrong", "closed"}:
            return False
        if _contains_bad_word(name, BAD_GASTRO_WORDS):
            return False
        if item.get("rating", 0) and item.get("rating", 0) < 4.0:
            return False
        if item.get("user_ratings_total", 0) < 15:
            return False

    if section == "hotels":
        if decision in {"cottage", "wrong", "closed"}:
            return False
        if _contains_bad_word(name, BAD_HOTEL_WORDS):
            return False
        if item.get("user_ratings_total", 0) < 5:
            return False

    if section == "history":
        if decision in {"wrong", "closed"}:
            return False

    if section == "shop":
        if decision in {"wrong", "closed"}:
            return False

    return True


def get_random_places(
    n: int = 3,
    allowed_types: Optional[List[str]] = None,
    start_lat: Optional[float] = None,
    start_lon: Optional[float] = None,
    excluded_ids: Optional[Set[str]] = None,
    section: Optional[str] = None,
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

    while len(all_places) < n and attempts < 50:
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
            if not is_place_allowed(item, section=section):
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
    section: Optional[str] = None,
) -> Optional[Dict]:
    if not GOOGLE_API_KEY:
        return None

    excluded_ids = excluded_ids or set()
    types_pool = allowed_types or ALLOWED_TYPES
    used_types = set()
    attempts = 0

    while attempts < 40:
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
            if not is_place_allowed(item, section=section):
                continue
            return _place_from_item(item)
    return None
