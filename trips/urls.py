from django.urls import path
from . import views, chat_views

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
    
    # Chat
    path('chat/upload-file/', chat_views.upload_chat_file, name='upload-chat-file'),
    path('chat/send-message/', chat_views.send_chat_message, name='send-chat-message'),
    path('chat/rooms/<str:room_id>/messages/', chat_views.get_chat_messages, name='get-chat-messages'),
    path('chat/rooms/', chat_views.get_user_chat_rooms, name='get-user-chat-rooms'),
    path('chat/messages/<str:message_id>/delete-file/', chat_views.delete_chat_file, name='delete-chat-file'),
    path('chat/rooms/<str:room_id>/file-stats/', chat_views.get_room_file_stats, name='get-room-file-stats'),
]