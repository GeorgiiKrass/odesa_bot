import os
import random
import requests

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CENTER_LAT, CENTER_LON = 46.4825, 30.7233  # Центр Одеси
DEFAULT_RADIUS = 500

ALLOWED_TYPES = [
    "art_gallery", "museum", "park", "zoo", "church", "synagogue", "library",
    "movie_theater", "restaurant", "cafe", "tourist_attraction", "amusement_park",
    "aquarium", "book_store", "bowling_alley", "cemetery", "hindu_temple",
    "mosque", "night_club", "shopping_mall", "stadium", "university",
    "city_hall", "train_station", "fountain", "plaza", "sculpture",
    "historical_landmark"
]

def get_photo_url(photo_reference):
    return (
        f"https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth=800&photoreference={photo_reference}&key={GOOGLE_API_KEY}"
    )

def get_random_places(n=3):
    all_places = []
    used_ids = set()
    location = (CENTER_LAT, CENTER_LON)

    while len(all_places) < n:
        place_type = random.choice(ALLOWED_TYPES)

        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={
                "location": f"{location[0]},{location[1]}",
                "radius": DEFAULT_RADIUS,
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
            location = (lat, lon)  # наступна точка — це центр для наступного запиту
            break  # виходимо з внутрішнього циклу, шукаємо нову точку

    return all_places

def get_directions_image_url(places):
    if len(places) < 2:
        return None

    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    markers = []
    path = "color:0x0000ff|weight:5"

    for place in places:
        lat, lon = place["lat"], place["lon"]
        markers.append(f"markers=color:red|{lat},{lon}")
        path += f"|{lat},{lon}"

    params = "&".join(markers + [f"path={path}", "size=600x400", f"key={GOOGLE_API_KEY}"])
    return f"{base_url}?{params}"
