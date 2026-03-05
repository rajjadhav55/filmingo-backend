import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Turf, TurfBooking
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils.html import format_html
from datetime import datetime
from .sports_utils import get_turfs_from_osm, get_turf_details

def turf_list(request):
    """
    API endpoint: /api/sports/turfs/?location=Palghar
    Returns a list of sports turfs in the requested location fetched from OSM.
    """
    location = request.GET.get('location', 'Mumbai')
    turfs = get_turfs_from_osm(location)
    return JsonResponse({'turfs': turfs})

def turf_detail(request, turf_id):
    """
    API endpoint: /api/sports/turf/<str:turf_id>/
    Returns detailed mock information for a single turf.
    """
    details = get_turf_details(turf_id)
    return JsonResponse(details)

def get_booked_slots(request, turf_id):
    """
    API endpoint: /api/sports/turf/<str:turf_id>/booked-slots/?date=YYYY-MM-DD
    Returns a list of already booked slots for a given turf and date.
    """
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'error': 'Date is required'}, status=400)
    
    booked_slots = TurfBooking.objects.filter(
        turf__osm_id=turf_id,
        booking_date=date_str
    ).values_list('time_slot', flat=True)
    
    return JsonResponse({'booked_slots': list(booked_slots)})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def book_turf_slot(request):
    """
    API endpoint: /api/sports/turfs/book/
    Creates a new turf booking.
    """
    data = request.data
    turf_id = data.get('turf_id')
    turf_name = data.get('turf_name', 'Unnamed Turf')
    turf_location = data.get('turf_location', 'Unknown Location')
    booking_date = data.get('booking_date')
    
    # Support both new array format and old fallback
    time_slots = data.get('time_slots')
    time_slot = data.get('time_slot')
    
    total_price = data.get('total_price')
    
    if not all([turf_id, booking_date, total_price]) or not (time_slots or time_slot):
        return JsonResponse({'error': 'Missing required fields'}, status=400)
    
    # Get or create the Turf object (since they are dynamic from OSM)
    turf, _ = Turf.objects.get_or_create(osm_id=turf_id, defaults={'name': turf_name, 'location': turf_location})
    
    try:
        bookings = []
        if time_slots:
            for slot in time_slots:
                booking = TurfBooking.objects.create(
                    user=request.user,
                    turf=turf,
                    location=turf_location,
                    booking_date=booking_date,
                    time_slot=slot.get('time'),
                    total_price=slot.get('price')
                )
                bookings.append(booking)
            
            # Format combined string for the single email
            display_time_slot = ", ".join(sorted([s.get('time') for s in time_slots]))
            display_booking_ref = f"TB-{bookings[0].id}" + ("+" if len(bookings) > 1 else "")
            response_booking_id = bookings[0].id
        else:
            booking = TurfBooking.objects.create(
                user=request.user,
                turf=turf,
                location=turf_location,
                booking_date=booking_date,
                time_slot=time_slot,
                total_price=total_price
            )
            bookings.append(booking)
            display_time_slot = time_slot
            display_booking_ref = f"TB-{booking.id}"
            response_booking_id = booking.id
        
        # Send confirmation email
        try:
            user_email = request.user.email
            if user_email:
                subject = f"🏟️ Turf Booking Confirmed - {turf_name}"
                
                # Format date string nicely if we can
                try:
                    date_obj = datetime.strptime(booking_date, "%Y-%m-%d")
                    display_date = date_obj.strftime("%d %b %Y")
                except:
                    display_date = booking_date
                
                body = format_html(f'''
                <div style="font-family: 'Helvetica Neue', Arial, sans-serif; color: #333; background-color: #f9fafb; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: white; border: 2px solid #059669; border-radius: 12px; overflow: hidden; box-shadow: 0px 4px 12px rgba(0,0,0,0.2);">
                        <!-- Header -->
                        <div style="background: linear-gradient(135deg, #059669 0%, #047857 100%); padding: 30px; text-align: center;">
                            <h1 style="color: white; margin: 0 0 10px 0; font-size: 28px;">✅ Booking Confirmed!</h1>
                            <p style="color: #d1fae5; margin: 0; font-size: 16px;">Your turf is reserved</p>
                        </div>
                        
                        <!-- Booking ID -->
                        <div style="background-color: #ecfdf5; padding: 20px; text-align: center; border-bottom: 2px dashed #059669;">
                            <p style="font-size: 14px; color: #666; margin: 0 0 5px 0;">Booking Ref</p>
                            <p style="font-size: 32px; font-weight: bold; color: #059669; margin: 0; letter-spacing: 2px;">{display_booking_ref}</p>
                        </div>
                        
                        <!-- Content -->
                        <div style="padding: 30px;">
                            <h3 style="color: #059669; border-bottom: 2px solid #059669; padding-bottom: 10px; margin-top: 0;">
                                🏟️ Turf Details
                            </h3>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Venue</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 14px; text-align: right;">{turf_name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Location</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 14px; text-align: right;">{turf_location}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Date</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 14px; text-align: right;">{display_date}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Time Slots</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 14px; text-align: right;">{display_time_slot}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Amount Paid</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 18px; color: #059669; text-align: right;">₹{total_price}</td>
                                </tr>
                            </table>
                            
                            <!-- Important Instructions -->
                            <div style="margin-top: 25px; background-color: #fef3c7; padding: 15px; border-radius: 8px; border-left: 4px solid #f59e0b;">
                                <p style="font-size: 14px; font-weight: bold; color: #92400e; margin: 0 0 10px 0;">
                                    ⚠️ Ground Rules
                                </p>
                                <ul style="font-size: 13px; color: #78350f; margin: 0; padding-left: 20px;">
                                    <li style="margin: 5px 0;">Wear proper non-marking sports shoes</li>
                                    <li style="margin: 5px 0;">Arrive 10 minutes prior to your slot</li>
                                    <li style="margin: 5px 0;">Show this email at the reception desk</li>
                                </ul>
                            </div>
                        </div>
                        
                        <!-- Footer -->
                        <div style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 2px solid #e5e7eb;">
                            <p style="font-size: 14px; color: #666; margin: 0 0 5px 0;">Have a great game!</p>
                            <p style="font-size: 20px; font-weight: bold; color: #059669; margin: 0;">Filmingo Sports</p>
                        </div>
                    </div>
                </div>
                ''')
                
                email_message = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=settings.EMAIL_HOST_USER,
                    to=[user_email],
                )
                email_message.content_subtype = 'html'
                email_message.send(fail_silently=True)
                
        except Exception as email_err:
            # We don't want to fail the booking if the email just failed to send
            print(f"Failed to send turf booking email: {email_err}")

        return JsonResponse({
            'success': True,
            'message': 'Booking successful',
            'booking_id': response_booking_id
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
