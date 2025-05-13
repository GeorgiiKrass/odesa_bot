import random
import requests
import os

ALLOWED_TYPES = [
    "art_gallery", "museum", "park", "zoo", "church", "synagogue", "library",
    "movie_theater", "restaurant", "cafe", "tourist_attraction", "amusement_park",
    "aquarium", "book_store", "bowling_alley", "cemetery", "hindu_temple",
    "mosque", "night_club", "shopping_mall", "stadium", "university",
    "city_hall", "train_station", "subway_station", "fountain", "plaza",
    "sculpture", "historical_landmark", "campground"
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
    random.shuffle(ALLOWED_TYPES)

    for place_type in ALLOWED_TYPES:
        if len(all_places) >= n:
            break
        if place_type in used_types:
            continue

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

        print(f"👉 type: {place_type}, status: {data.get('status')}, results: {len(data.get('results', []))}")

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
            used_types.add(place_type)
            break  # беремо тільки одну локацію з кожного типу

    print(f"🔍 Зібрано унікальних локацій: {len(all_places)}")
    return all_places[:n]
