from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
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
from supabase import create_client

def debug_supabase_config():
    """Debug function to check Supabase configuration"""
    url = os.environ.get('SUPABASE_URL')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    anon_key = os.environ.get('SUPABASE_ANON_KEY')
    
    print(f"SUPABASE_URL: {url}")
    print(f"SUPABASE_SERVICE_ROLE_KEY: {service_key[:10] if service_key else 'None'}...")
    print(f"SUPABASE_ANON_KEY: {anon_key[:10] if anon_key else 'None'}...")
    
    return url and service_key and anon_key

def get_supabase_client():
    """Get Supabase client with direct connection"""
    url = os.environ.get('SUPABASE_URL')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    
    if not url or not service_key:
        # Fallback to hardcoded values for development
        # IMPORTANT: Replace these with your actual Supabase credentials
        url = "https://your-project.supabase.co"  # Replace with your Supabase URL
        service_key = "your-service-role-key"    # Replace with your service role key
    
    return create_client(url, service_key)

class PostListCreateView(APIView):
    authentication_classes = []
    permission_classes = []
    
    def options(self, request, *args, **kwargs):
        """Handle preflight requests"""
        return Response(status=status.HTTP_200_OK)
    
    def get(self, request):
        """Obtener posts del feed"""
        try:
            limit = int(request.GET.get('limit', 20))
            offset = int(request.GET.get('offset', 0))
            
            # Use Supabase directly
            supabase = get_supabase_client()
            
            # Get posts first
            posts_response = supabase.table('posts').select('*').eq('is_public', True).is_('deleted_at', 'null').order('created_at', desc=True).limit(limit).offset(offset).execute()
            
            posts = []
            for post in posts_response.data:
                # Get user information separately
                user_response = supabase.table('User').select('nombre, apellido, avatar_url').eq('userid', post['user_id']).execute()
                user_data = user_response.data[0] if user_response.data else None
                
                # Get likes count
                likes_response = supabase.table('post_likes').select('id', count='exact').eq('post_id', post['id']).execute()
                likes_count = likes_response.count if likes_response.count else 0
                
                # Get comments count
                comments_response = supabase.table('post_comments').select('id', count='exact').eq('post_id', post['id']).is_('deleted_at', 'null').execute()
                comments_count = comments_response.count if comments_response.count else 0
                
                posts.append({
                    "id": str(post['id']),
                    "user_id": str(post['user_id']),
                    "content": post['content'],
                    "image_url": post['image_url'],
                    "video_url": post['video_url'],
                    "location": post['location'],
                    "is_public": post['is_public'],
                    "created_at": post['created_at'],
                    "author": {
                        "nombre": user_data['nombre'] if user_data else 'Usuario',
                        "apellido": user_data['apellido'] if user_data else '',
                        "avatar_url": user_data['avatar_url'] if user_data else None
                    },
                    "likes_count": likes_count,
                    "comments_count": comments_count,
                    "is_liked": False  # TODO: Implement user-specific like status
                })
            
            return Response({"posts": posts})
                
        except Exception as e:
            print(f"Error in PostListCreateView GET: {str(e)}")
            return Response({"error": f"Supabase error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """Crear un nuevo post"""
        try:
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            post_id = str(uuid.uuid4())
            content = request.data.get('content', '')
            location = request.data.get('location', '')
            is_public = request.data.get('is_public', True)
            
            # Manejar archivo si existe
            file_url = None
            if 'file' in request.FILES:
                try:
                    supabase = get_supabase_client()
                    file = request.FILES['file']
                    
                    # Validar tipo de archivo
                    if not file.content_type.startswith(('image/', 'video/')):
                        return Response({"error": "Solo se permiten archivos de imagen o video"}, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Leer contenido del archivo
                    file_content = file.read()
                    
                    # Generar nombre de archivo único
                    file_extension = file.name.split('.')[-1] if '.' in file.name else 'jpg'
                    file_name = f"{post_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
                    file_path = f"{user_id}/{file_name}"
                    
                    # Subir a Supabase Storage
                    try:
                        result = supabase.storage.from_("jetgo-posts").upload(
                            file_path, 
                            file_content,
                            file_options={"content-type": file.content_type}
                        )
                        print(f"Upload result: {result}")
                        
                        # Obtener URL pública
                        file_url = supabase.storage.from_("jetgo-posts").get_public_url(file_path)
                        print(f"File URL: {file_url}")
                        
                    except Exception as upload_error:
                        print(f"Upload error: {upload_error}")
                        return Response({"error": f"Error uploading file: {str(upload_error)}"}, status=status.HTTP_400_BAD_REQUEST)
                        
                except Exception as e:
                    print(f"Supabase upload error: {str(e)}")
                    return Response({"error": f"Supabase error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Determinar si es imagen o video
            image_url = None
            video_url = None
            if file_url and 'file' in request.FILES:
                file = request.FILES['file']
                if file.content_type.startswith('image/'):
                    image_url = file_url
                elif file.content_type.startswith('video/'):
                    video_url = file_url
            
            # Insert post into Supabase
            supabase = get_supabase_client()
            post_data = {
                'id': post_id,
                'user_id': user_id,
                'content': content,
                'image_url': image_url,
                'video_url': video_url,
                'location': location,
                'is_public': is_public,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            result = supabase.table('posts').insert(post_data).execute()
            
            if result.data:
                return Response({"message": "Post created successfully", "post_id": post_id})
            else:
                return Response({"error": "Failed to create post"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            print(f"Error in PostListCreateView POST: {str(e)}")
            return Response({"error": f"Supabase error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PostLikeView(APIView):
    authentication_classes = []
    permission_classes = []
    
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
    authentication_classes = []
    permission_classes = []
    
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
    authentication_classes = []
    permission_classes = []
    
    def options(self, request, *args, **kwargs):
        """Handle preflight requests"""
        return Response(status=status.HTTP_200_OK)
    
    def get(self, request):
        """Obtener stories activas"""
        try:
            # Use Supabase directly
            supabase = get_supabase_client()
            
            # Get active stories first
            stories_response = supabase.table('stories').select('*').gt('expires_at', datetime.utcnow().isoformat()).eq('is_archived', False).order('created_at', desc=True).execute()
            
            stories = []
            for story in stories_response.data:
                # Get user information separately
                user_response = supabase.table('User').select('nombre, apellido, avatar_url').eq('userid', story['user_id']).execute()
                user_data = user_response.data[0] if user_response.data else None
                
                # Get views count
                views_response = supabase.table('story_views').select('id', count='exact').eq('story_id', story['id']).execute()
                views_count = views_response.count if views_response.count else 0
                
                stories.append({
                    "id": str(story['id']),
                    "user_id": str(story['user_id']),
                    "content": story['content'],
                    "media_url": story['media_url'],
                    "media_type": story['media_type'],
                    "background_color": story['background_color'],
                    "text_color": story['text_color'],
                    "font_family": story['font_family'],
                    "expires_at": story['expires_at'],
                    "created_at": story['created_at'],
                    "author": {
                        "nombre": user_data['nombre'] if user_data else 'Usuario',
                        "apellido": user_data['apellido'] if user_data else '',
                        "avatar_url": user_data['avatar_url'] if user_data else None
                    },
                    "views_count": views_count,
                    "is_viewed": False  # TODO: Implement user-specific view status
                })
            
            return Response({"stories": stories})
                
        except Exception as e:
            print(f"Error in StoryListCreateView GET: {str(e)}")
            return Response({"error": f"Supabase error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """Crear una nueva story"""
        try:
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            story_id = str(uuid.uuid4())
            content = request.data.get('content', '')
            background_color = request.data.get('background_color')
            text_color = request.data.get('text_color')
            font_family = request.data.get('font_family')
            
            # Manejar archivo
            if 'file' not in request.FILES:
                return Response({"error": "File is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                supabase = get_supabase_client()
                file = request.FILES['file']
                
                # Validar tipo de archivo
                if not file.content_type.startswith(('image/', 'video/')):
                    return Response({"error": "Solo se permiten archivos de imagen o video"}, status=status.HTTP_400_BAD_REQUEST)
                
                # Leer contenido del archivo
                file_content = file.read()
                
                # Generar nombre de archivo único
                file_extension = file.name.split('.')[-1] if '.' in file.name else 'jpg'
                file_name = f"{story_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
                file_path = f"{user_id}/{file_name}"
                
                # Subir a Supabase Storage
                try:
                    result = supabase.storage.from_("jetgo-stories").upload(
                        file_path, 
                        file_content,
                        file_options={"content-type": file.content_type}
                    )
                    print(f"Story upload result: {result}")
                    
                    # Obtener URL pública
                    file_url = supabase.storage.from_("jetgo-stories").get_public_url(file_path)
                    print(f"Story file URL: {file_url}")
                    
                except Exception as upload_error:
                    print(f"Story upload error: {upload_error}")
                    return Response({"error": f"Error uploading story file: {str(upload_error)}"}, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                print(f"Supabase upload error: {str(e)}")
                return Response({"error": f"Supabase error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Calcular fecha de expiración (24 horas)
            expires_at = datetime.utcnow() + timedelta(hours=24)
            
            # Insert story into Supabase
            story_data = {
                'id': story_id,
                'user_id': user_id,
                'content': content,
                'media_url': file_url,
                'media_type': "image" if file.content_type.startswith('image/') else "video",
                'background_color': background_color,
                'text_color': text_color,
                'font_family': font_family,
                'expires_at': expires_at.isoformat(),
                'created_at': datetime.utcnow().isoformat(),
                'is_archived': False
            }
            
            result = supabase.table('stories').insert(story_data).execute()
            
            if result.data:
                return Response({"message": "Story created successfully", "story_id": story_id})
            else:
                return Response({"error": "Failed to create story"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            print(f"Error in StoryListCreateView POST: {str(e)}")
            return Response({"error": f"Supabase error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StoryViewView(APIView):
    authentication_classes = []
    permission_classes = []
    
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
    authentication_classes = []
    permission_classes = []
    
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
    authentication_classes = []
    permission_classes = []
    
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
    authentication_classes = []
    permission_classes = []
    
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
    authentication_classes = []
    permission_classes = []
    
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
    authentication_classes = []
    permission_classes = []
    
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

# Vista de prueba simple
class TestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response({"message": "Test endpoint working!", "status": "success"})
