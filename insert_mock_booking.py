import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyshow.settings')
django.setup()

from django.contrib.auth import get_user_model
from ticket_booking.models import Turf, TurfBooking
from datetime import date

User = get_user_model()
user = User.objects.first()

if not user:
    print("No user found. Please create a user first.")
    exit()

print(f"Using user: {user.username}")

turf, _ = Turf.objects.get_or_create(
    osm_id='mock_fb_0', 
    defaults={'name': 'Kickoff Pitch Football'}
)
print(f"Turf: {turf.name}")

booking, created = TurfBooking.objects.get_or_create(
    user=user, 
    turf=turf, 
    booking_date=date.today(), 
    time_slot='16:30 - 17:00', 
    defaults={'total_price': 800}
)

if created:
    print(f"Booking created for {booking.booking_date} at {booking.time_slot}")
else:
    print(f"Booking already exists for {booking.booking_date} at {booking.time_slot}")
