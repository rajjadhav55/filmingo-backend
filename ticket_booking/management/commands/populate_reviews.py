import random
import sys
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import IntegrityError

class Command(BaseCommand):
    help = 'Populate the database with random reviews for movies'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting populate_reviews...")
        sys.stdout.flush()

        from ticket_booking.models import Movie, Review
        User = get_user_model()
        
        # 1. Ensure we have users to create reviews
        users = list(User.objects.all())
        if len(users) < 3:
            self.stdout.write("Creating dummy users...")
            for i in range(5):
                username = f'reviewer_{i}'
                if not User.objects.filter(username=username).exists():
                    u = User.objects.create_user(username=username, email=f'{username}@example.com', password='password123')
                    users.append(u)
        
        movies = list(Movie.objects.all())
        if not movies:
            self.stdout.write(self.style.ERROR("No movies found! Please add movies first."))
            return

        comments_pool = [
            "Really enjoyed this one! The pacing was perfect.",
            "A bit slow in the middle, but great ending.",
            "Absolutely fantastic! Would watch again.",
            "Not my cup of tea, honestly.",
            "The visual effects were stunning.",
            "Good performance by the lead actor.",
            "Disappointing plot, expected more.",
            "A masterpiece of modern cinema.",
            "Decent watch for a weekend.",
            "Characters felt a bit shallow.",
            "Hilarious! Laughed the whole time.",
            "Intense and gripping from start to finish.",
            "Average movie, nothing special.",
            "Unexpected twists kept me hooked!",
            "Wasted potential given the cast.",
        ]

        # 2. Add random reviews
        count = 0
        for movie in movies:
            # Pick distinct random users for each movie review
            # Let's add 3-8 reviews per movie
            num_reviews_to_add = random.randint(3, 8)
            available_users = users[:] 
            random.shuffle(available_users)

            creation_count_for_movie = 0
            for _ in range(num_reviews_to_add):
                if not available_users:
                    break
                
                user = available_users.pop()
                rating = random.randint(1, 5)
                comment = random.choice(comments_pool)

                try:
                    Review.objects.create(
                        movie=movie,
                        user=user,
                        rating=rating,
                        comment=comment,
                    )
                    count += 1
                    creation_count_for_movie += 1
                except IntegrityError:
                    # User already reviewed this movie
                    continue
            
            self.stdout.write(f"Added {creation_count_for_movie} reviews for '{movie.title}'")

        self.stdout.write(self.style.SUCCESS(f'Successfully created {count} new reviews!'))
