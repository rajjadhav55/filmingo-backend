from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
import json
import os
import requests
from datetime import datetime, timedelta
from django.conf import settings
import google.generativeai as genai

def get_gemini_client():
    api_key = getattr(settings, 'GEMINI_API_KEY', os.environ.get("GEMINI_API_KEY"))
    if not api_key:
        return False
    genai.configure(api_key=api_key)
    return True

def get_movie_info(movie_query: str) -> str:
    """Fetches movie details from TMDB, checks theatrical status, and finds streaming providers in India."""
    tmdb_api_key = getattr(settings, 'TMDB_API_KEY', os.environ.get('TMDB_API_KEY'))
    if not tmdb_api_key:
        return {"error": "TMDB API key not configured."}
        
    # Search for the movie
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={tmdb_api_key}&query={movie_query}&language=en-US&page=1"
    
    try:
        search_response = requests.get(search_url).json()
        if not search_response.get('results'):
            return {"error": f"Could not find any movie matching '{movie_query}'."}
            
        # Get the top result
        movie = search_response['results'][0]
        movie_id = movie.get('id')
        title = movie.get('title')
        release_date_str = movie.get('release_date', '')
        
        # Check theatrical status
        in_theaters = False
        if release_date_str:
            try:
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
                today = datetime.now().date()
                # Consider it in theaters if released within the last 60 days
                if today - timedelta(days=60) <= release_date <= today + timedelta(days=15):
                    in_theaters = True
            except ValueError:
                pass
                
        # Fetch watch providers
        providers_url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers?api_key={tmdb_api_key}"
        providers_response = requests.get(providers_url).json()
        
        # Look for IN (India) region providers
        india_providers = providers_response.get('results', {}).get('IN', {})
        flatrate_providers = [p.get('provider_name') for p in india_providers.get('flatrate', [])]
        
        return json.dumps({
            "db_id": movie_id,
            "title": title,
            "release_date": release_date_str,
            "in_theaters": in_theaters,
            "streaming_platforms_in_india": flatrate_providers,
            "image": f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get('poster_path') else ""
        })
        
    except Exception as e:
         return {"error": f"Failed to fetch TMDB data: {str(e)}"}

def discover_tmdb_movies(genres: str) -> str:
    """Discovers top recommendations from TMDB (Movies and TV). Returns mostly Hindi content and some high-rated English."""
    tmdb_api_key = getattr(settings, 'TMDB_API_KEY', os.environ.get('TMDB_API_KEY'))
    if not tmdb_api_key:
        return {"error": "TMDB API key not configured."}
        
    movie_genre_map = {
        'action': 28, 'comedy': 35, 'drama': 18, 'romance': 10749, 'horror': 27,
        'sci-fi': 878, 'thriller': 53, 'animation': 16, 'family': 10751, 'fantasy': 14
    }
    tv_genre_map = {
         'action': 10759, 'comedy': 35, 'drama': 18, 'romance': 10749, 'horror': 27,
         'sci-fi': 10765, 'thriller': 53, 'animation': 16, 'family': 10751, 'fantasy': 10765
    }
    
    movie_genre_ids = []
    tv_genre_ids = []
    for g in genres.lower().replace('/', ',').split(','):
        g = g.strip()
        if g in movie_genre_map:
            movie_genre_ids.append(str(movie_genre_map[g]))
        if g in tv_genre_map:
            tv_genre_ids.append(str(tv_genre_map[g]))
            
    m_url = f"https://api.themoviedb.org/3/discover/movie?api_key={tmdb_api_key}&language=en-US&sort_by=popularity.desc&page=1"
    if movie_genre_ids: m_url += f"&with_genres={'|'.join(movie_genre_ids)}"
    
    t_url = f"https://api.themoviedb.org/3/discover/tv?api_key={tmdb_api_key}&language=en-US&sort_by=popularity.desc&page=1"
    if tv_genre_ids: t_url += f"&with_genres={'|'.join(tv_genre_ids)}"
        
    try:
        # Fetch 2 Hindi movies
        hi_m_url = m_url + "&with_original_language=hi"
        hi_m_resp = requests.get(hi_m_url).json().get('results', [])[:2]
        
        # Fetch 2 Hindi tv shows
        hi_t_url = t_url + "&with_original_language=hi"
        hi_t_resp = requests.get(hi_t_url).json().get('results', [])[:2]
        
        # Fetch 2 English movies (Highly Rated)
        en_m_url = m_url + "&with_original_language=en&vote_average.gte=6.5&vote_count.gte=300"
        en_m_resp = requests.get(en_m_url).json().get('results', [])[:2]
        
        content = hi_m_resp + hi_t_resp + en_m_resp
        result = []
        for c in content:
            title = c.get('title') or c.get('name')
            date = c.get('release_date') or c.get('first_air_date')
            result.append({
                "db_id": c.get('id'),
                "title": title,
                "release_date": date,
                "overview": c.get('overview'),
                "language": c.get('original_language'),
                "image": f"https://image.tmdb.org/t/p/w500{c.get('poster_path')}" if c.get('poster_path') else ""
            })
        return json.dumps(result) if result else json.dumps({"error": "No content found."})
    except Exception as e:
        return f"Error discovering content: {str(e)}"

