import json
import os
import traceback
from typing import Dict, List, Any

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from google import genai
from google.genai import types
from google.genai.errors import ClientError

from django.db import models
from .models import Movie

# --- Configuration ---
# Your movie catalog helps Gemini prioritize what you have in stock.
MY_CATALOG = [
    "Demon Slayer - Kimetsu no Yaiba - The Movie: Infinity Castle",
    "Jurassic World: Rebirth", "Kantara: A Legend Chapter-1", "Housefull 5",
    "Shinchan: Our Dinosaur Diary", "Lilo & Stitch", "Avatar: Fire and Ash",
    "Retro", "Raid 2", "Gulkand", "Thunderbolts*", "Final Destination Bloodlines",
    "Mission: Impossible - The Final Reckoning", "bhool chuk maf", "your name", "DR.STONE"
]

def call_llm_for_movies(user_prompt: str) -> Dict[str, Any]:
    """
    Call Gemini to get structured movie recommendations.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Please set it in your environment before starting the Celery worker."
        )

    client = genai.Client(api_key=api_key)

    system_prompt = (
        "You are an expert movie recommendation engine for a cinema ticket booking website.\n\n"
        "GOAL:\n"
        "Given a user mood or natural language description, recommend 3-5 movies that best match the request.\n\n"
        f"AVAILABLE CATALOG:\n{', '.join(MY_CATALOG)}\n\n"
        "GUIDELINES:\n"
        "- PRIORITIZE movies from the 'AVAILABLE CATALOG' if they fit the mood.\n"
        "- If no catalog movies fit, suggest other well-known films.\n"
        "- Return ONLY valid JSON."
    )

    # Official JSON schema for Gemini 2.0
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "movies": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING"},
                        "year": {"type": "INTEGER"},
                        "genres": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "reason": {"type": "STRING"}
                    },
                    "required": ["title", "year", "reason"]
                }
            }
        }
    }

    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=f"{system_prompt}\n\nUser request:\n{user_prompt}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        ),
    )

    try:
        data = json.loads(response.text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Gemini did not return valid JSON: {exc}") from exc

    return data


# Rate limit set to 10/m to stay comfortably under the 15/m Free Tier limit
@shared_task(bind=True, rate_limit='10/m', max_retries=5)
def generate_movie_recommendations(self, user_prompt: str) -> Dict[str, Any]:
    """
    Celery task that fetches recommendations and matches them with your DB.
    Handles 429 Rate Limits by waiting and retrying.
    """
    try:
        # 1. Call Gemini
        llm_data = call_llm_for_movies(user_prompt)

    except ClientError as e:
        # Check specifically for Rate Limit / Quota Exhaustion
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            print(f"⚠️ Quota hit. Pausing for 60s before retry. (Attempt {self.request.retries + 1}/5)")
            try:
                # Wait 60 seconds (countdown) then try again
                raise self.retry(exc=e, countdown=60)
            except MaxRetriesExceededError:
                print("❌ Max retries reached. Giving up.")
                self.update_state(
                    state="FAILURE",
                    meta={'exc_type': 'MaxRetriesExceeded', 'exc_message': 'Google API quota exhausted repeatedly.'}
                )
                raise
        
        # Handle other API errors (like 400 Bad Request, 401 Unauthorized)
        self.update_state(
            state="FAILURE",
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e),
                'traceback': traceback.format_exc()
            }
        )
        raise

    except Exception as exc:
        # Handle unexpected Python errors
        self.update_state(
            state="FAILURE",
            meta={
                'exc_type': type(exc).__name__,
                'exc_message': str(exc),
                'traceback': traceback.format_exc()
            }
        )
        raise

    # 2. Process the Results
    movies_from_llm = llm_data.get("movies", [])
    
    # Extract titles for bulk DB lookup
    titles = [m.get("title") for m in movies_from_llm if isinstance(m, dict) and m.get("title")]
    
    # Filter using case-insensitive OR logic
    from django.db.models import Q
    query = Q()
    for t in titles:
        query |= Q(title__iexact=t)
    
    db_movies = Movie.objects.filter(query) if titles else []
    
    # Create a lookup map: "your name" -> MovieObject
    db_by_title_lower = {m.title.lower(): m for m in db_movies}

    combined_results = []
    for m in movies_from_llm:
        if not isinstance(m, dict): 
            continue

        title = m.get("title")
        if not title: 
            continue

        # Check catalog using lowercase to catch "Your Name" vs "your name"
        db_movie = db_by_title_lower.get(title.lower())

        rating = None
        image_url = None
        if db_movie:
            if db_movie.image:
                 image_url = db_movie.image.url
            
            # Calculate average rating
            avg = db_movie.reviews.aggregate(models.Avg('rating'))['rating__avg']
            if avg:
                rating = round(avg, 1)

        combined_results.append({
            "title": title,
            "year": m.get("year"),
            "genres": m.get("genres") or [],
            "reason": m.get("reason"),
            "in_catalog": db_movie is not None,
            "db_id": db_movie.id if db_movie else None,
            "image": image_url,
            "rating": rating,
        })

    return {
        "user_prompt": user_prompt,
        "movies": combined_results,
    }