from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import connection
import uuid
from datetime import datetime, timedelta
import json
import os
from users.models import User
from api.supabase_client import get_supabase_admin

def debug_supabase_config():
    """Debug function to check Supabase configuration"""
    url = os.environ.get('SUPABASE_URL')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    anon_key = os.environ.get('SUPABASE_ANON_KEY')
    
    print(f"SUPABASE_URL: {url}")
    print(f"SUPABASE_SERVICE_ROLE_KEY: {service_key[:10] if service_key else 'None'}...")
    print(f"SUPABASE_ANON_KEY: {anon_key[:10] if anon_key else 'None'}...")
    
    return url and service_key and anon_key

class PostListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Obtener posts del feed"""
        try:
            limit = int(request.GET.get('limit', 20))
            offset = int(request.GET.get('offset', 0))
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT p.*, u.nombre, u.apellido, u.avatar_url,
                           COUNT(pl.id) as likes_count,
                           COUNT(pc.id) as comments_count,
                           CASE WHEN pl2.id IS NOT NULL THEN true ELSE false END as is_liked
                    FROM posts p
                    JOIN "User" u ON p.user_id = u.userid
                    LEFT JOIN post_likes pl ON p.id = pl.post_id
                    LEFT JOIN post_comments pc ON p.id = pc.post_id
                    LEFT JOIN post_likes pl2 ON p.id = pl2.post_id AND pl2.user_id = %s
                    WHERE p.is_public = true AND p.deleted_at IS NULL
                    GROUP BY p.id, u.nombre, u.apellido, u.avatar_url, pl2.id
                    ORDER BY p.created_at DESC
                    LIMIT %s OFFSET %s
                """, [request.user.userid, limit, offset])
                
                columns = [col[0] for col in cursor.description]
                posts = []
                for row in cursor.fetchall():
                    post_dict = dict(zip(columns, row))
                    posts.append({
                        "id": str(post_dict['id']),
                        "user_id": str(post_dict['user_id']),
                        "content": post_dict['content'],
                        "image_url": post_dict['image_url'],
                        "video_url": post_dict['video_url'],
                        "location": post_dict['location'],
                        "is_public": post_dict['is_public'],
                        "created_at": post_dict['created_at'].isoformat(),
                        "author": {
                            "nombre": post_dict['nombre'],
                            "apellido": post_dict['apellido'],
                            "avatar_url": post_dict['avatar_url']
                        },
                        "likes_count": post_dict['likes_count'],
                        "comments_count": post_dict['comments_count'],
                        "is_liked": post_dict['is_liked']
                    })
                
                return Response({"posts": posts})
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """Crear un nuevo post"""
        try:
            # Debug: Verificar configuración de Supabase
            if not debug_supabase_config():
                return Response({"error": "Supabase configuration not found. Check .env file"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            post_id = str(uuid.uuid4())
            content = request.data.get('content', '')
            location = request.data.get('location', '')
            is_public = request.data.get('is_public', True)
            
            # Manejar archivo si existe
            file_url = None
            if 'file' in request.FILES:
                try:
                    supabase = get_supabase_admin()
                    file = request.FILES['file']
                    file_content = file.read()
                    file_path = f"{request.user.userid}/{post_id}_{file.name}"
                    
                    # Subir a Supabase Storage
                    result = supabase.storage.from_("jetgo-posts").upload(file_path, file_content)
                    
                    if result.get('error'):
                        return Response({"error": "Error uploading file"}, status=status.HTTP_400_BAD_REQUEST)
                    
                    file_url = supabase.storage.from_("jetgo-posts").get_public_url(file_path)
                except Exception as e:
                    return Response({"error": f"Supabase error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO posts (id, user_id, content, image_url, video_url, location, is_public, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, [
                    post_id,
                    request.user.userid,
                    content,
                    file_url if file_url and 'image' in request.FILES.get('file', {}).content_type else None,
                    file_url if file_url and 'video' in request.FILES.get('file', {}).content_type else None,
                    location,
                    is_public,
                    datetime.utcnow()
                ])
            
            return Response({"message": "Post created successfully", "post_id": post_id})
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PostLikeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, post_id):
        """Dar like a un post"""
        try:
            with connection.cursor() as cursor:
                # Verificar si ya existe el like
                cursor.execute("""
                    SELECT id FROM post_likes 
                    WHERE post_id = %s AND user_id = %s
                """, [post_id, request.user.userid])
                
                existing_like = cursor.fetchone()
                
                if existing_like:
                    # Quitar like
                    cursor.execute("""
                        DELETE FROM post_likes 
                        WHERE post_id = %s AND user_id = %s
                    """, [post_id, request.user.userid])
                    action = "unliked"
                else:
                    # Agregar like
                    like_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO post_likes (id, post_id, user_id, created_at)
                        VALUES (%s, %s, %s, %s)
                    """, [like_id, post_id, request.user.userid, datetime.utcnow()])
                    action = "liked"
            
            return Response({"action": action})
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CommentListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, post_id):
        """Obtener comentarios de un post"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT pc.*, u.nombre, u.apellido, u.avatar_url,
                           COUNT(cl.id) as likes_count,
                           CASE WHEN cl2.id IS NOT NULL THEN true ELSE false END as is_liked
                    FROM post_comments pc
                    JOIN "User" u ON pc.user_id = u.userid
                    LEFT JOIN comment_likes cl ON pc.id = cl.comment_id
                    LEFT JOIN comment_likes cl2 ON pc.id = cl2.comment_id AND cl2.user_id = %s
                    WHERE pc.post_id = %s AND pc.deleted_at IS NULL
                    GROUP BY pc.id, u.nombre, u.apellido, u.avatar_url, cl2.id
                    ORDER BY pc.created_at ASC
                """, [request.user.userid, post_id])
                
                columns = [col[0] for col in cursor.description]
                comments = []
                for row in cursor.fetchall():
                    comment_dict = dict(zip(columns, row))
                    comments.append({
                        "id": str(comment_dict['id']),
                        "post_id": str(comment_dict['post_id']),
                        "user_id": str(comment_dict['user_id']),
                        "content": comment_dict['content'],
                        "parent_comment_id": str(comment_dict['parent_comment_id']) if comment_dict['parent_comment_id'] else None,
                        "created_at": comment_dict['created_at'].isoformat(),
                        "author": {
                            "nombre": comment_dict['nombre'],
                            "apellido": comment_dict['apellido'],
                            "avatar_url": comment_dict['avatar_url']
                        },
                        "likes_count": comment_dict['likes_count'],
                        "is_liked": comment_dict['is_liked']
                    })
                
                return Response({"comments": comments})
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, post_id):
        """Crear comentario en un post"""
        try:
            comment_id = str(uuid.uuid4())
            content = request.data.get('content', '')
            parent_comment_id = request.data.get('parent_comment_id')
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO post_comments (id, post_id, user_id, content, parent_comment_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, [comment_id, post_id, request.user.userid, content, parent_comment_id, datetime.utcnow()])
            
            return Response({"message": "Comment created successfully", "comment_id": comment_id})
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StoryListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Obtener stories activas"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT s.*, u.nombre, u.apellido, u.avatar_url,
                           COUNT(sv.id) as views_count,
                           CASE WHEN sv2.id IS NOT NULL THEN true ELSE false END as is_viewed
                    FROM stories s
                    JOIN "User" u ON s.user_id = u.userid
                    LEFT JOIN story_views sv ON s.id = sv.story_id
                    LEFT JOIN story_views sv2 ON s.id = sv2.story_id AND sv2.viewer_id = %s
                    WHERE s.expires_at > NOW() AND s.is_archived = false
                    GROUP BY s.id, u.nombre, u.apellido, u.avatar_url, sv2.id
                    ORDER BY s.created_at DESC
                """, [request.user.userid])
                
                columns = [col[0] for col in cursor.description]
                stories = []
                for row in cursor.fetchall():
                    story_dict = dict(zip(columns, row))
                    stories.append({
                        "id": str(story_dict['id']),
                        "user_id": str(story_dict['user_id']),
                        "content": story_dict['content'],
                        "media_url": story_dict['media_url'],
                        "media_type": story_dict['media_type'],
                        "background_color": story_dict['background_color'],
                        "text_color": story_dict['text_color'],
                        "font_family": story_dict['font_family'],
                        "expires_at": story_dict['expires_at'].isoformat(),
                        "created_at": story_dict['created_at'].isoformat(),
                        "author": {
                            "nombre": story_dict['nombre'],
                            "apellido": story_dict['apellido'],
                            "avatar_url": story_dict['avatar_url']
                        },
                        "views_count": story_dict['views_count'],
                        "is_viewed": story_dict['is_viewed']
                    })
                
                return Response({"stories": stories})
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """Crear una nueva story"""
        try:
            # Debug: Verificar configuración de Supabase
            if not debug_supabase_config():
                return Response({"error": "Supabase configuration not found. Check .env file"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            story_id = str(uuid.uuid4())
            content = request.data.get('content', '')
            background_color = request.data.get('background_color')
            text_color = request.data.get('text_color')
            font_family = request.data.get('font_family')
            
            # Manejar archivo
            if 'file' not in request.FILES:
                return Response({"error": "File is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                supabase = get_supabase_admin()
                file = request.FILES['file']
                file_content = file.read()
                file_path = f"{request.user.userid}/{story_id}_{file.name}"
                
                # Subir a Supabase Storage
                result = supabase.storage.from_("jetgo-stories").upload(file_path, file_content)
                
                if result.get('error'):
                    return Response({"error": "Error uploading story file"}, status=status.HTTP_400_BAD_REQUEST)
                
                file_url = supabase.storage.from_("jetgo-stories").get_public_url(file_path)
            except Exception as e:
                return Response({"error": f"Supabase error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Calcular fecha de expiración (24 horas)
            expires_at = datetime.utcnow() + timedelta(hours=24)
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO stories (id, user_id, content, media_url, media_type, background_color, text_color, font_family, expires_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [
                    story_id,
                    request.user.userid,
                    content,
                    file_url,
                    "image" if file.content_type.startswith('image/') else "video",
                    background_color,
                    text_color,
                    font_family,
                    expires_at,
                    datetime.utcnow()
                ])
            
            return Response({"message": "Story created successfully", "story_id": story_id})
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StoryViewView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, story_id):
        """Marcar story como vista"""
        try:
            with connection.cursor() as cursor:
                # Verificar si ya fue vista
                cursor.execute("""
                    SELECT id FROM story_views 
                    WHERE story_id = %s AND viewer_id = %s
                """, [story_id, request.user.userid])
                
                existing_view = cursor.fetchone()
                
                if not existing_view:
                    # Agregar vista
                    view_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO story_views (id, story_id, viewer_id, viewed_at)
                        VALUES (%s, %s, %s, %s)
                    """, [view_id, story_id, request.user.userid, datetime.utcnow()])
            
            return Response({"message": "Story viewed"})
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FollowUserView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, user_id):
        """Seguir a un usuario"""
        try:
            if user_id == str(request.user.userid):
                return Response({"error": "Cannot follow yourself"}, status=status.HTTP_400_BAD_REQUEST)
            
            with connection.cursor() as cursor:
                # Verificar si ya existe el follow
                cursor.execute("""
                    SELECT id FROM user_follows 
                    WHERE follower_id = %s AND following_id = %s
                """, [request.user.userid, user_id])
                
                existing_follow = cursor.fetchone()
                
                if existing_follow:
                    # Dejar de seguir
                    cursor.execute("""
                        DELETE FROM user_follows 
                        WHERE follower_id = %s AND following_id = %s
                    """, [request.user.userid, user_id])
                    action = "unfollowed"
                else:
                    # Seguir
                    follow_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO user_follows (id, follower_id, following_id, created_at)
                        VALUES (%s, %s, %s, %s)
                    """, [follow_id, request.user.userid, user_id, datetime.utcnow()])
                    action = "followed"
            
            return Response({"action": action})
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FollowersListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, user_id):
        """Obtener seguidores de un usuario"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT u.userid, u.nombre, u.apellido, u.avatar_url, uf.created_at,
                           CASE WHEN uf2.id IS NOT NULL THEN true ELSE false END as is_following
                    FROM user_follows uf
                    JOIN "User" u ON uf.follower_id = u.userid
                    LEFT JOIN user_follows uf2 ON uf.follower_id = uf2.follower_id AND uf2.following_id = %s
                    WHERE uf.following_id = %s
                    ORDER BY uf.created_at DESC
                """, [request.user.userid, user_id])
                
                columns = [col[0] for col in cursor.description]
                followers = []
                for row in cursor.fetchall():
                    follower_dict = dict(zip(columns, row))
                    followers.append({
                        "user_id": str(follower_dict['userid']),
                        "nombre": follower_dict['nombre'],
                        "apellido": follower_dict['apellido'],
                        "avatar_url": follower_dict['avatar_url'],
                        "followed_at": follower_dict['created_at'].isoformat(),
                        "is_following": follower_dict['is_following']
                    })
                
                return Response({"followers": followers})
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FollowingListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, user_id):
        """Obtener usuarios que sigue un usuario"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT u.userid, u.nombre, u.apellido, u.avatar_url, uf.created_at,
                           CASE WHEN uf2.id IS NOT NULL THEN true ELSE false END as is_following
                    FROM user_follows uf
                    JOIN "User" u ON uf.following_id = u.userid
                    LEFT JOIN user_follows uf2 ON uf.following_id = uf2.follower_id AND uf2.following_id = %s
                    WHERE uf.follower_id = %s
                    ORDER BY uf.created_at DESC
                """, [request.user.userid, user_id])
                
                columns = [col[0] for col in cursor.description]
                following = []
                for row in cursor.fetchall():
                    following_dict = dict(zip(columns, row))
                    following.append({
                        "user_id": str(following_dict['userid']),
                        "nombre": following_dict['nombre'],
                        "apellido": following_dict['apellido'],
                        "avatar_url": following_dict['avatar_url'],
                        "followed_at": following_dict['created_at'].isoformat(),
                        "is_following": following_dict['is_following']
                    })
                
                return Response({"following": following})
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Obtener notificaciones del usuario"""
        try:
            limit = int(request.GET.get('limit', 20))
            offset = int(request.GET.get('offset', 0))
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT sn.*, u.nombre, u.apellido, u.avatar_url
                    FROM social_notifications sn
                    JOIN "User" u ON sn.from_user_id = u.userid
                    WHERE sn.user_id = %s
                    ORDER BY sn.created_at DESC
                    LIMIT %s OFFSET %s
                """, [request.user.userid, limit, offset])
                
                columns = [col[0] for col in cursor.description]
                notifications = []
                for row in cursor.fetchall():
                    notification_dict = dict(zip(columns, row))
                    notifications.append({
                        "id": str(notification_dict['id']),
                        "type": notification_dict['type'],
                        "is_read": notification_dict['is_read'],
                        "created_at": notification_dict['created_at'].isoformat(),
                        "read_at": notification_dict['read_at'].isoformat() if notification_dict['read_at'] else None,
                        "from_user": {
                            "user_id": str(notification_dict['from_user_id']),
                            "nombre": notification_dict['nombre'],
                            "apellido": notification_dict['apellido'],
                            "avatar_url": notification_dict['avatar_url']
                        },
                        "post_id": str(notification_dict['post_id']) if notification_dict['post_id'] else None,
                        "comment_id": str(notification_dict['comment_id']) if notification_dict['comment_id'] else None,
                        "story_id": str(notification_dict['story_id']) if notification_dict['story_id'] else None
                    })
                
                return Response({"notifications": notifications})
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, notification_id):
        """Marcar notificación como leída"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE social_notifications 
                    SET is_read = true, read_at = %s
                    WHERE id = %s AND user_id = %s
                """, [datetime.utcnow(), notification_id, request.user.userid])
            
            return Response({"message": "Notification marked as read"})
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
