from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    UpsertProfileView,
    InviteView,
    TripCreateView,
    ListTripsView,
    JoinTripView,
)


urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/upsert_profile/', UpsertProfileView.as_view(), name='upsert_profile'),
    path('chat/invite/', InviteView.as_view(), name='chat_invite'),
    path('trips/create/', TripCreateView.as_view(), name='trip_create'),
    path('trips/list/', ListTripsView.as_view(), name='trip_list'),
    path('trips/join/', JoinTripView.as_view(), name='trip_join'),
]

