import random
import requests
import os

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

ALLOWED_TYPES = [
    "art_gallery","museum","park","zoo","church","synagogue","library",
    "movie_theater","restaurant","cafe","tourist_attraction","amusement_park",
    "aquarium","book_store","bowling_alley","cemetery","hindu_temple",
    "mosque","night_club","shopping_mall","stadium","university",
    "city_hall","train_station","subway_station","light_rail_station",
    "fountain","plaza","sculpture","historical_landmark","campground"
]

CENTER_LAT, CENTER_LON = 46.4825, 30.7233
INITIAL_RADIUS = 3000
STEP_RADIUS = 500

def get_photo_url(ref):
    return (
        "https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth=800&photoreference={ref}&key={GOOGLE_API_KEY}"
    )

def get_random_places(n=3, allowed_types=None):
    pool = allowed_types or ALLOWED_TYPES
    res = []
    used = set()
    types_used = set()
    lat, lon = CENTER_LAT, CENTER_LON
    radius = INITIAL_RADIUS
    tries = 0

    while len(res) < n and tries < 30:
        choices = list(set(pool) - types_used)
        if not choices:
            choices = pool
            types_used.clear()
        t = random.choice(choices)
        types_used.add(t)

        r = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={"location":f"{lat},{lon}", "radius":radius, "type":t, "key":GOOGLE_API_KEY}
        )
        items = r.json().get("results",[])
        random.shuffle(items)
        for p in items:
            pid = p["place_id"]
            if pid in used: continue
            used.add(pid)
            nm = p["name"]
            plat = p["geometry"]["location"]["lat"]
            plon = p["geometry"]["location"]["lng"]
            url = f"https://maps.google.com/?q={plat},{plon}"
            addr = p.get("vicinity","Адреса не вказана")
            rt = p.get("rating")
            ph = None
            if "photos" in p:
                pr = p["photos"][0].get("photo_reference")
                if pr: ph = get_photo_url(pr)
            res.append({"name":nm,"lat":plat,"lon":plon,"url":url,"address":addr,"rating":rt,"photo":ph})
            lat, lon = plat, plon
            radius = STEP_RADIUS
            break
        tries += 1

    return res[:n]

def get_directions_image_url(places):
    if len(places) < 2: return None, None
    base_static = "https://maps.googleapis.com/maps/api/staticmap"
    base_dir = "https://www.google.com/maps/dir/?api=1"
    marks = [f"color:blue|label:{i+1}|{p['lat']},{p['lon']}" for i,p in enumerate(places)]
    path = "color:0x0000ff|weight:5|" + "|".join(f"{p['lat']},{p['lon']}" for p in places)
    img_url = f"{base_static}?size=640x400&" + "&".join(f"markers={m}" for m in marks) + f"&path={path}&key={GOOGLE_API_KEY}"

    o = f"{places[0]['lat']},{places[0]['lon']}"
    d = f"{places[-1]['lat']},{places[-1]['lon']}"
    wps = "|".join(f"{p['lat']},{p['lon']}" for p in places[1:-1])
    map_url = f"{base_dir}&origin={o}&destination={d}&travelmode=walking"
    if wps: map_url += f"&waypoints={wps}"
    return map_url, img_url
