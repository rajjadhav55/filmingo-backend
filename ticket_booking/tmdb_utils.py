import requests
from datetime import date, timedelta
from django.conf import settings

TMDB_IMG_BASE = "https://image.tmdb.org/t/p/w500"

def _fetch_discover(api_key, language, date_gte, date_lte, limit, sort_by="popularity.desc"):
    """Helper: calls /discover/movie for a single language and returns formatted list."""
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": api_key,
        "region": "IN",
        "with_original_language": language,
        "primary_release_date.gte": date_gte,
        "primary_release_date.lte": date_lte,
        "sort_by": sort_by,
        "with_runtime.gte": 60,   # exclude movies with 0 or unknown runtime
        "page": 1,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    results = resp.json().get('results', [])
    movies = []
    for m in results[:limit]:
        poster = m.get('poster_path')
        movies.append({
            "id": m.get('id'),
            "title": m.get('title') or m.get('original_title'),
            "poster_url": f"{TMDB_IMG_BASE}{poster}" if poster else None,
            "rating": m.get('vote_average'),
            "release_date": m.get('release_date', ''),
            "overview": m.get('overview', ''),
        })
    return movies

def get_now_playing_movies():
    """
    Fetches a curated 'Now Showing' list for the last 6 days:
      - Hindi movies (priority, up to 12)
      - Trending Hollywood/English movies (fills remaining slots up to 20 total)
    Filters by region=IN throughout.
    """
    api_key = settings.TMDB_API_KEY
    if not api_key:
        return []

    today = date.today()
    six_days_ago = today - timedelta(days=14)
    date_gte = six_days_ago.strftime("%Y-%m-%d")
    date_lte = today.strftime("%Y-%m-%d")

    try:
        # 1. Hindi movies (up to 16) — sorted newest first so low-vote films still appear
        hindi_movies = _fetch_discover(api_key, "hi", date_gte, date_lte, limit=16, sort_by="primary_release_date.desc")

        # 2. Hollywood fills up to 20 total (min 4, more if Hindi is short)
        seen_ids = {m['id'] for m in hindi_movies}
        hollywood_needed = max(4, 20 - len(hindi_movies))
        english_movies = _fetch_discover(api_key, "en", date_gte, date_lte, limit=hollywood_needed + 5, sort_by="popularity.desc")
        hollywood = [m for m in english_movies if m['id'] not in seen_ids][:hollywood_needed]

        # Result: always 20 total (16 Hindi + 4 Hollywood, or fewer Hindi + more Hollywood)
        return hindi_movies + hollywood

    except Exception as e:
        print(f"Error fetching now_playing: {e}")
        return []


def fetch_popular_indian_movies(filters=None):
    """
    Fetches popular Indian movies from TMDB.
    filters: dict with keys 'language', 'genre', 'search' from frontend
    """
    filters = filters or {}
    api_key = settings.TMDB_API_KEY
    if not api_key:
        print("TMDB_API_KEY is not set.")
        return []

    # If search, use search endpoint
    search_query = filters.get('search')
    if search_query:
        url = "https://api.themoviedb.org/3/search/movie"
        params = {
            "api_key": api_key,
            "query": search_query,
            "region": "IN",
            "page": 1
        }
    else:
        url = "https://api.themoviedb.org/3/discover/movie"
        params = {
            "api_key": api_key,
            "region": "IN",
            "sort_by": "primary_release_date.desc",
            "primary_release_date.gte": (date.today() - timedelta(days=5*365)).strftime("%Y-%m-%d"),
            "primary_release_date.lte": date.today().strftime("%Y-%m-%d"),
            "vote_count.gte": 0, # Allow 0 votes but allow loop to filter if rating is exactly 0
            "page": int(filters.get('page', 1)),
            # If language is specified, use it. Otherwise default to major Indian languages
            "with_original_language": "hi|kn|bn|gu|pa|mr" 
        }
        
        # Apply filters
        lang = filters.get('language')
        if lang:
            # Map frontend language names to ISO codes if needed
            # For now assume mostly matching or just use what we have
            # Simple mapping for common Indian languages
            lang_map = {
                'Hindi': 'hi', 'English': 'en', 'Marathi': 'mr', 
                'Malayalam': 'ml', 'Tamil': 'ta', 'Telugu': 'te', 
                'Kannada': 'kn', 'Bengali': 'bn', 'Gujarati': 'gu', 'Punjabi': 'pa'
            }
            if lang in lang_map:
                params['with_original_language'] = lang_map[lang]
        
        # Genre mapping — support multiple genres (comma-separated names) → pipe-separated IDs for TMDB OR logic
        genre = filters.get('genre', '')
        if genre:
            genre_map = {
                'Action': 28, 'Adventure': 12, 'Animation': 16, 'Comedy': 35,
                'Crime': 80, 'Documentary': 99, 'Drama': 18, 'Family': 10751,
                'Fantasy': 14, 'History': 36, 'Horror': 27, 'Music': 10402,
                'Mystery': 9648, 'Romance': 10749, 'Sci-Fi': 878,
                'TV Movie': 10770, 'Thriller': 53, 'War': 10752, 'Western': 37
            }
            genre_names = [g.strip() for g in genre.split(',') if g.strip()]
            genre_ids = [str(genre_map[g]) for g in genre_names if g in genre_map]
            if genre_ids:
                params['with_genres'] = '|'.join(genre_ids)

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        movies = []
        for item in data.get('results', []):
            poster_path = item.get('poster_path')
            # Only include movies with posters
            if not poster_path:
                continue
            
            # Filter user request: No 0 rating, No Te/Ta/Ml
            rating = item.get('vote_average', 0) or 0
            lang = item.get('original_language', '')
            if rating == 0: continue
            if lang in ['te', 'ta', 'ml']: continue
                
            full_poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            
            # Map genre_ids to names if needed, but for now just basic data
            movies.append({
                "id": item.get('id'),
                "title": item.get('title'),
                "overview": item.get('overview'),
                "image": full_poster_url,
                "rating": item.get('vote_average'),
                "release_date": item.get('release_date'),
                "language": item.get('original_language'),
                "genre_ids": item.get('genre_ids', []),
                "backdrop": f"https://image.tmdb.org/t/p/original{item.get('backdrop_path')}" if item.get('backdrop_path') else None
            })
            
        return movies
    except requests.RequestException as e:
        print(f"Error fetching data from TMDB: {e}")
        return []

