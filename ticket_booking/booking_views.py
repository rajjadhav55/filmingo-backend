import uuid
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models import Bookinginfo, Show, Seat, ShowSeatBooking, Session


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_booking(request):
    """
    Confirm booking after payment (mock payment gateway).
    Creates a permanent booking record and marks seats as booked.
    """
    show_id = request.data.get('show_id')
    seat_numbers = request.data.get('seat_numbers', [])
    payment_method = request.data.get('payment_method', 'upi')
    session_id = request.data.get('session_id')
    
    if not show_id or not seat_numbers:
        return JsonResponse({'error': 'Missing show_id or seat_numbers'}, status=400)
    
    try:
        show = Show.objects.get(id=show_id)
    except Show.DoesNotExist:
        return JsonResponse({'error': 'Show not found'}, status=404)
    
    # Verify all seats exist and are available
    seats = []
    for seat_num in seat_numbers:
        try:
            seat = Seat.objects.get(theater=show.theater, seat_number=seat_num)
            
            # Check if seat is already booked for this show
            existing_booking = ShowSeatBooking.objects.filter(
                show=show,
                seat=seat,
                is_booked=True
            ).exists()
            
            if existing_booking:
                return JsonResponse({
                    'error': f'Seat {seat_num} is already booked'
                }, status=400)
            
            seats.append(seat)
        except Seat.DoesNotExist:
            return JsonResponse({
                'error': f'Seat {seat_num} not found'
            }, status=404)
    
    # Generate booking ID
    booking_id = str(uuid.uuid4())[:8].upper()
    
    # Create main booking record
    booking = Bookinginfo.objects.create(
        user=request.user,
        show=show,
        theater=show.theater,
        number_of_tickets=len(seats),
        is_paid=True  # Mock payment successful
    )
    
    # Add seats to the booking
    booking.seats.set(seats)
    
    # Mark seats as booked in ShowSeatBooking
    session = None
    if session_id:
        try:
            session = Session.objects.get(session_id=session_id)
        except Session.DoesNotExist:
            pass
            
    if not session:
        session = Session.objects.filter(user=request.user).order_by('-created_at').first()
        if not session:
            session = Session.objects.create(user=request.user)
    
    for seat in seats:
        if session_id:
            # Update the existing locked seat
            ShowSeatBooking.objects.filter(
                show=show,
                seat=seat,
                session_id=session,
                is_locked=True
            ).update(
                bookinginfo=booking,
                is_booked=True,
                is_locked=False
            )
        else:
            ShowSeatBooking.objects.update_or_create(
                show=show,
                seat=seat,
                defaults={
                    'bookinginfo': booking,
                    'session_id': session,
                    'is_booked': True,
                    'is_locked': False
                }
            )
    
    # Calculate total price
    price_per_seat = 200  # Default price
    total_price = len(seats) * price_per_seat
    
    # Send confirmation email
    try:
        from django.core.mail import EmailMessage
        from django.conf import settings
        from django.utils.html import format_html
        
        user_email = request.user.email
        
        if user_email:
            # Try to generate QR code as attachment
            qr_buffer = None
            try:
                import qrcode
                from io import BytesIO
                
                qr_data = f"Booking ID: {booking_id}\nMovie: {show.movie.title}\nTheater: {show.theater.name}\nSeats: {', '.join(seat_numbers)}\nShow: {show.time_slot.strftime('%d %b %Y, %I:%M %p')}"
                
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(qr_data)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                
                qr_buffer = BytesIO()
                qr_img.save(qr_buffer, format='PNG')
                qr_buffer.seek(0)  # Reset buffer position
                
            except ImportError:
                print("QR code library not installed. Skipping QR code generation.")
            except Exception as e:
                print(f"Failed to generate QR code: {e}")
            
            subject = f"🎬 Booking Confirmed - {show.movie.title}"
            
            # Format seat list
            seats_list = ', '.join(seat_numbers)
            
            # Format show time
            show_time = show.time_slot.strftime('%d %B %Y, %I:%M %p')
            
            # Movie poster URL (if available)
            poster_url = ""
            if show.movie.image:
                poster_url = f"{settings.MEDIA_URL}{show.movie.image}"
            
            body = format_html(f'''
            <div style="
                font-family: 'Helvetica Neue', Arial, sans-serif; 
                color: #333; 
                background-color: #f9fafb;
                padding: 20px;
            ">
                <div style="
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    border: 2px solid #dc2626; 
                    border-radius: 12px; 
                    overflow: hidden;
                    box-shadow: 0px 4px 12px rgba(0,0,0,0.2);
                ">
                    <!-- Header with Movie Poster -->
                    <div style="background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%); padding: 30px; text-align: center;">
                        <h1 style="color: white; margin: 0 0 10px 0; font-size: 28px;">✅ Booking Confirmed!</h1>
                        <p style="color: #fecaca; margin: 0; font-size: 16px;">Your tickets are ready</p>
                    </div>
                    
                    <!-- Booking ID -->
                    <div style="background-color: #fef2f2; padding: 20px; text-align: center; border-bottom: 2px dashed #dc2626;">
                        <p style="font-size: 14px; color: #666; margin: 0 0 5px 0;">Booking ID</p>
                        <p style="font-size: 32px; font-weight: bold; color: #dc2626; margin: 0; letter-spacing: 2px;">{booking_id}</p>
                    </div>
                    
                    <!-- Content -->
                    <div style="padding: 30px;">
                        <!-- Movie Details -->
                        <div style="margin-bottom: 25px;">
                            <h3 style="color: #dc2626; border-bottom: 2px solid #dc2626; padding-bottom: 10px; margin-top: 0;">
                                🎬 Movie Details
                            </h3>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Movie</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 14px; text-align: right;">{show.movie.title}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Theater</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 14px; text-align: right;">{show.theater.name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Location</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 14px; text-align: right;">{show.theater.location}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Show Time</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 14px; text-align: right;">{show_time}</td>
                                </tr>
                            </table>
                        </div>
                        
                        <!-- Booking Details -->
                        <div style="margin-bottom: 25px;">
                            <h3 style="color: #dc2626; border-bottom: 2px solid #dc2626; padding-bottom: 10px;">
                                🎫 Booking Details
                            </h3>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Seats</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 14px; text-align: right;">{seats_list}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Tickets</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 14px; text-align: right;">{len(seats)}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Amount Paid</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 18px; color: #dc2626; text-align: right;">₹{total_price}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Payment Method</td>
                                    <td style="padding: 8px 0; font-weight: bold; font-size: 14px; text-align: right;">{payment_method.upper()}</td>
                                </tr>
                            </table>
                        </div>
                        
                        <!-- Important Instructions -->
                        <div style="background-color: #fef3c7; padding: 15px; border-radius: 8px; border-left: 4px solid #f59e0b;">
                            <p style="font-size: 14px; font-weight: bold; color: #92400e; margin: 0 0 10px 0;">
                                ⚠️ Important Instructions
                            </p>
                            <ul style="font-size: 13px; color: #78350f; margin: 0; padding-left: 20px;">
                                <li style="margin: 5px 0;">Arrive 15 minutes before show time</li>
                                <li style="margin: 5px 0;">Carry a valid ID proof</li>
                                <li style="margin: 5px 0;">Show the attached QR code at the counter</li>
                                <li style="margin: 5px 0;">Outside food not allowed</li>
                            </ul>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 2px solid #e5e7eb;">
                        <p style="font-size: 14px; color: #666; margin: 0 0 5px 0;">Thank you for booking with us!</p>
                        <p style="font-size: 20px; font-weight: bold; color: #dc2626; margin: 0;">BookMyShow</p>
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
            
            # Attach QR code if generated successfully
            if qr_buffer:
                email_message.attach(
                    f'booking_qr_{booking_id}.png',
                    qr_buffer.getvalue(),
                    'image/png'
                )
            
            email_message.send(fail_silently=True)
            
    except Exception as e:
        print(f"Failed to send confirmation email: {e}")
    
    # Extract QR code and poster for frontend response
    qr_base64 = None
    if 'qr_buffer' in locals() and qr_buffer:
        import base64
        qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')

    poster_url = ""
    if show.movie and show.movie.image:
        image_str = str(show.movie.image)
        if image_str.startswith('http'):
            poster_url = image_str
        else:
            try:
                poster_url = str(show.movie.image.url)
            except ValueError:
                from django.conf import settings
                poster_url = f"{settings.MEDIA_URL}{image_str}"

    return JsonResponse({
        'success': True,
        'booking_id': booking_id,
        'seats': seat_numbers,
        'total_price': total_price,
        'payment_method': payment_method,
        'show_time': show.time_slot.isoformat(),
        'message': 'Booking confirmed successfully!',
        'movie_title': show.movie.title if show.movie else '',
        'theater_name': show.theater.name if show.theater else '',
        'poster_url': poster_url,
        'qr_base64': qr_base64
    })


