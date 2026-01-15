from serpapi import GoogleSearch
import os
import csv
import json
import time
from pathlib import Path
from dateutil.parser import parse
from geopy.geocoders import Nominatim
from googletrans import Translator

# =====================================================
# CONFIGURATION
# =====================================================

API_KEY = os.getenv("SERPAPI_API_KEY")
if not API_KEY:
    raise ValueError(" SERPAPI_API_KEY non définie")

# MODE TEST : True = arrêt après 1 événement
TEST_MODE = False

MAX_EVENTS_PER_QUERY = 5
TYPES_PER_CITY = 12

OUTPUT_CSV = "data/csv_fusionne.csv"
GEO_CACHE_FILE = "geo_cache.json"

# =====================================================
# DATA
# =====================================================

villes = [
    {"name": "Berlin", "location": "Berlin, Germany", "gl": "de", "hl": "de"},
    {"name": "Paris", "location": "Paris, France", "gl": "fr", "hl": "fr"},
    {"name": "Rome", "location": "Rome, Italy", "gl": "it", "hl": "it"},
    {"name": "Madrid", "location": "Madrid, Spain", "gl": "es", "hl": "es"},
    {"name": "Amsterdam", "location": "Amsterdam, Netherlands", "gl": "nl", "hl": "nl"},
    {"name": "Bruxelles", "location": "Brussels, Belgium", "gl": "be", "hl": "fr"},
    {"name": "Vienne", "location": "Vienna, Austria", "gl": "at", "hl": "de"},
    {"name": "Zurich", "location": "Zurich, Switzerland", "gl": "ch", "hl": "de"},
    {"name": "Genève", "location": "Geneva, Switzerland", "gl": "ch", "hl": "fr"},
    {"name": "Barcelone", "location": "Barcelona, Spain", "gl": "es", "hl": "es"},
    {"name": "Lisbonne", "location": "Lisbon, Portugal", "gl": "pt", "hl": "pt"},
    {"name": "Stockholm", "location": "Stockholm, Sweden", "gl": "se", "hl": "sv"},
    {"name": "Copenhague", "location": "Copenhagen, Denmark", "gl": "dk", "hl": "da"},
    {"name": "Oslo", "location": "Oslo, Norway", "gl": "no", "hl": "no"},
    {"name": "Dublin", "location": "Dublin, Ireland", "gl": "ie", "hl": "en"},
]

event_types_by_lang = {
    "fr": ["concerts","expositions","marchés","festivals","théâtre","opéra",
           "comédies musicales","foires","brocantes","salons professionnels",
           "spectacles de danse","marchés de Noël"],
    "en": ["concerts","exhibitions","markets","festivals","theater","opera",
           "musicals","fairs","flea markets","trade shows","dance shows","Christmas markets"],
    "de": ["konzerte","ausstellungen","märkte","festivals","theater","oper",
           "musicals","messen","flohmärkte","fachmessen","tanzshows","weihnachtsmärkte"],
    "it": ["concerti","mostre","mercati","festival","teatro","opera",
           "musical","fiere","mercatini","fiere professionali","danza","mercatini di Natale"],
    "es": ["conciertos","exposiciones","mercados","festivales","teatro","ópera",
           "musicales","ferias","mercadillos","ferias profesionales","danza","mercados de Navidad"],
    "nl": ["concerten","tentoonstellingen","markten","festivals","theater","opera",
           "musicals","beurzen","vlooienmarkten","vakbeurzen","dans","kerstmarkten"],
    "pt": ["concertos","exposições","mercados","festivais","teatro","ópera",
           "musicais","feiras","mercados","feiras profissionais","dança","mercados de Natal"],
    "sv": ["konserter","utställningar","marknader","festivaler","teater","opera",
           "musikaler","mässor","loppmarknader","fackmässor","dans","julmarknader"],
    "da": ["koncerter","udstillinger","markeder","festivaler","teater","opera",
           "musicals","messer","loppemarkeder","fagmesser","dans","julemarkeder"],
    "no": ["konserter","utstillinger","markeder","festivaler","teater","opera",
           "musikaler","messer","loppemarkeder","fagmesser","dans","julemarkeder"],
}

