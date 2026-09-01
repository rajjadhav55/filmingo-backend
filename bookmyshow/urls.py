

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from ticket_booking.views import fetch_sports_events

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/sports/', fetch_sports_events, name='sports_events'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # refresh
    path('', include('ticket_booking.urls')), 
]

