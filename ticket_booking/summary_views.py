
import os
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from google import genai
from google.genai import types

from .models import Movie, Review

def call_llm_for_summary(movie_title, reviews_text):
    """
    Call Gemini to summarize reviews.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "AI Summary unavailable (API Key missing)."

    client = genai.Client(api_key=api_key)

    system_prompt = (
        "You are an AI assistant for a movie review platform.\n"
        "GOAL: Summarize the following user reviews into a single, concise paragraph (max 3 sentences) that captures the general sentiment.\n"
        "Start with 'The audience feels', 'Viewers generally agree', or similar.\n"
        "Focus on common themes like acting, plot, visuals, etc.\n"
        "Do not list individual reviews. Synthesize them."
    )

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=f"{system_prompt}\n\nMovie: {movie_title}\n\nReviews:\n{reviews_text}",
            config=types.GenerateContentConfig(
                response_mime_type="text/plain",
            ),
        )
        return response.text.strip()
    except Exception as e:
        error_str = str(e)
        print(f"Gemini API Error: {e}")
        
        # Check for quota/rate limit errors
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
            return "AI summary is temporarily unavailable due to high demand. Please check back later or read the reviews below for audience opinions."
        
        return "Summary unavailable at the moment. Please read the reviews below for detailed audience feedback."

@require_http_methods(["GET"])
def get_movie_summary(request, movie_id):
    try:
        movie = Movie.objects.get(pk=movie_id)
    except Movie.DoesNotExist:
        return JsonResponse({'error': 'Movie not found'}, status=404)

    # Check if force refresh is requested
    force_refresh = request.GET.get('force_refresh', 'false').lower() == 'true'
    
    # Check cache first (cache key includes movie_id)
    cache_key = f"movie_summary_{movie_id}"
    
    if not force_refresh:
        cached_summary = cache.get(cache_key)
        
        if cached_summary is not None:
            print(f"✓ Returning cached summary for movie {movie_id}")
            return JsonResponse({'summary': cached_summary, 'cached': True})

    # Fetch last 20 reviews to avoid context limit issues and keep it relevant
    reviews = Review.objects.filter(movie=movie).order_by('-created_at')[:20]
    
    if not reviews.exists():
        return JsonResponse({'summary': None})

    # Concatenate reviews
    reviews_text = "\n".join([f"- {r.comment}" for r in reviews if r.comment.strip()])
    
    if not reviews_text:
         return JsonResponse({'summary': None})

    # Call LLM
    if force_refresh:
        print(f"🔄 Force refreshing summary for movie {movie_id}")
    else:
        print(f"⚠ Calling Gemini API for movie {movie_id} (not cached)")
    
    summary = call_llm_for_summary(movie.title, reviews_text)
    
    # Cache the result for 1 hour (3600 seconds)
    cache.set(cache_key, summary, 3600)
    
    return JsonResponse({'summary': summary, 'cached': False})

