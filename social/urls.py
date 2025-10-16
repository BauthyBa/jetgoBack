from django.urls import path
from . import views

urlpatterns = [
    # Posts
    path('posts/', views.PostListCreateView.as_view(), name='post-list-create'),
    path('posts/<str:post_id>/like/', views.PostLikeView.as_view(), name='post-like'),
    path('posts/<str:post_id>/comments/', views.CommentListCreateView.as_view(), name='comment-list-create'),
    
    # Stories
    path('stories/', views.StoryListCreateView.as_view(), name='story-list-create'),
    path('stories/<str:story_id>/view/', views.StoryViewView.as_view(), name='story-view'),
    
    # Follows
    path('users/<str:user_id>/follow/', views.FollowUserView.as_view(), name='follow-user'),
    path('users/<str:user_id>/followers/', views.FollowersListView.as_view(), name='followers-list'),
    path('users/<str:user_id>/following/', views.FollowingListView.as_view(), name='following-list'),
    
    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notification-list'),
    path('notifications/<str:notification_id>/read/', views.NotificationReadView.as_view(), name='notification-read'),
]
