import random
import requests
import os

ALLOWED_TYPES = [
    "art_gallery", "museum", "park", "zoo", "church", "synagogue", "library",
    "movie_theater", "restaurant", "cafe", "tourist_attraction", "amusement_park",
    "aquarium", "book_store", "bowling_alley", "cemetery", "hindu_temple",
    "mosque", "night_club", "shopping_mall", "stadium", "university",
    "city_hall", "train_station", "subway_station", "light_rail_station",
    "fountain", "plaza", "sculpture", "historical_landmark", "campground"
]

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CENTER_LAT, CENTER_LON = 46.4825, 30.7233
RADIUS = 3000

def get_random_places(n=3):
    all_places = []
    used_ids = set()
    used_types = set()
    attempts = 0

    while len(all_places) < n and attempts < 50:
        available_types = list(set(ALLOWED_TYPES) - used_types)
        if not available_types:
            available_types = ALLOWED_TYPES
        place_type = random.choice(available_types)
        used_types.add(place_type)

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

            photo_url = None
            if "photos" in place:
                photo_ref = place["photos"][0]["photo_reference"]
                photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference={photo_ref}&key={GOOGLE_API_KEY}"

            address = place.get("vicinity", "Адреса не вказана")
            rating = place.get("rating")
            user_ratings_total = place.get("user_ratings_total")

            all_places.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "url": url,
                "photo_url": photo_url,
                "address": address,
                "rating": rating,
                "user_ratings_total": user_ratings_total
            })
            used_ids.add(place_id)

            if len(all_places) >= n:
                break

        attempts += 1

    return all_places[:n]