from celery import shared_task
from celery.result import AsyncResult

@shared_task
def process_chatbot_request(user_message):
    print("\n" + "="*50)
    print(f"🚀 [CELERY WORKER] Processing message: '{user_message}'")
    try:
        print("🔗 Initializing Gemini Client...")
        client = get_gemini_client()
        if not client:
             return {"error": "Chatbot service unavailable", "status": 503}

        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            tools=[get_movie_info, discover_tmdb_movies],
            system_instruction=(
                "You are the BookMyShow Assistant, a highly knowledgeable and friendly movie/TV recommendation expert.\n"
                "You have two tools available:\n"
                "1. `discover_tmdb_movies(genres)`: Use this when the user asks for recommendations based on mood (e.g., 'sad', 'happy'), genres, or general categories. Map their mood to appropriate genres (like 'comedy', 'action') and call this tool to get a mixed list of top Hindi movies, Hindi TV series, and high-rated English movies.\n"
                "2. `get_movie_info(movie_query)`: Use this ONLY when the user asks about a SPECIFIC movie by name, or if you want to check if a specific movie is in theaters or streaming in India.\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "- NEVER HALLUCINATE OR MAKE UP MOVIES. You must ONLY recommend real movies specifically returned by the JSON output of your tools.\n"
                "- When providing recommendations (either from the discovery tool or your own knowledge), ensure your list is MOSTLY Hindi movies or TV series, with only 1 or 2 highly-rated English titles.\n"
                "- Emphasize if a recommendation is a TV Series instead of a movie.\n"
                "- You MUST ALWAYS return your final response as a pure JSON object. DO NOT wrap it in markdown block quotes. Just return the raw JSON string natively.\n"
                "- The JSON must have this EXACT structure:\n"
                "{\n"
                '  "text": "Your conversational, enthusiastic reply goes here.",\n'
                '  "type": "recommendations",\n'
                '  "movies": [\n'
                "    {\n"
                '       "title": "Movie Title",\n'
                '       "year": "Release Year",\n'
                '       "rating": "Provide an emoji or score",\n'
                '       "reason": "Why you recommend this particular movie in 1-2 sentences",\n'
                '       "db_id": 12345,\n'
                '       "image": "https://image.tmdb.org/t/p/w500/...",\n'
                '       "in_theaters": true,\n'
                '       "in_catalog": true\n'
                "    }\n"
                "  ]\n"
                "}\n"
                "- Set `in_catalog` to true ALWAYS when returning movies.\n"
                "- Set `in_theaters` to whatever boolean the TMDB tool returned for that movie.\n"
                "- Pull `db_id` and `image` directly from the tool JSON outputs.\n"
                "- If the user's message does not require you to show movie cards (e.g. just a simple greeting), you must still return the JSON object, but set \"type\" to \"chat\" and \"movies\" to an empty list []."
            )
        )
        
        print("🧠 Starting a multi-turn chat session with Gemini...")
        chat = model.start_chat(enable_automatic_function_calling=True)
        response = chat.send_message(user_message)
        
        print("✅ Gemini Request Successful!")
        raw_text = response.text.replace('```json', '').replace('```', '').strip()
        try:
            reply_payload = json.loads(raw_text)
        except Exception:
            # Fallback if LLM ignores instructions
            reply_payload = {"text": raw_text, "type": "chat", "movies": []}
            
        print("="*50 + "\n")
        return {"reply": reply_payload}
        
    except Exception as e:
        error_msg = str(e)
        import traceback; traceback.print_exc()
        print(f"CRITICAL GEMINI ERROR: {error_msg}")
        
        if "429" in error_msg or "quota" in error_msg.lower() or "exhausted" in error_msg.lower():
            print("🛑 Caught '429 Quota/Exhausted' Error from Gemini SDK.")
            return {"error": "I'm currently receiving too many requests. Please try again in about an hour!", "status": 429}
            
        return {"error": error_msg, "status": 500}


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def chatbot_response(request):
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            user_message = data.get("message", "")
        else:
             user_message = request.POST.get("message", "")

        if not user_message:
            return JsonResponse({"error": "Message is required"}, status=400)
            
        # Dispatch to Celery queue immediately
        task = process_chatbot_request.delay(user_message)
        return JsonResponse({"task_id": task.id}, status=202)
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def chatbot_response_status(request, task_id):
    task_result = AsyncResult(task_id)
    if task_result.state == 'PENDING':
        return JsonResponse({'status': 'PENDING'})
    elif task_result.state == 'SUCCESS':
        result = task_result.result
        if "error" in result:
             # Retain the exact HTTP status codes generated by the worker
             status_code = result.get("status", 500)
             return JsonResponse({"error": result["error"]}, status=status_code)
        return JsonResponse({'status': 'SUCCESS', 'reply': result.get('reply', '')})
    elif task_result.state == 'FAILURE':
        return JsonResponse({'status': 'FAILURE', 'error': str(task_result.info)}, status=500)
    else:
        return JsonResponse({'status': task_result.state})
