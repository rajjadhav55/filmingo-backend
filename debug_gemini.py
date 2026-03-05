import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyshow.settings')
django.setup()

from ticket_booking.models import Show, Bookinginfo

last_booking = Bookinginfo.objects.order_by('-id').first()
if last_booking:
    show = last_booking.show
    movie = show.movie
    print(f"Movie: {movie.title}")
    print(f"Image Type: {type(movie.image)}")
    print(f"Image Name: {movie.image.name if movie.image else 'None'}")
    
    try:
        url = movie.image.url
        print(f"Image URL property: {url}")
    except Exception as e:
        print(f"URL error: {e}")
        
    print(f"String rep: {str(movie.image)}")
else:
    print("No bookings found")
