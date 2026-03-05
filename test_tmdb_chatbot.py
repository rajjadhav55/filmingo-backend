import os
import django
from django.conf import settings
import sys

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyshow.settings')
django.setup()

from ticket_booking.chat_views import get_movie_info, get_gemini_client
from google.genai import types

def test_chatbot(query):
    print(f"\n--- Testing Query: {query} ---")
    client = get_gemini_client()
    if not client:
        print("Error: Gemini client could not be initialized.")
        return
        
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=query,
            config=types.GenerateContentConfig(
                tools=[get_movie_info],
                system_instruction=(
                    "You are the 'BookMyShow Assistant', a helpful chatbot for movie recommendations.\n"
                    "ALWAYS use the `get_movie_info` tool when the user asks about a specific movie, "
                    "or where to watch it, or if it is in theaters.\n"
                    "Format your response specifically based on the tool's output:\n"
                    "- If the tool says `in_theaters` is true, explicitly say: 'This movie is currently running in theaters!'\n"
                    "- If the tool says `in_theaters` is false and lists platforms, explicitly say: "
                    "'This movie is not in theaters right now, but you can stream it on [Insert OTT Platform Name(s)].'\n"
                    "- If the tool returns an error, apologize and say you couldn't find the information."
                )
            )
        )
        print("Response:", response.text)
    except Exception as e:
        print(f"Error calling Gemini: {e}")

if __name__ == "__main__":
    test_chatbot("Where can I watch Inception?")
    test_chatbot("Is Deadpool currently running in theaters?")
