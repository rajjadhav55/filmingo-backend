import requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Shared thread pool for non-blocking OMDb calls
_executor = ThreadPoolExecutor(max_workers=4)

def _fetch_omdb_ratings(imdb_id):
    """Fetches IMDb, RT, and Metacritic ratings from OMDb. Returns [] on any failure."""
    omdb_key = getattr(settings, 'OMDB_API_KEY', '')
    if not omdb_key or not imdb_id:
        return []

    def _call():
        resp = requests.get(
            'https://www.omdbapi.com/',
            params={'apikey': omdb_key, 'i': imdb_id},
            timeout=5,   # socket-level timeout
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get('Response') == 'False':
            print(f"OMDb: no entry for {imdb_id} — {data.get('Error')}")
            return []
        ratings = data.get('Ratings', [])
        print(f"OMDb ratings for {imdb_id}: {ratings}")
        return ratings

    try:
        future = _executor.submit(_call)
        return future.result(timeout=6)   # wall-clock deadline
    except FutureTimeout:
        print(f"OMDb timed out for {imdb_id}")
        return []
    except Exception as e:
        print(f"OMDb fetch failed for {imdb_id}: {e}")
        return []

def fetch_movie_details(movie_id):
    """
    Fetches details for a single movie by ID from TMDB.
    Also appends OMDb ratings (IMDb / RT / Metacritic) via the movie's IMDb ID.
    """
    api_key = settings.TMDB_API_KEY
    if not api_key:
        return None

    try:
        # TMDB movie detail + external IDs in one request
        url = f"https://api.themoviedb.org/3/movie/{movie_id}"
        params = {
            "api_key": api_key,
            "append_to_response": "credits,reviews,external_ids,watch/providers"
        }
        
        # Use session with retries for robustness against transient SSL/Network errors
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))

        response = session.get(url, params=params, timeout=10)
        
        is_tv = False
        try:
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                # Fallback: Maybe it's a TV show recommended by the AI?
                url = f"https://api.themoviedb.org/3/tv/{movie_id}"
                response = session.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                is_tv = True
            else:
                raise e
        
        full_poster_url = f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}" if data.get('poster_path') else None
        backdrop_url = f"https://image.tmdb.org/t/p/original{data.get('backdrop_path')}" if data.get('backdrop_path') else None
        
        genres = [g['name'] for g in data.get('genres', [])]
        languages = [l['english_name'] for l in data.get('spoken_languages', [])]

        # Get reviews count
        reviews_count = data.get('reviews', {}).get('total_results', 0)

        # OMDb ratings — fetched via IMDb ID returned in external_ids
        imdb_id = (data.get('external_ids') or {}).get('imdb_id') or data.get('imdb_id')
        omdb_ratings = _fetch_omdb_ratings(imdb_id)

        # Extract top 10 cast from credits (already fetched via append_to_response)
        raw_cast = data.get('credits', {}).get('cast', [])
        cast = []
        for member in raw_cast[:15]:
            profile = member.get('profile_path')
            cast.append({
                "id": member.get('id'),
                "name": member.get('name'),
                "character": member.get('character'),
                "profile_url": f"https://image.tmdb.org/t/p/w185{profile}" if profile else None,
            })

        # Extract streaming providers (flatrate) for India ('IN')
        watch_providers_data = data.get('watch/providers', {}).get('results', {}).get('IN', {})
        flatrate_providers = watch_providers_data.get('flatrate', [])
        streaming_platforms = []
        for p in flatrate_providers:
            streaming_platforms.append({
                "name": p.get('provider_name'),
                "logo_url": f"https://image.tmdb.org/t/p/w92{p.get('logo_path')}" if p.get('logo_path') else None
            })

        # Handle differences between Movie and TV JSON keys
        title = data.get('title') or data.get('name')
        release_date = data.get('release_date') or data.get('first_air_date')
        
        # TV shows don't have a single 'runtime', they have 'episode_run_time' (array of ints)
        duration_min = data.get('runtime')
        if not duration_min and is_tv:
            episodic_runtimes = data.get('episode_run_time', [])
            duration_min = episodic_runtimes[0] if episodic_runtimes else 0

        return {
            "id": data.get('id'),
            "title": title,
            "description": data.get('overview'),
            "image": full_poster_url,
            "backdrop": backdrop_url,
            "avg_rating": data.get('vote_average'),
            "reviews_count": reviews_count,
            "release_date": release_date,
            "duration_min": duration_min,
            "genres": genres,
            "language": languages,
            "censor_rating": "UA",
            "imdb_id": imdb_id,
            "omdb_ratings": omdb_ratings,   # [{Source, Value}, ...]
            "cast": cast,                   # top 10 cast members
            "streaming_platforms": streaming_platforms,
            "is_tv": is_tv
        }
    except requests.RequestException as e:
        print(f"Error fetching detail {movie_id}: {e}")
        return None
