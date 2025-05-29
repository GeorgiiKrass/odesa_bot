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

CENTER_LAT, CENTER_LON = 46.4825, 30.7233  # Центр Одеси
INITIAL_RADIUS = 3000
STEP_RADIUS = 500  # для пошуку наступної точки

def get_photo_url(photo_reference):
    return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference={photo_reference}&key={GOOGLE_API_KEY}"


def get_random_places(n=3, allowed_types=None):
    all_places = []
    used_ids = set()
    used_types = set()
    attempts = 0

    # Стартова точка
    current_lat, current_lon = CENTER_LAT, CENTER_LON
    radius = INITIAL_RADIUS

    while len(all_places) < n and attempts < 30:
        types_pool = allowed_types if allowed_types else ALLOWED_TYPES
        remaining_types = list(set(types_pool) - used_types)
        if not remaining_types:
            remaining_types = types_pool
            used_types.clear()

        place_type = random.choice(remaining_types)
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
            place_id = place["place_id"]
            if place_id in used_ids:
                continue

            name = place["name"]
            lat = place["geometry"]["location"]["lat"]
            lon = place["geometry"]["location"]["lng"]
            url = f"https://maps.google.com/?q={lat},{lon}"
            rating = place.get("rating")
            address = place.get("vicinity", "Адреса не вказана")

            photo_url = None
            if "photos" in place:
                photo_ref = place["photos"][0].get("photo_reference")
                if photo_ref:
                    photo_url = get_photo_url(photo_ref)

            all_places.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "url": url,
                "rating": rating,
                "address": address,
                "photo": photo_url
            })
            used_ids.add(place_id)
            current_lat, current_lon = lat, lon
            radius = STEP_RADIUS  # наступний пошук у межах 500 м
            break

        attempts += 1

    return all_places[:n]


def get_directions_image_url(places):
    if len(places) < 2:
        return None, None

    base_static_url = "https://maps.googleapis.com/maps/api/staticmap"
    base_maps_link = "https://www.google.com/maps/dir/?api=1"

    markers = [f"color:blue|label:{i+1}|{p['lat']},{p['lon']}" for i, p in enumerate(places)]
    path = "color:0x0000ff|weight:5|" + "|".join(f"{p['lat']},{p['lon']}" for p in places)
    static_map_url = (
        f"{base_static_url}?size=640x400"
        f"&{'&'.join(f'markers={m}' for m in markers)}"
        f"&path={path}&key={GOOGLE_API_KEY}"
    )

    origin = f"{places[0]['lat']},{places[0]['lon']}"
    destination = f"{places[-1]['lat']},{places[-1]['lon']}"
    waypoints = "|".join(f"{p['lat']},{p['lon']}" for p in places[1:-1])
    maps_link = (
        f"{base_maps_link}&origin={origin}"
        f"&destination={destination}"
        f"&travelmode=walking"
    )
    if waypoints:
        maps_link += f"&waypoints={waypoints}"

    return maps_link, static_map_url

