import uuid
import random
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
# from django.dispatch import receiver
# from django.db.models.signals import post_save
class customUser(AbstractUser):
    contact_no = models.CharField(max_length=15, null=True, blank=True)
    is_admin = models.BooleanField(default=False)

    def __str__(self):
        return self.username
    
class State (models.Model):
    name = models.CharField(max_length= 20)

    def __str__(self):
        return self.name
    

class City (models.Model):
    name = models.CharField(max_length= 50 )
    state = models.ForeignKey(State,on_delete=models.CASCADE)

    def __str__(self):
        return self.name
    
class Theater(models.Model):
    name = models.CharField(max_length=100)
    city = models.ForeignKey(City,on_delete=models.CASCADE)
    location= models.CharField(max_length=20)

    def __str__(self):
        return self.name
    
class Genre(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name
    
class Language(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name
    
class Seat(models.Model):
    theater= models.ForeignKey(Theater, on_delete=models.CASCADE)
    seat_number = models.CharField(max_length=10)
    tier = models.CharField(max_length=20, default='Classic')  # Recliner, Prime, Classic
    price = models.IntegerField(default=200)
    # is_booked = models.BooleanField(default=False)

    def __str__(self):
        return (self.seat_number)

    
class Movie(models.Model):
    title = models.CharField(max_length=100)
    duration_min = models.IntegerField()
    release_date = models.DateField(null=True, blank=True)
    description =  models.CharField(max_length=1000)
    genres =  models.ManyToManyField(Genre,max_length=100)
    language = models.ManyToManyField(Language,max_length=20)
    image = models.ImageField(upload_to='movies/', null=True, blank=True)

    def __str__(self):
        return self.title
    

class Review(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="movie_reviews")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.CharField(max_length=1000, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("movie", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.movie.title} - {self.user} ({self.rating}/5)"




class Show(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE)
    language= models.ForeignKey(Language,on_delete=models.CASCADE)
    seats = models.ManyToManyField(Seat,through='ShowSeatBooking')
    price = models.IntegerField(default=0)
    time_slot = models.DateTimeField()
    format = models.CharField(max_length=20, default='2D')  # 2D, 3D, IMAX 3D
    

    def __str__(self):
        if self.movie:
            movie_title = self.movie.title
        else:
            movie_title = 'No Movie'

        if self.theater:
            theater_name = self.theater.name
        else:
            theater_name = 'No Theater'

        if self.time_slot:
            time_slot_str = self.time_slot.strftime('%I:%M %p on %B %d, %Y')
        else:
            time_slot_str = 'No Time Slot'

        return f"{movie_title} at {theater_name} - {time_slot_str}"



class Bookinginfo(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    booking_time = models.DateTimeField(auto_now_add=True)
    number_of_tickets = models.IntegerField(default=1)
    theater = models.ForeignKey(Theater,on_delete=models.CASCADE)
    is_paid = models.BooleanField(default=False)
    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    seats = models.ManyToManyField(Seat)  

    def __str__(self):
        return f"{self.user.username} booked {self.number_of_tickets} tickets for {self.show.movie.title} at {self.show.theater.name}"

class Session(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ShowSeatBooking(models.Model):
    show = models.ForeignKey('Show', on_delete=models.CASCADE)
    seat = models.ForeignKey('Seat', on_delete=models.CASCADE)
    bookinginfo = models.ForeignKey(Bookinginfo, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.ForeignKey(Session,on_delete=models.CASCADE)
    is_booked = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    


    class Meta:
        unique_together = ('show', 'seat')





class OTPStorage(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    counter=  models.IntegerField(default=1)
    is_expired = models.BooleanField(default=False)
    

    class Meta:
        get_latest_by = "created_at"

class ingredients (models.Model):
    name = models.CharField(max_length=50)
    category = models.CharField(max_length=50)
    quantity = models.IntegerField(default=0)
    price = models.IntegerField(default=0)

class Turf(models.Model):
    osm_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, default='Unknown Location')

    def __str__(self):
        return self.name

class TurfBooking(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    turf = models.ForeignKey(Turf, on_delete=models.CASCADE)
    location = models.CharField(max_length=255, default='Unknown Location')
    booking_date = models.DateField()
    time_slot = models.CharField(max_length=50) # e.g., '16:00 - 17:00'
    total_price = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('turf', 'booking_date', 'time_slot')

    def __str__(self):
        return f"{self.user.username} - {self.turf.name} - {self.booking_date} ({self.time_slot})"
    