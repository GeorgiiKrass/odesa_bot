import random
import requests
import os

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CENTER_LAT, CENTER_LON = 46.4825, 30.7233  # Центр Одеси
RADIUS = 3000

ALLOWED_TYPES = [
    "art_gallery", "museum", "park", "zoo", "church", "synagogue", "library",
    "movie_theater", "restaurant", "cafe", "tourist_attraction", "amusement_park",
    "aquarium", "book_store", "bowling_alley", "cemetery", "hindu_temple",
    "mosque", "night_club", "shopping_mall", "stadium", "university",
    "city_hall", "train_station", "subway_station", "light_rail_station",
    "fountain", "plaza", "sculpture", "historical_landmark", "campground"
]

def get_photo_url(photo_reference):
    return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference={photo_reference}&key={GOOGLE_API_KEY}"

def get_random_places(n=3):
    all_places = []
    used_ids = set()
    used_types = set()
    attempts = 0

    lat, lon = CENTER_LAT, CENTER_LON

    while len(all_places) < n and attempts < 30:
        remaining_types = list(set(ALLOWED_TYPES) - used_types)
        if not remaining_types:
            remaining_types = ALLOWED_TYPES
            used_types.clear()

        place_type = random.choice(remaining_types)
        used_types.add(place_type)

        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={
                "location": f"{lat},{lon}",
                "radius": 500 if len(all_places) > 0 else RADIUS,
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
            break

        attempts += 1

    return all_places[:n]

def get_directions_image_url(places):
    if not places:
        return None, None

    base_directions_url = "https://www.google.com/maps/dir/"
    base_static_map_url = "https://maps.googleapis.com/maps/api/staticmap"

    # Створюємо шлях через координати локацій
    waypoints = [f"{p['lat']},{p['lon']}" for p in places]
    directions_link = base_directions_url + "/".join(waypoints)

    path = "|".join(waypoints)
    markers = "&".join([f"markers=label:{i+1}%7C{p['lat']},{p['lon']}" for i, p in enumerate(places)])

    static_map_url = (
        f"{base_static_map_url}?size=640x400&path=color:0x0000ff|weight:5|{path}&{markers}"
        f"&key={GOOGLE_API_KEY}"
    )

    return static_map_url, directions_link
