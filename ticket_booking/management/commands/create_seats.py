from django.core.management.base import BaseCommand
from ticket_booking.models import Seat, Theater


class Command(BaseCommand):
    help = 'Create seats for a theater'

    def add_arguments(self, parser):
        parser.add_argument(
            '--theater-id',
            type=int,
            default=12,
            help='Theater ID to create seats for (default: 12)'
        )
        parser.add_argument(
            '--rows',
            type=str,
            default='A,B,C,D,E,F,G,H,I,J,K,L',
            help='Comma-separated list of row labels (default: A-L)'
        )
        parser.add_argument(
            '--cols',
            type=str,
            default='1-12',
            help='Column range in format "start-end" (default: 1-12)'
        )
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing seats before creating new ones'
        )

    def handle(self, *args, **options):
        theater_id = options['theater_id']
        rows = options['rows'].split(',')
        
        # Parse column range
        col_range = options['cols'].split('-')
        if len(col_range) == 2:
            cols = range(int(col_range[0]), int(col_range[1]) + 1)
        else:
            self.stdout.write(self.style.ERROR('Invalid column range format. Use "start-end"'))
            return
        
        # Get theater
        try:
            theater = Theater.objects.get(id=theater_id)
            self.stdout.write(self.style.SUCCESS(f'Theater found: {theater.name} (ID: {theater.id})'))
        except Theater.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Theater with ID {theater_id} not found'))
            return
        
        # Check existing seats
        existing_seats = Seat.objects.filter(theater=theater)
        existing_count = existing_seats.count()
        
        if existing_count > 0:
            self.stdout.write(self.style.WARNING(f'Theater already has {existing_count} seats'))
            
            if options['delete_existing']:
                deleted_count = existing_seats.delete()[0]
                self.stdout.write(self.style.WARNING(f'Deleted {deleted_count} existing seats'))
            else:
                self.stdout.write(self.style.NOTICE('Skipping duplicate seats (use --delete-existing to recreate)'))
        
        # Generate seat list
        seats_to_create = []
        skipped = []
        
        for row in rows:
            for col in cols:
                seat_number = f"{row}{col}"
                
                # Check if seat already exists
                if Seat.objects.filter(theater=theater, seat_number=seat_number).exists():
                    skipped.append(seat_number)
                    continue
                
                seats_to_create.append(Seat(theater=theater, seat_number=seat_number))
        
        # Bulk create seats
        if seats_to_create:
            Seat.objects.bulk_create(seats_to_create)
            self.stdout.write(self.style.SUCCESS(f'✓ Successfully created {len(seats_to_create)} seats'))
        else:
            self.stdout.write(self.style.NOTICE('No new seats to create'))
        
        if skipped:
            self.stdout.write(self.style.WARNING(f'Skipped {len(skipped)} duplicate seats'))
        
        # Summary
        total_seats = Seat.objects.filter(theater=theater).count()
        self.stdout.write(self.style.SUCCESS(f'\nTotal seats in theater: {total_seats}'))
        self.stdout.write(self.style.SUCCESS(f'Layout: {len(rows)} rows × {len(list(cols))} columns'))