def fetch_upcoming_indian_movies(page=1):
    """
    Fetches upcoming movies.
    """
    api_key = settings.TMDB_API_KEY
    if not api_key:
        return []

    url = "https://api.themoviedb.org/3/movie/upcoming"
    params = {
        "api_key": api_key,
        "region": "IN",
        "page": page,
        "with_original_language": "hi|kn|bn|gu|pa" 
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        movies = []
        for item in data.get('results', []):
            poster_path = item.get('poster_path')
            if not poster_path:
                continue

            # Apply same quality filters as Now Showing: no 0 ratings, no Te/Ta/Ml
            rating = item.get('vote_average', 0) or 0
            lang = item.get('original_language', '')
            if rating == 0:
                continue
            if lang in ['te', 'ta', 'ml']:
                continue

            full_poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            
            movies.append({
                "id": item.get('id'),
                "title": item.get('title'),
                "image": full_poster_url, 
                "rating": item.get('vote_average'),
                "release_date": item.get('release_date'),
            })
            
        return movies
    except Exception as e:
        print(f"Error fetching upcoming: {e}")
        return []

import google.generativeai as genai

def get_movie_reviews(movie_id):
    """
    Fetch reviews from TMDB for a movie.
    """
    api_key = settings.TMDB_API_KEY
    if not api_key:
        return []

    url = f"https://api.themoviedb.org/3/movie/{movie_id}/reviews"
    params = {
        "api_key": api_key,
        "page": 1
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        reviews = []
        for item in data.get('results', []):
            reviews.append({
                "id": item.get('id'),
                "author": item.get('author'),
                "content": item.get('content'),
                "created_at": item.get('created_at'),
                "url": item.get('url'),
                "rating": item.get('author_details', {}).get('rating')
            })
            
        return reviews
    except Exception as e:
        print(f"Error fetching reviews for {movie_id}: {e}")
        return []

def get_ai_review_summary(reviews):
    """
    Summarize reviews using Gemini.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key or not reviews:
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Prepare text for summarization
        # Limit to first 10 reviews 
        reviews_text = "\n\n".join([f"- {r['content'][:500]}" for r in reviews[:10]])
        
        prompt = f"""
        Here are some audience reviews for a movie:
        
        {reviews_text}
        
        Summarize these audience reviews into a short, two-sentence consensus holding the general sentiment.
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating AI summary: {e}")
        return None

# Simple in-process cache to avoid hammering RapidAPI (respects free-tier rate limits)
# Maps imdb_id -> (timestamp, list_of_reviews)
import time as _time
_rapidapi_cache = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour

def get_imdb_reviews_via_tmdb(tmdb_movie_id):
    """
    Fetches IMDb reviews for a movie via RapidAPI.

    Flow:
    1. Get IMDb ID from TMDB external_ids endpoint.
    2. Call RapidAPI 'movies-ratings2' endpoint to get ratings/review data.
       Results are cached in-process for 1 hour to avoid 429 rate-limit errors.
    3. Format and return the reviews.
    """
    tmdb_api_key = settings.TMDB_API_KEY
    rapidapi_key = settings.RAPIDAPI_KEY

    if not tmdb_api_key or not rapidapi_key:
        print("Missing TMDB_API_KEY or RAPIDAPI_KEY in settings.")
        return []

    # Step 1: Get IMDb ID from TMDB
    try:
        ext_url = f"https://api.themoviedb.org/3/movie/{tmdb_movie_id}/external_ids"
        ext_resp = requests.get(ext_url, params={"api_key": tmdb_api_key}, timeout=10)
        ext_resp.raise_for_status()
        imdb_id = ext_resp.json().get('imdb_id')  # e.g. "tt1375666"

        if not imdb_id:
            print(f"No IMDb ID for TMDB movie {tmdb_movie_id}")
            return []

    except Exception as e:
        print(f"Error fetching IMDb ID: {e}")
        return []

    # --- Cache check ---
    cached = _rapidapi_cache.get(imdb_id)
    if cached:
        ts, reviews = cached
        if _time.time() - ts < _CACHE_TTL_SECONDS:
            print(f"Cache HIT for {imdb_id} — skipping RapidAPI call")
            return reviews


    # Step 2: Fetch rating data from imdb236 RapidAPI (/metascore endpoint)
    # Response: { id, url, averageRating, numVotes }
    try:
        rapidapi_url = f"https://imdb236.p.rapidapi.com/api/imdb/{imdb_id}/metascore"
        headers = {
            "x-rapidapi-host": "imdb236.p.rapidapi.com",
            "x-rapidapi-key": rapidapi_key,
        }
        resp = requests.get(rapidapi_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        print(f"imdb236 response for {imdb_id}: {str(data)[:300]}")

    except Exception as e:
        print(f"Error fetching from imdb236 RapidAPI: {e}")
        return []

    # Step 3: Parse the imdb236 response
    # Structure: { "id": "ttXXX", "url": "...", "averageRating": 8.7, "numVotes": 2481022 }
    formatted_reviews = []

    try:
        imdb_rating = data.get('averageRating') or ''
        imdb_votes  = data.get('numVotes') or ''
        imdb_url    = data.get('url') or f"https://www.imdb.com/title/{imdb_id}/"

        # Build human-readable content string
        content_parts = []
        if imdb_rating:
            content_parts.append(f"IMDb Rating: {imdb_rating}/10")
        if imdb_votes:
            formatted_votes = f"{int(imdb_votes):,}" if isinstance(imdb_votes, int) else str(imdb_votes)
            content_parts.append(f"Based on {formatted_votes} votes")

        content = " | ".join(content_parts) if content_parts else "IMDb data available."

        # Normalise rating to int (1-10 scale)
        rating_val = None
        try:
            rating_val = round(float(str(imdb_rating).replace(',', '')))
        except (ValueError, TypeError):
            pass

        formatted_reviews.append({
            "id": imdb_id,
            "author": "IMDb",
            "content": content,
            "created_at": "",
            "url": imdb_url,
            "rating": rating_val,
        })

    except Exception as e:
        print(f"Error formatting imdb236 response: {e}")

    # Write to cache so subsequent requests (page refresh, duplicate API calls) skip RapidAPI
    if formatted_reviews:
        _rapidapi_cache[imdb_id] = (_time.time(), formatted_reviews)

    return formatted_reviews


def get_streaming_providers():
    """
    Fetches the list of streaming providers available in India (IN region).
    Returns the top 10 sorted by display_priority (most prominent first).
    """
    api_key = settings.TMDB_API_KEY
    if not api_key:
        return []

    url = "https://api.themoviedb.org/3/watch/providers/movie"
    params = {
        "api_key": api_key,
        "watch_region": "IN",
        "language": "en-US",
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get('results', [])

        # Sort by display_priority (lower = more prominent)
        results.sort(key=lambda x: x.get('display_priorities', {}).get('IN', 999))

        providers = []
        for p in results[:10]:
            logo = p.get('logo_path')
            providers.append({
                "id": p.get('provider_id'),
                "name": p.get('provider_name'),
                "logo_url": f"https://image.tmdb.org/t/p/w92{logo}" if logo else None,
            })
        return providers
    except Exception as e:
        print(f"Error fetching streaming providers: {e}")
        return []


def get_movies_by_provider(provider_id, page=1, genre_filter=None, language_code=None):
    """
    Fetches movies available on a given streaming platform in India.
    genre_filter: pipe-separated TMDB genre IDs string, e.g. "28|35" (OR logic)
    language_code: ISO 639-1 code, e.g. 'hi', 'mr', 'en'
    Returns up to 20 movies per page.
    """
    api_key = settings.TMDB_API_KEY
    if not api_key:
        return []

    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": api_key,
        "watch_region": "IN",
        "with_watch_providers": provider_id,
        "watch_monetization_types": "flatrate",
        "sort_by": "popularity.desc",
        "page": page,
    }
    if genre_filter:
        params["with_genres"] = genre_filter
    if language_code:
        params["with_original_language"] = language_code

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get('results', [])

        movies = []
        for m in results[:20]:
            poster = m.get('poster_path')
            if not poster:
                continue
            movies.append({
                "id": m.get('id'),
                "title": m.get('title') or m.get('original_title'),
                "poster_url": f"{TMDB_IMG_BASE}{poster}",
                "rating": m.get('vote_average'),
                "release_date": m.get('release_date', ''),
                "overview": m.get('overview', ''),
                "language": m.get('original_language', ''),
                "genre_ids": m.get('genre_ids', []),
            })
        return movies
    except Exception as e:
        print(f"Error fetching movies for provider {provider_id}: {e}")
        return []
