import random
import requests
import os

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Типи локацій для випадкових маршрутів
ALLOWED_TYPES = [
    "art_gallery", "museum", "park", "zoo", "church", "synagogue", "library",
    "movie_theater", "restaurant", "cafe", "tourist_attraction", "amusement_park",
    "aquarium", "book_store", "bowling_alley", "cemetery", "hindu_temple",
    "mosque", "night_club", "shopping_mall", "stadium", "university",
    "city_hall", "train_station", "subway_station", "light_rail_station",
    "fountain", "plaza", "sculpture", "historical_landmark", "campground"
]

# Центр Одеси для старту пошуку
CENTER_LAT, CENTER_LON = 46.4825, 30.7233
# Початковий та крок радіусів (у метрах)
INITIAL_RADIUS = 3000
STEP_RADIUS = 500


def get_photo_url(photo_reference: str) -> str:
    """
    Формує URL для завантаження фото через Google Places API.
    """
    return (
        f"https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth=800&photoreference={photo_reference}&key={GOOGLE_API_KEY}"
    )


def get_random_places(n: int = 3, allowed_types: list[str] | None = None) -> list[dict]:
    """
    Повертає n випадкових місць навколо центру Одеси.
    Якщо передано allowed_types, обмежує випадковий вибір цими типами.
    """
    all_places = []
    used_ids = set()
    used_types = set()
    attempts = 0

    current_lat, current_lon = CENTER_LAT, CENTER_LON
    radius = INITIAL_RADIUS
    types_pool = allowed_types if allowed_types is not None else ALLOWED_TYPES

    while len(all_places) < n and attempts < 30:
        remaining = list(set(types_pool) - used_types) or types_pool
        place_type = random.choice(remaining)
        used_types.add(place_type)

        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={
                "location": f"{current_lat},{current_lon}",
                "radius": radius,
                "type": place_type,
                "key": GOOGLE_API_KEY
            }
        )
        data = response.json()
        candidates = data.get("results", [])
        random.shuffle(candidates)

        for place in candidates:
            pid = place["place_id"]
            if pid in used_ids:
                continue

            lat = place["geometry"]["location"]["lat"]
            lon = place["geometry"]["location"]["lng"]
            url = f"https://maps.google.com/?q={lat},{lon}"
            name = place.get("name")
            address = place.get("vicinity", "Адреса не вказана")
            rating = place.get("rating")

            photo_url = None
            photos = place.get("photos")
            if photos:
                ref = photos[0].get("photo_reference")
                if ref:
                    photo_url = get_photo_url(ref)

            all_places.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "url": url,
                "address": address,
                "rating": rating,
                "photo": photo_url
            })
            used_ids.add(pid)
            # переміщуємо центр для наступного пошуку
            current_lat, current_lon = lat, lon
            radius = STEP_RADIUS
            break

        attempts += 1

    return all_places[:n]


def get_directions_image_url(places: list[dict]) -> tuple[str | None, str | None]:
    """
    Формує URL для статичної карти з маршрутом та посилання на Google Maps.
    """
    if len(places) < 2:
        return None, None

    base_static = "https://maps.googleapis.com/maps/api/staticmap"
    base_maps = "https://www.google.com/maps/dir/?api=1"

    markers = [f"color:blue|label:{i+1}|{p['lat']},{p['lon']}" for i,p in enumerate(places)]
    path = "color:0x0000ff|weight:5|" + "|".join(f"{p['lat']},{p['lon']}" for p in places)

    static_url = (
        f"{base_static}?size=640x400&"
        + "&".join(f"markers={m}" for m in markers)
        + f"&path={path}&key={GOOGLE_API_KEY}"
    )

    origin = f"{places[0]['lat']},{places[0]['lon']}"
    destination = f"{places[-1]['lat']},{places[-1]['lon']}"
    waypoints = "|".join(f"{p['lat']},{p['lon']}" for p in places[1:-1])

    maps_link = (
        f"{base_maps}&origin={origin}&destination={destination}&travelmode=walking"
        + (f"&waypoints={waypoints}" if waypoints else "")
    )

    return maps_link, static_url


