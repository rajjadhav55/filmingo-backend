"""
Quick standalone test for OMDb connectivity and imdb_id extraction.
Run from: c:\Users\asus\bookmyshow\bookmyshow\
  python test_omdb.py
"""
import os
import sys
import requests

# Load .env manually (no Django needed)
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
env = {}
try:
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
except Exception as e:
    print(f"Could not read .env: {e}")

TMDB_KEY = env.get('TMDB_API_KEY', '')
OMDB_KEY = env.get('OMDB_API_KEY', '')
MOVIE_ID = '1122512'   # change to any TMDB movie ID you know

print(f"TMDB_KEY present: {bool(TMDB_KEY)}")
print(f"OMDB_KEY present: {bool(OMDB_KEY)} ({OMDB_KEY})")
print()

# 1. TMDB external_ids
print(f"=== Step 1: TMDB external_ids for movie {MOVIE_ID} ===")
try:
    url = f"https://api.themoviedb.org/3/movie/{MOVIE_ID}"
    params = {"api_key": TMDB_KEY, "append_to_response": "external_ids"}
    r = requests.get(url, params=params, timeout=8)
    r.raise_for_status()
    data = r.json()
    imdb_id = (data.get('external_ids') or {}).get('imdb_id') or data.get('imdb_id')
    print(f"  Movie title : {data.get('title')}")
    print(f"  imdb_id     : {imdb_id}")
    print(f"  external_ids: {data.get('external_ids')}")
except Exception as e:
    print(f"  TMDB error: {e}")
    imdb_id = None

print()

# 2. OMDb call
print(f"=== Step 2: OMDb for {imdb_id} ===")
if imdb_id and OMDB_KEY:
    try:
        r = requests.get(
            'https://www.omdbapi.com/',
            params={'apikey': OMDB_KEY, 'i': imdb_id},
            timeout=8
        )
        r.raise_for_status()
        data = r.json()
        print(f"  Response   : {data.get('Response')}")
        print(f"  Error      : {data.get('Error')}")
        print(f"  Ratings    : {data.get('Ratings')}")
        print(f"  Full resp  : {data}")
    except Exception as e:
        print(f"  OMDb error: {e}")
else:
    print(f"  Skipped (imdb_id={imdb_id}, key={OMDB_KEY})")
