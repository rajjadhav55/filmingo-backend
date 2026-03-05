from django.http import JsonResponse
from .tmdb_utils import (
    fetch_popular_indian_movies, 
    fetch_upcoming_indian_movies,
    get_movie_reviews,
    get_imdb_reviews_via_tmdb,
    get_ai_review_summary,
    get_now_playing_movies,
    get_streaming_providers,
    get_movies_by_provider,
)

def now_playing(request):
    """
    API endpoint: /api/movies/now-playing/
    Returns movies currently in Indian theatres from TMDB.
    """
    movies = get_now_playing_movies()
    return JsonResponse({'results': movies})


def movie_reviews(request, movie_id):
    """
    API endpoint: /api/movie/<id>/reviews/
    Returns reviews and AI summary (now using IMDb)
    """
    # 1. Try fetching IMDb reviews first
    reviews = get_imdb_reviews_via_tmdb(movie_id)
    
    # 2. Fallback to TMDB reviews if no IMDb reviews found (optional, but good for robustness)
    if not reviews:
        reviews = get_movie_reviews(movie_id)

    ai_summary = None
    
    # Only generate summary if there are reviews
    if reviews:
        ai_summary = get_ai_review_summary(reviews)
        
    return JsonResponse({
        'reviews': reviews,
        'ai_summary': ai_summary
    })

def movies_list(request):
    """
    API endpoint: /api/movies/
    Returns JSON with 'Now Showing' and 'upcoming'.
    When searching, splits results by release_date:
      - released on/before today  -> Now Showing
      - releasing after today     -> Upcoming
    """
    from datetime import date
    today = date.today().isoformat()

    page = int(request.GET.get('page', 1))

    filters = {
        'language': request.GET.get('language'),
        'genre': request.GET.get('genre'),
        'search': request.GET.get('search'),
        'page': page,
    }

    search_query = filters.get('search')

    if search_query:
        # Search returns all matching movies regardless of release date.
        # Split them here so each ends up in the right section.
        all_results = fetch_popular_indian_movies(filters)
        now_showing = [m for m in all_results if (m.get('release_date') or '') <= today]
        upcoming    = [m for m in all_results if (m.get('release_date') or '') >  today]
    else:
        now_showing = fetch_popular_indian_movies(filters)
        upcoming    = fetch_upcoming_indian_movies(page=page)

    return JsonResponse({
        'Now Showing': now_showing,
        'upcoming': upcoming
    })

from .tmdb_details_utils import fetch_movie_details

def movie_details(request, movie_id):
    """
    API endpoint: /api/movie/<id>/
    Returns detailed JSON for a movie
    """
    details = fetch_movie_details(movie_id)
    if details:
        return JsonResponse({'movie': details})
    return JsonResponse({'error': 'Movie not found'}, status=404)


def streaming_providers(request):
    """
    API endpoint: /api/providers/
    Returns the top 10 streaming providers available in India.
    """
    providers = get_streaming_providers()
    return JsonResponse({'providers': providers})


def stream_movies(request):
    """
    API endpoint: /api/stream/movies/?provider_id=<id>&page=<n>&genres=<name1,name2>
    Returns movies available on the given streaming platform in India.
    """
    provider_id = request.GET.get('provider_id')
    if not provider_id:
        return JsonResponse({'error': 'provider_id is required'}, status=400)

    page = int(request.GET.get('page', 1))

    # Build pipe-separated genre IDs for TMDB OR logic
    GENRE_MAP = {
        'Action': 28, 'Adventure': 12, 'Animation': 16, 'Comedy': 35,
        'Crime': 80, 'Drama': 18, 'Fantasy': 14, 'Horror': 27,
        'Mystery': 9648, 'Romance': 10749, 'Sci-Fi': 878, 'Thriller': 53,
    }
    genres_raw = request.GET.get('genres', '')
    genre_ids = [str(GENRE_MAP[g.strip()]) for g in genres_raw.split(',') if g.strip() in GENRE_MAP]
    genre_filter = '|'.join(genre_ids) if genre_ids else None

    LANG_MAP = {
        'Hindi': 'hi', 'English': 'en', 'Marathi': 'mr', 'Malayalam': 'ml',
        'Tamil': 'ta', 'Telugu': 'te', 'Kannada': 'kn', 'Bengali': 'bn',
        'Gujarati': 'gu', 'Punjabi': 'pa',
    }
    language_name = request.GET.get('language', '')
    language_code = LANG_MAP.get(language_name)

    movies = get_movies_by_provider(provider_id, page=page, genre_filter=genre_filter, language_code=language_code)
    return JsonResponse({'results': movies, 'page': page})
