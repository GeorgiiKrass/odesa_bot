import os
import random
from typing import List, Dict, Optional, Tuple, Set

import requests

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Центр Одеси (базова точка для маршрутів, якщо не вказано інше)
CENTER_LAT = 46.482952
CENTER_LON = 30.712481

# Радіуси пошуку в метрах
# Жорстко обмежуємося 700 м між точками
INITIAL_RADIUS = 700
MAX_RADIUS = 700

# Типи закладів / місць, які можемо підбирати
ALLOWED_TYPES = [
    "art_gallery", "museum", "park", "zoo", "church", "synagogue", "library",
    "movie_theater", "restaurant", "cafe", "tourist_attraction", "amusement_park",
    "aquarium", "book_store", "bowling_alley", "cemetery", "hindu_temple",
    "mosque", "night_club", "shopping_mall", "stadium", "university",
    "city_hall", "train_station", "subway_station", "light_rail_station",
    "fountain", "plaza", "sculpture", "historical_landmark", "campground"
]


def get_photo_url(photo_reference: str, maxwidth: int = 800) -> str:
    """
    Формує URL для отримання фото з Google Places Photo API.
    """
    if not GOOGLE_API_KEY or not photo_reference:
        return ""
    return (
        "https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth={maxwidth}&photoreference={photo_reference}&key={GOOGLE_API_KEY}"
    )


def _place_from_item(item: Dict) -> Dict:
    """
    Витягує потрібну інформацію з елемента Google Places Nearby Search.
    """
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
        "place_id": item.get("place_id"),  # place_id для відгуків і унікальності
    }


def get_random_places(
    n: int = 3,
    allowed_types: Optional[List[str]] = None,
    start_lat: Optional[float] = None,
    start_lon: Optional[float] = None,
    excluded_ids: Optional[Set[str]] = None,
) -> List[Dict]:
    """
    Повертає список з n випадкових локацій.
    Якщо start_lat/start_lon задані — стартуємо від цих координат,
    інакше — від центру Одеси.

    Обмеження:
    - Радіус пошуку 700 м (INITIAL_RADIUS / MAX_RADIUS).
    - Беремо тільки місця, де є відгуки (user_ratings_total > 0).
    - Не повертаємо place_id, які в excluded_ids.
    """
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
            if not pid:
                continue

            # ⚠️ фільтр: не показуємо вже використані для цього юзера place_id
            if pid in used_ids or pid in excluded_ids:
                continue

            # ⚠️ фільтр: тільки місця з відгуками
            if item.get("user_ratings_total", 0) <= 0:
                continue

            place = _place_from_item(item)
            all_places.append(place)
            used_ids.add(pid)

            current_lat = place["lat"]
            current_lon = place["lon"]
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
    """
    Повертає одну випадкову локацію поблизу заданих координат.
    Використовується у «фірмовому маршруті».

    - Радіус за замовчуванням 700 м.
    - Беремо тільки місця з відгуками.
    - Не повертаємо place_id з excluded_ids.
    """
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
            if not pid:
                continue

            if pid in excluded_ids:
                continue

            if item.get("user_ratings_total", 0) <= 0:
                continue

            return _place_from_item(item)

    return None


def get_directions_image_url(places: List[Dict]) -> Tuple[Optional[str], Optional[str]]:
    """
    Генерує:
      • maps_link — посилання на маршрут у Google Maps
      • static_url — посилання на статичну картинку маршруту (Static Maps API)
    """
    if not places:
        return None, None

    if len(places) == 1:
        p = places[0]
        origin = f"{p['lat']},{p['lon']}"
        maps_link = f"https://www.google.com/maps/search/?api=1&query={origin}"

        if not GOOGLE_API_KEY:
            return maps_link, None

        static_url = (
            "https://maps.googleapis.com/maps/api/staticmap"
            f"?center={origin}&zoom=15&size=640x400"
            f"&markers={origin}&key={GOOGLE_API_KEY}"
        )
        return maps_link, static_url

    if not GOOGLE_API_KEY:
        origin = f"{places[0]['lat']},{places[0]['lon']}"
        dest = f"{places[-1]['lat']},{places[-1]['lon']}"
        wayp = "|".join(f"{p['lat']},{p['lon']}" for p in places[1:-1])
        maps_link = (
            "https://www.google.com/maps/dir/?api=1"
            f"&origin={origin}&destination={dest}&travelmode=walking"
        )
        if wayp:
            maps_link += f"&waypoints={wayp}"
        return maps_link, None

    base_static = "https://maps.googleapis.com/maps/api/staticmap"

    markers = [
        f"size:mid|label:{i+1}|{p['lat']},{p['lon']}"
        for i, p in enumerate(places)
    ]
    path = "color:0x0000ff|weight:4|" + "|".join(
        f"{p['lat']},{p['lon']}" for p in places
    )

    static_url = (
        f"{base_static}?size=640x400&"
        + "&".join(f"markers={m}" for m in markers)
        + f"&path={path}&key={GOOGLE_API_KEY}"
    )

    origin = f"{places[0]['lat']},{places[0]['lon']}"
    dest = f"{places[-1]['lat']},{places[-1]['lon']}"
    wayp = "|".join(f"{p['lat']},{p['lon']}" for p in places[1:-1])

    maps_link = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={origin}&destination={dest}&travelmode=walking"
    )
    if wayp:
        maps_link += f"&waypoints={wayp}"

    return maps_link, static_url
