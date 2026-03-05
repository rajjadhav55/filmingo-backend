import random
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import (
    Movie, Theater, Show, Seat, ShowSeatBooking, Language, City, State,
    Session
)

# ──────────────────────────────────────────────────────────────────────
# Constants for on-the-fly mock data generation
# ──────────────────────────────────────────────────────────────────────
MOCK_THEATERS = [
    {"name": "PVR Icon", "location": "Andheri West"},
    {"name": "INOX Megaplex", "location": "Malad West"},
    {"name": "Cinepolis", "location": "Thane"},
]

TIME_SLOTS = [
    (9, 30),   # 09:30 AM
    (13, 15),  # 01:15 PM
    (17, 0),   # 05:00 PM
    (21, 45),  # 09:45 PM
]

FORMATS = ["2D", "3D", "IMAX 3D"]

SEAT_TIERS = {
    "Recliner": {"rows": ["K", "L"], "price": 450},
    "Prime":    {"rows": ["E", "F", "G", "H", "I", "J"], "price": 250},
    "Classic":  {"rows": ["A", "B", "C", "D"], "price": 150},
}

COLS = list(range(1, 13))  # 1..12


def _ensure_city():
    """Get or create a default city to attach theaters to."""
    city = City.objects.first()
    if not city:
        state, _ = State.objects.get_or_create(name="Maharashtra")
        city, _ = City.objects.get_or_create(name="Mumbai", defaults={"state": state})
    return city


def _ensure_language():
    """Get or create a Hindi language record."""
    lang = Language.objects.filter(name="Hindi").first()
    if not lang:
        lang = Language.objects.create(name="Hindi")
    return lang


def _ensure_theaters():
    """Ensure the 3 mock theaters exist and return them."""
    city = _ensure_city()
    theaters = []
    for info in MOCK_THEATERS:
        # Use filter().first() to handle databases with duplicate theater names
        theater = Theater.objects.filter(name=info["name"]).first()
        if not theater:
            theater = Theater.objects.create(
                name=info["name"],
                city=city,
                location=info["location"],
            )
        theaters.append(theater)
    return theaters


def _ensure_seats_for_theater(theater):
    """Ensure tier-based seats exist for a theater (rows A-L × cols 1-12)."""
    if Seat.objects.filter(theater=theater).count() >= 144:
        return  # already populated

    seats_to_create = []
    for tier_name, config in SEAT_TIERS.items():
        for row in config["rows"]:
            for col in COLS:
                seat_num = f"{row}{col}"
                if not Seat.objects.filter(theater=theater, seat_number=seat_num).exists():
                    seats_to_create.append(
                        Seat(
                            theater=theater,
                            seat_number=seat_num,
                            tier=tier_name,
                            price=config["price"],
                        )
                    )
    if seats_to_create:
        Seat.objects.bulk_create(seats_to_create)


def _ensure_movie_placeholder(tmdb_id):
    """
    Get or create a lightweight placeholder Movie row so we can attach
    Show records to TMDB movies.  The tmdb_id is stored in the PK.
    """
    movie, created = Movie.objects.get_or_create(
        id=tmdb_id,
        defaults={
            "title": f"TMDB#{tmdb_id}",
            "duration_min": 150,
            "description": "Auto-created placeholder for TMDB movie",
        },
    )
    return movie


def _ensure_shows_for_movie_on_date(movie, date_obj):
    """Auto-generate shows for every mock theater on the given date if none exist."""
    theaters = _ensure_theaters()
    lang = _ensure_language()

    for theater in theaters:
        _ensure_seats_for_theater(theater)

        existing = Show.objects.filter(
            movie=movie,
            theater=theater,
            time_slot__date=date_obj,
        ).count()

        if existing >= len(TIME_SLOTS):
            continue

        for hour, minute in TIME_SLOTS:
            slot_dt = timezone.make_aware(
                datetime.combine(date_obj, datetime.min.time().replace(hour=hour, minute=minute))
            )
            if Show.objects.filter(movie=movie, theater=theater, time_slot=slot_dt).exists():
                continue

            fmt = random.choice(FORMATS)
            base_price = SEAT_TIERS["Classic"]["price"]

            show = Show.objects.create(
                movie=movie,
                theater=theater,
                language=lang,
                price=base_price,
                time_slot=slot_dt,
                format=fmt,
            )

            # Pre-book ~20% of seats randomly
            seats = Seat.objects.filter(theater=theater)
            booked_count = max(1, int(seats.count() * 0.2))
            booked_seats = random.sample(list(seats), min(booked_count, seats.count()))

            # Create a session for mock bookings
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_user = User.objects.first()
            if admin_user:
                session = Session.objects.filter(user=admin_user).first()
                if not session:
                    session = Session.objects.create(user=admin_user)
                for seat in booked_seats:
                    ShowSeatBooking.objects.get_or_create(
                        show=show,
                        seat=seat,
                        defaults={
                            "session_id": session,
                            "is_booked": True,
                            "is_locked": False,
                        },
                    )


