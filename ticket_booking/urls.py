from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from .auth_views import MyTokenObtainPairView
from .views import generate_invoice_pdf, start_recommendation_task, recommendation_task_status
from .chat_views import chatbot_response, chatbot_response_status
from .summary_views import get_movie_summary
from .booking_views import confirm_booking
from .my_bookings_views import my_bookings
from .tmdb_views import movies_list as tmdb_movies_list, movie_details as tmdb_movie_details, movie_reviews as tmdb_movie_reviews, now_playing as tmdb_now_playing, streaming_providers, stream_movies
from . import sports_views
from . import show_views

urlpatterns = [
    path('', views.movie_list, name='movies'),
    path('api/movies/', tmdb_movies_list, name='tmdb_movies'),
    path('api/movies/now-playing/', tmdb_now_playing, name='tmdb_now_playing'),
    path('api/movie/<int:movie_id>/', tmdb_movie_details, name='tmdb_movie_details'),
    path('api/movie/<int:movie_id>/reviews/', tmdb_movie_reviews, name='tmdb_movie_reviews'),
    path('citys/',views.city_list, name="city"),
    path('explore/', views.explore, name='explore'),
    path('genre/',views.genre_list, name = 'genres'),
    path('payment/', views.payment , name = "payment"),
    path('movies/', views.movie_list, name='movie_list'),
    path('movie/<int:movie_id>/summary/', get_movie_summary, name='movie_summary'),
    path('movie/<int:movie_id>/reviews/', views.movie_reviews, name='movie_reviews'),
    path('movie/<int:movie_id>/reviews/<int:review_id>/', views.delete_movie_review, name='delete_movie_review'),
    path('send_otp/', views.send_otp , name='send email'),
    path('language/',views.language_list, name='language'),
    path('verify_otp/', views.verify_otp , name='verify-otp'),
    path('booking/', views.initial_booking, name='book_ticket'),
    path('confirm_booking/', confirm_booking, name='confirm_booking'),
    path('register_user/', views.register_user, name='register' ),
    path('booking_info/', views.booking_info, name="booking_info" ),
    path('seat_layout/', views.show_seat_layout, name='show_seat_layout'),
    path('theater_list/', views.theater_list, name='theater_list_by_movie'),
    path('payment_confirm/', views.payment_confirm , name = "payment_confirm"),
    path('api/token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('retrieve_movie/<int:movie_id>', views.retrieve_movie, name='retrive_movie'),
    path('invoice/<int:booking_id>/', views.generate_invoice_pdf, name='invoice_view' ),
    path('download-invoice/<int:booking_id>/', generate_invoice_pdf, name='download_invoice'),
    path('recommendations/start/', start_recommendation_task, name='start_recommendation_task'),
    path('recommendations/status/<str:task_id>/', recommendation_task_status, name='recommendation_task_status'),
    path('chatbot/', chatbot_response, name='chatbot'),
    path('chatbot/status/<str:task_id>/', chatbot_response_status, name='chatbot_status'),
    path('my-bookings/', my_bookings, name='my_bookings'),
    path('api/providers/', streaming_providers, name='streaming_providers'),
    path('api/stream/movies/', stream_movies, name='stream_movies'),
    path('api/sports/turfs/', sports_views.turf_list, name='turf_list'),
    path('api/sports/turf/<str:turf_id>/', sports_views.turf_detail, name='turf_detail'),
    path('api/sports/turf/<str:turf_id>/booked-slots/', sports_views.get_booked_slots, name='get_booked_slots'),
    path('api/sports/turfs/book/', sports_views.book_turf_slot, name='book_turf_slot'),
    path('api/movies/<int:movie_id>/shows/', show_views.movie_shows, name='movie_shows'),
    path('api/shows/<int:show_id>/seats/', show_views.show_seats, name='show_seats'),

    # path('movie_list/', views.movie_list_with_status, name='movie_list_with_status'),
    # path('email_verification/',views.send_otp_email,name= ' verification'),
    # path('mybookings/', views.my_bookings, name='my_bookings '),
    # path('theaters/', views.theater_list, name='theater list'),
    # path('lock_seats/', views.lock_seats, name='lock_seats'),
    # path('login_user/',views.login_user,name="login"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

