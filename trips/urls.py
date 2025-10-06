from django.urls import path
from . import views

urlpatterns = [
    # Viajes
    path('trips/', views.TripListCreateView.as_view(), name='trip-list-create'),
    path('trips/<int:pk>/', views.TripDetailView.as_view(), name='trip-detail'),
    path('trips/<int:trip_id>/participants/', views.trip_participants, name='trip-participants'),
    path('trips/<int:trip_id>/group-chat/', views.create_group_chat, name='create-group-chat'),
    path('trips/<int:trip_id>/leave/', views.leave_trip, name='leave-trip'),
    
    # Aplicaciones
    path('applications/', views.ApplicationCreateView.as_view(), name='application-create'),
    path('applications/my/', views.ApplicationListView.as_view(), name='my-applications'),
    path('trips/<int:trip_id>/applications/', views.TripApplicationsListView.as_view(), name='trip-applications'),
    path('applications/<int:application_id>/respond/', views.respond_to_application, name='respond-application'),
]