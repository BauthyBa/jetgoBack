from django.urls import path
from . import views, chat_views, trip_reviews_views, expenses_views

urlpatterns = [
    # Viajes
    path('trips/', views.TripListCreateView.as_view(), name='trip-list-create'),
    path('trips/<int:pk>/', views.TripDetailView.as_view(), name='trip-detail'),
    path('trips/my-participating/', views.user_participating_trips, name='user-participating-trips'),
    path('trips/<int:trip_id>/participants/', views.trip_participants, name='trip-participants'),
    path('trips/<int:trip_id>/group-chat/', views.create_group_chat, name='create-group-chat'),
    path('trips/<int:trip_id>/leave/', views.leave_trip, name='leave-trip'),
    
    # Aplicaciones
    path('applications/', views.ApplicationCreateView.as_view(), name='application-create'),
    path('applications/my/', views.ApplicationListView.as_view(), name='my-applications'),
    path('trips/<int:trip_id>/applications/', views.TripApplicationsListView.as_view(), name='trip-applications'),
    path('applications/<int:application_id>/respond/', views.respond_to_application, name='respond-application'),
    
    # Chat
    path('chat/test/', chat_views.test_endpoint, name='test-endpoint'),
    path('chat/test-audio/', chat_views.test_audio_upload, name='test-audio-upload'),
    path('chat/upload-file/', chat_views.upload_chat_file, name='upload-chat-file'),
    path('chat/upload-camera/', chat_views.upload_camera_image, name='upload-camera-image'),
    path('chat/send-message/', chat_views.send_chat_message, name='send-chat-message'),
    path('chat/rooms/<str:room_id>/messages/', chat_views.get_chat_messages, name='get-chat-messages'),
    path('chat/rooms/', chat_views.get_user_chat_rooms, name='get-user-chat-rooms'),
    path('chat/messages/<str:message_id>/delete-file/', chat_views.delete_chat_file, name='delete-chat-file'),
    path('chat/rooms/<str:room_id>/file-stats/', chat_views.get_room_file_stats, name='get-room-file-stats'),
    
    # Reseñas de Viajes
    path('trip-reviews/', trip_reviews_views.TripReviewCreateView.as_view(), name='trip-review-create'),
    path('trip-reviews/list/', trip_reviews_views.TripReviewListView.as_view(), name='trip-review-list'),
    path('trip-reviews/eligibility/', trip_reviews_views.TripReviewEligibilityView.as_view(), name='trip-review-eligibility'),
    path('trip-reviews/<str:review_id>/', trip_reviews_views.TripReviewDetailView.as_view(), name='trip-review-detail'),
    path('trip-reviews/<str:review_id>/update/', trip_reviews_views.TripReviewUpdateView.as_view(), name='trip-review-update'),
    path('trip-reviews/<str:review_id>/delete/', trip_reviews_views.TripReviewDeleteView.as_view(), name='trip-review-delete'),
    path('trip-reviews/<str:review_id>/response/', trip_reviews_views.TripReviewResponseView.as_view(), name='trip-review-response'),
    path('trip-reviews/categories/', trip_reviews_views.TripReviewCategoriesView.as_view(), name='trip-review-categories'),
    
    # Gastos de Viajes
    path('trip-expenses/', expenses_views.TripExpenseCreateView.as_view(), name='trip-expense-create'),
    path('trip-expenses/list/', expenses_views.TripExpenseListView.as_view(), name='trip-expense-list'),
    path('trip-expenses/summary/', expenses_views.TripExpenseSummaryView.as_view(), name='trip-expense-summary'),
    path('trip-expenses/<str:expense_id>/', expenses_views.TripExpenseDetailView.as_view(), name='trip-expense-detail'),
    path('trip-expenses/<str:expense_id>/update/', expenses_views.TripExpenseUpdateView.as_view(), name='trip-expense-update'),
    path('trip-expenses/<str:expense_id>/delete/', expenses_views.TripExpenseDeleteView.as_view(), name='trip-expense-delete'),
    path('trip-expenses/categories/', expenses_views.TripExpenseCategoriesView.as_view(), name='trip-expense-categories'),
]