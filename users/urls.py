from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    UpsertProfileView,
    InviteView,
    TripCreateView,
    ListTripsView,
    JoinTripView,
    ListTripMembersView,
    LeaveTripView,
    CreateReviewView,
    GetUserReviewsView,
    GetUserProfileView,
)


urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/upsert_profile/', UpsertProfileView.as_view(), name='upsert_profile'),
    path('chat/invite/', InviteView.as_view(), name='chat_invite'),
    path('trips/create/', TripCreateView.as_view(), name='trip_create'),
    path('trips/list/', ListTripsView.as_view(), name='trip_list'),
    path('trips/join/', JoinTripView.as_view(), name='trip_join'),
    path('trips/members/', ListTripMembersView.as_view(), name='trip_members'),
    path('trips/leave/', LeaveTripView.as_view(), name='trip_leave'),
    # URLs para reseñas
    path('reviews/create/', CreateReviewView.as_view(), name='create_review'),
    path('reviews/user/', GetUserReviewsView.as_view(), name='get_user_reviews'),
    path('profile/user/', GetUserProfileView.as_view(), name='get_user_profile'),
]

