from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Bookinginfo, TurfBooking


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_bookings(request):
    """
    Get all bookings for the authenticated user (movies and turfs).
    """
    # Fetch movie bookings
    movie_bookings = Bookinginfo.objects.filter(user=request.user).order_by('-booking_time')
    
    combined_data = []
    
    # Process movie bookings
    for booking in movie_bookings:
        seats = booking.seats.all()
        seat_numbers = [seat.seat_number for seat in seats]
        
        combined_data.append({
            'id': f"movie_{booking.id}",
            'type': 'movie',
            'booking_time': booking.booking_time.isoformat(),
            'movie_title': booking.show.movie.title,
            'movie_poster': booking.show.movie.image.url if booking.show.movie.image else None,
            'theater_name': booking.theater.name,
            'theater_location': booking.theater.location,
            'show_time': booking.show.time_slot.isoformat(),
            'seats': seat_numbers,
            'number_of_tickets': booking.number_of_tickets,
            'total_price': booking.show.price * booking.number_of_tickets,
            'is_paid': booking.is_paid,
        })

    turf_bookings = TurfBooking.objects.filter(user=request.user).order_by('-created_at')
    
    # Process turf bookings and group them by turf_id and booking_date
    turf_bookings_grouped = {}
    for booking in turf_bookings:
        key = (booking.turf.osm_id, booking.booking_date)
        if key not in turf_bookings_grouped:
            turf_bookings_grouped[key] = {
                'id': f"turf_{booking.id}",
                'type': 'turf',
                'booking_time': booking.created_at.isoformat(),
                'turf_name': booking.turf.name,
                'turf_location': booking.location,
                'turf_id': booking.turf.osm_id,
                'booking_date': booking.booking_date.isoformat(),
                'time_slots': [booking.time_slot],
                'total_price': booking.total_price,
                'is_paid': True,
            }
        else:
            turf_bookings_grouped[key]['time_slots'].append(booking.time_slot)
            turf_bookings_grouped[key]['total_price'] += booking.total_price

    # Sort the time slots within each grouping chronologically
    for booking_group in turf_bookings_grouped.values():
        booking_group['time_slots'].sort()

    combined_data.extend(turf_bookings_grouped.values())

    # Sort combined list by booking_time descending
    combined_data.sort(key=lambda x: x['booking_time'], reverse=True)
    
    return JsonResponse({'bookings': combined_data})
