import sys
from ticket_booking.models import Seat, Theater

# Configuration
THEATER_ID = 11
ROWS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
COLS = range(1, 13)  # 1 to 12

print("=" * 60)
print("SEAT CREATION SCRIPT")
print("=" * 60)

# Get theater
try:
    theater = Theater.objects.get(id=THEATER_ID)
    print(f"✓ Theater found: {theater.name} (ID: {theater.id})")
except Theater.DoesNotExist:
    print(f"✗ Error: Theater with ID {THEATER_ID} not found")
    sys.exit(1)

# Check existing seats
existing_count = Seat.objects.filter(theater=theater).count()

if existing_count > 0:
    print(f"⚠ Warning: Theater already has {existing_count} seats")
    print(f"  Skipping duplicate seats...")

# Generate seat list
seats_to_create = []
skipped = 0

for row in ROWS:
    for col in COLS:
        seat_number = f"{row}{col}"
        
        # Check if seat already exists
        if Seat.objects.filter(theater=theater, seat_number=seat_number).exists():
            skipped += 1
            continue
        
        seats_to_create.append(Seat(theater=theater, seat_number=seat_number))

# Bulk create seats
if seats_to_create:
    Seat.objects.bulk_create(seats_to_create)
    print(f"✓ Successfully created {len(seats_to_create)} new seats")
else:
    print("ℹ No new seats to create")

if skipped > 0:
    print(f"  Skipped {skipped} duplicate seats")

# Summary
total_seats = Seat.objects.filter(theater=theater).count()
print("=" * 60)
print(f"SUMMARY:")
print(f"  Total seats in theater: {total_seats}")
print(f"  Layout: {len(ROWS)} rows × {len(list(COLS))} columns")
print("=" * 60)

# To delete all seats and recreate, uncomment below:
# Seat.objects.filter(theater=theater).delete()
# Then run this script again


