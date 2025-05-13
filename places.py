import random
import requests
import os

ALLOWED_TYPES = [
    "art_gallery", "museum", "park", "zoo", "church", "synagogue", "library",
    "movie_theater", "restaurant", "cafe", "tourist_attraction"
]

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CENTER_LAT, CENTER_LON = 46.4825, 30.7233  # Центр Одеси
RADIUS = 3000

def get_photo_url(photo_reference):
    return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference={photo_reference}&key={GOOGLE_API_KEY}"

def get_random_places(n=3):
    all_places = []
    used_ids = set()
    used_types = set()
    attempts = 0

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

            name = place.get("name")
            lat = place["geometry"]["location"]["lat"]
            lon = place["geometry"]["location"]["lng"]
            url = f"https://maps.google.com/?q={lat},{lon}"
            rating = place.get("rating")
            address = place.get("vicinity", "Адреса не вказана")
            reviews = place.get("user_ratings_total", 0)

            photo_url = None
            if "photos" in place:
                ref = place["photos"][0].get("photo_reference")
                if ref:
                    photo_url = get_photo_url(ref)

            all_places.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "url": url,
                "rating": rating,
                "reviews": reviews,
                "address": address,
                "photo": photo_url
            })
            used_ids.add(place_id)

            if len(all_places) >= n:
                break

        attempts += 1

    return all_places[:n]