# =====================================================
# TOOLS INITIALIZATION
# =====================================================

translator = Translator()
geolocator = Nominatim(user_agent="event_scraper")

try:
    with open(GEO_CACHE_FILE, "r", encoding="utf-8") as f:
        geo_cache = json.load(f)
except FileNotFoundError:
    geo_cache = {}

def save_geo_cache():
    with open(GEO_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(geo_cache, f, ensure_ascii=False, indent=2)

def translate_fr(text):
    if not text:
        return ""
    try:
        return translator.translate(text, src="auto", dest="fr").text
    except:
        return text

def geolocate(address):
    if not address:
        return None, None
    if address in geo_cache:
        return geo_cache[address]
    try:
        loc = geolocator.geocode(address)
        if loc:
            geo_cache[address] = (loc.latitude, loc.longitude)
            save_geo_cache()
            return geo_cache[address]
    except:
        pass
    geo_cache[address] = (None, None)
    save_geo_cache()
    return None, None

def parse_date_range(date_str):
    if not date_str:
        return None, None, None
    try:
        parts = date_str.split("–")
        start = parse(parts[0], fuzzy=True)
        end = parse(parts[1], fuzzy=True) if len(parts) > 1 else None
        duration = (end - start).total_seconds() / 3600 if end else None
        return start, end, duration
    except:
        return None, None, None

# =====================================================
# LOADING EXISTING DUPLICATES
# =====================================================

existing_keys = set()

csv_path = Path(OUTPUT_CSV)
if csv_path.exists():
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (
                row.get("EventName", "").strip().lower(),
                row.get("City", "").strip().lower(),
                row.get("DateTime_start", "")
            )
            existing_keys.add(key)

# =====================================================
# WRITING (APPEND)
# =====================================================

os.makedirs("data", exist_ok=True)
file_exists = csv_path.exists()

with open(csv_path, "a", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)

    if not file_exists:
        writer.writerow([
            "Source","Category","EventName","DateTime","City","VenueName","Address","Link",
            "Description","DateTime_start","DateTime_end","Jour_start","Mois_start",
            "Annee_start","Heure_start","Heure_end","lat","lon","duration_h","tags"
        ])

    for ville in villes:
        types = event_types_by_lang.get(ville["hl"], [])[:TYPES_PER_CITY]

        for event_type in types:
            print(f" {event_type} — {ville['name']}")

            params = {
                "engine": "google_events",
                "api_key": API_KEY,
                "q": f"{event_type} in {ville['name']}",
                "location": ville["location"],
                "gl": ville["gl"],
                "hl": ville["hl"]
            }

            search = GoogleSearch(params)
            results = search.get_dict()
            events = results.get("events_results", [])[:MAX_EVENTS_PER_QUERY]

            for ev in events:
                title = translate_fr(ev.get("title", "")).strip()
                date_raw = ev.get("date", {}).get("when", "")
                city = ville["name"]

                dt_start, dt_end, duration = parse_date_range(date_raw)

                key = (
                    title.lower(),
                    city.lower(),
                    dt_start.isoformat() if dt_start else ""
                )

                if key in existing_keys:
                    continue

                desc = translate_fr(ev.get("description", ""))
                venue = translate_fr(", ".join(ev.get("address", [])))
                link = ev.get("link", "")
                lat, lon = geolocate(venue)
                time.sleep(1)

                writer.writerow([
                    "SerpApi", event_type, title, date_raw, city,
                    venue, venue, link, desc,
                    dt_start.isoformat() if dt_start else "",
                    dt_end.isoformat() if dt_end else "",
                    dt_start.day if dt_start else "",
                    dt_start.month if dt_start else "",
                    dt_start.year if dt_start else "",
                    dt_start.hour if dt_start else "",
                    dt_end.hour if dt_end else "",
                    lat, lon, round(duration, 2) if duration else "", event_type
                ])

                existing_keys.add(key)

                if TEST_MODE:
                    print(" TEST MODE — arrêt après 1 événement")
                    break

            if TEST_MODE:
                break
        if TEST_MODE:
            break

print(f" Scraping terminé — données ajoutées à {OUTPUT_CSV}")