# ======================================================================
#  API ENDPOINTS
# ======================================================================

@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def movie_shows(request, movie_id):
    """
    GET /api/movies/<movie_id>/shows/?date=YYYY-MM-DD
    Returns shows grouped by theater for a given TMDB movie on a date.
    """
    date_str = request.GET.get("date")
    if not date_str:
        return JsonResponse({"error": "date query param required (YYYY-MM-DD)"}, status=400)

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

    # Ensure placeholder movie & shows exist
    movie = _ensure_movie_placeholder(movie_id)
    _ensure_shows_for_movie_on_date(movie, date_obj)

    shows = (
        Show.objects
        .filter(movie=movie, time_slot__date=date_obj)
        .select_related("theater", "language")
        .order_by("theater__name", "time_slot")
    )

    # Group by theater
    theaters_map = {}
    for show in shows:
        tid = show.theater.id
        if tid not in theaters_map:
            theaters_map[tid] = {
                "theater_id": tid,
                "theater_name": show.theater.name,
                "theater_location": show.theater.location,
                "showtimes": [],
            }
        theaters_map[tid]["showtimes"].append({
            "id": show.id,
            "time": show.time_slot.strftime("%I:%M %p"),
            "format": show.format,
            "price": show.price,
            "language": show.language.name if show.language else "Hindi",
        })

    return JsonResponse(list(theaters_map.values()), safe=False)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def show_seats(request, show_id):
    """
    GET /api/shows/<show_id>/seats/
    Returns seat layout grouped by tier with booking status.
    """
    try:
        show = Show.objects.select_related("movie", "theater", "language").get(id=show_id)
    except Show.DoesNotExist:
        return JsonResponse({"error": "Show not found"}, status=404)

    # Build seat status map from ShowSeatBooking
    bookings = ShowSeatBooking.objects.filter(show=show).select_related("seat")
    seat_status = {}
    for b in bookings:
        if b.is_booked:
            seat_status[b.seat.id] = "booked"
        elif b.is_locked:
            seat_status[b.seat.id] = "locked"

    # Get all seats for theater
    all_seats = Seat.objects.filter(theater=show.theater).order_by("seat_number")

    # Group by tier
    tiers_map = {}
    for seat in all_seats:
        tier_name = seat.tier or "Classic"
        if tier_name not in tiers_map:
            tiers_map[tier_name] = {
                "name": tier_name,
                "price": seat.price,
                "rows": set(),
                "seats": [],
            }
        row_letter = "".join(filter(str.isalpha, seat.seat_number))
        tiers_map[tier_name]["rows"].add(row_letter)
        tiers_map[tier_name]["seats"].append({
            "seat_number": seat.seat_number,
            "status": seat_status.get(seat.id, "available"),
        })

    # Convert rows sets to sorted lists & order tiers: Recliner > Prime > Classic
    tier_order = {"Recliner": 0, "Prime": 1, "Classic": 2}
    tiers_list = []
    for tier in sorted(tiers_map.values(), key=lambda t: tier_order.get(t["name"], 99)):
        tier["rows"] = sorted(tier["rows"])
        tiers_list.append(tier)

    return JsonResponse({
        "show_id": show.id,
        "movie_title": show.movie.title,
        "theater_name": show.theater.name,
        "theater_location": show.theater.location,
        "date": show.time_slot.strftime("%Y-%m-%d"),
        "time": show.time_slot.strftime("%I:%M %p"),
        "format": show.format,
        "language": show.language.name if show.language else "Hindi",
        "tiers": tiers_list,
    })
