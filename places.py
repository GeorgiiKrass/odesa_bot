import random
import requests
import os
import time

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CENTER_LAT, CENTER_LON = 46.4825, 30.7233  # Центр Одеси
START_RADIUS = 3000
NEXT_RADIUS = 500

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

def search_places(lat, lon, radius, used_ids, used_types):
    types_pool = list(set(ALLOWED_TYPES) - used_types)
    if not types_pool:
        types_pool = ALLOWED_TYPES
        used_types.clear()

    place_type = random.choice(types_pool)
    used_types.add(place_type)

    response = requests.get(
        "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
        params={
            "location": f"{lat},{lon}",
            "radius": radius,
            "type": place_type,
            "key": GOOGLE_API_KEY
        }
    )
    data = response.json()

    print(f"👉 type: {place_type}, status: {data.get('status')}, results: {len(data.get('results', []))}")

    results = []
    for place in data.get("results", []):
        if place["place_id"] in used_ids:
            continue

        name = place["name"]
        lat = place["geometry"]["location"]["lat"]
        lon = place["geometry"]["location"]["lng"]
        url = f"https://maps.google.com/?q={lat},{lon}"
        rating = place.get("rating")
        address = place.get("vicinity", "Адреса не вказана")
        reviews = place.get("user_ratings_total", 0)

        photo_url = None
        if "photos" in place:
            photo_ref = place["photos"][0].get("photo_reference")
            if photo_ref:
                photo_url = get_photo_url(photo_ref)

        results.append({
            "id": place["place_id"],
            "name": name,
            "lat": lat,
            "lon": lon,
            "url": url,
            "rating": rating,
            "reviews": reviews,
            "address": address,
            "photo": photo_url
        })

    return results

def get_random_places(n=3):
    places = []
    used_ids = set()
    used_types = set()
    
    current_lat, current_lon = CENTER_LAT, CENTER_LON
    radius = START_RADIUS

    while len(places) < n:
        candidates = search_places(current_lat, current_lon, radius, used_ids, used_types)
        random.shuffle(candidates)

        for place in candidates:
            if place["id"] not in used_ids:
                places.append(place)
                used_ids.add(place["id"])
                current_lat, current_lon = place["lat"], place["lon"]
                radius = NEXT_RADIUS  # уменьшить радиус для следующей точки
                break

        if len(places) < n:
            time.sleep(0.3)  # пауза перед следующим запросом

    print(f"🔍 Зібрано унікальних локацій: {len(places)}")
    return places
