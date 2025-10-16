from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import text, desc, and_, or_
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
import json
import os
from supabase import create_client, Client
import base64

from database import get_db
from auth import get_current_user
from models import User

router = APIRouter(prefix="/api/social", tags=["social"])

# Configuración de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================================================
# ENDPOINTS PARA POSTS
# =====================================================

@router.post("/posts")
async def create_post(
    content: str = Form(...),
    location: Optional[str] = Form(None),
    is_public: bool = Form(True),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear un nuevo post"""
    try:
        post_id = str(uuid.uuid4())
        file_url = None
        
        # Si hay archivo, subirlo a Supabase Storage
        if file:
            file_content = await file.read()
            file_path = f"{current_user.userid}/{post_id}_{file.filename}"
            
            # Determinar bucket según tipo de archivo
            bucket_name = "jetgo-posts"
            if file.content_type.startswith('video/'):
                bucket_name = "jetgo-posts"
            
            # Subir archivo
            result = supabase.storage.from_(bucket_name).upload(file_path, file_content)
            
            if result.get('error'):
                raise HTTPException(status_code=400, detail="Error uploading file")
            
            # Obtener URL pública
            file_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
        
        # Crear post en la base de datos
        query = text("""
            INSERT INTO posts (id, user_id, content, image_url, video_url, location, is_public, created_at)
            VALUES (:id, :user_id, :content, :image_url, :video_url, :location, :is_public, :created_at)
        """)
        
        db.execute(query, {
            "id": post_id,
            "user_id": current_user.userid,
            "content": content,
            "image_url": file_url if file and file.content_type.startswith('image/') else None,
            "video_url": file_url if file and file.content_type.startswith('video/') else None,
            "location": location,
            "is_public": is_public,
            "created_at": datetime.utcnow()
        })
        db.commit()
        
        return {"message": "Post created successfully", "post_id": post_id}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/posts")
async def get_posts(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener posts del feed"""
    try:
        query = text("""
            SELECT p.*, u.nombre, u.apellido, u.avatar_url,
                   COUNT(pl.id) as likes_count,
                   COUNT(pc.id) as comments_count,
                   CASE WHEN pl2.id IS NOT NULL THEN true ELSE false END as is_liked
            FROM posts p
            JOIN "User" u ON p.user_id = u.userid
            LEFT JOIN post_likes pl ON p.id = pl.post_id
            LEFT JOIN post_comments pc ON p.id = pc.post_id
            LEFT JOIN post_likes pl2 ON p.id = pl2.post_id AND pl2.user_id = :user_id
            WHERE p.is_public = true AND p.deleted_at IS NULL
            GROUP BY p.id, u.nombre, u.apellido, u.avatar_url, pl2.id
            ORDER BY p.created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        
        result = db.execute(query, {
            "user_id": current_user.userid,
            "limit": limit,
            "offset": offset
        }).fetchall()
        
        posts = []
        for row in result:
            posts.append({
                "id": str(row.id),
                "user_id": str(row.user_id),
                "content": row.content,
                "image_url": row.image_url,
                "video_url": row.video_url,
                "location": row.location,
                "is_public": row.is_public,
                "created_at": row.created_at.isoformat(),
                "author": {
                    "nombre": row.nombre,
                    "apellido": row.apellido,
                    "avatar_url": row.avatar_url
                },
                "likes_count": row.likes_count,
                "comments_count": row.comments_count,
                "is_liked": row.is_liked
            })
        
        return {"posts": posts}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/posts/{post_id}/like")
async def like_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dar like a un post"""
    try:
        # Verificar si ya existe el like
        check_query = text("SELECT id FROM post_likes WHERE post_id = :post_id AND user_id = :user_id")
        existing_like = db.execute(check_query, {
            "post_id": post_id,
            "user_id": current_user.userid
        }).fetchone()
        
        if existing_like:
            # Quitar like
            delete_query = text("DELETE FROM post_likes WHERE post_id = :post_id AND user_id = :user_id")
            db.execute(delete_query, {
                "post_id": post_id,
                "user_id": current_user.userid
            })
            action = "unliked"
        else:
            # Agregar like
            like_id = str(uuid.uuid4())
            insert_query = text("""
                INSERT INTO post_likes (id, post_id, user_id, created_at)
                VALUES (:id, :post_id, :user_id, :created_at)
            """)
            db.execute(insert_query, {
                "id": like_id,
                "post_id": post_id,
                "user_id": current_user.userid,
                "created_at": datetime.utcnow()
            })
            action = "liked"
        
        db.commit()
        return {"action": action}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# ENDPOINTS PARA STORIES
# =====================================================

@router.post("/stories")
async def create_story(
    content: Optional[str] = Form(None),
    background_color: Optional[str] = Form(None),
    text_color: Optional[str] = Form(None),
    font_family: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear una nueva story"""
    try:
        story_id = str(uuid.uuid4())
        
        # Subir archivo a Supabase Storage
        file_content = await file.read()
        file_path = f"{current_user.userid}/{story_id}_{file.filename}"
        
        # Subir a bucket de stories
        result = supabase.storage.from_("jetgo-stories").upload(file_path, file_content)
        
        if result.get('error'):
            raise HTTPException(status_code=400, detail="Error uploading story file")
        
        # Obtener URL pública
        file_url = supabase.storage.from_("jetgo-stories").get_public_url(file_path)
        
        # Calcular fecha de expiración (24 horas)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Crear story en la base de datos
        query = text("""
            INSERT INTO stories (id, user_id, content, media_url, media_type, background_color, text_color, font_family, expires_at, created_at)
            VALUES (:id, :user_id, :content, :media_url, :media_type, :background_color, :text_color, :font_family, :expires_at, :created_at)
        """)
        
        db.execute(query, {
            "id": story_id,
            "user_id": current_user.userid,
            "content": content,
            "media_url": file_url,
            "media_type": "image" if file.content_type.startswith('image/') else "video",
            "background_color": background_color,
            "text_color": text_color,
            "font_family": font_family,
            "expires_at": expires_at,
            "created_at": datetime.utcnow()
        })
        db.commit()
        
        return {"message": "Story created successfully", "story_id": story_id}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stories")
async def get_stories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener stories activas"""
    try:
        query = text("""
            SELECT s.*, u.nombre, u.apellido, u.avatar_url,
                   COUNT(sv.id) as views_count,
                   CASE WHEN sv2.id IS NOT NULL THEN true ELSE false END as is_viewed
            FROM stories s
            JOIN "User" u ON s.user_id = u.userid
            LEFT JOIN story_views sv ON s.id = sv.story_id
            LEFT JOIN story_views sv2 ON s.id = sv2.story_id AND sv2.viewer_id = :user_id
            WHERE s.expires_at > NOW() AND s.is_archived = false
            GROUP BY s.id, u.nombre, u.apellido, u.avatar_url, sv2.id
            ORDER BY s.created_at DESC
        """)
        
        result = db.execute(query, {
            "user_id": current_user.userid
        }).fetchall()
        
        stories = []
        for row in result:
            stories.append({
                "id": str(row.id),
                "user_id": str(row.user_id),
                "content": row.content,
                "media_url": row.media_url,
                "media_type": row.media_type,
                "background_color": row.background_color,
                "text_color": row.text_color,
                "font_family": row.font_family,
                "expires_at": row.expires_at.isoformat(),
                "created_at": row.created_at.isoformat(),
                "author": {
                    "nombre": row.nombre,
                    "apellido": row.apellido,
                    "avatar_url": row.avatar_url
                },
                "views_count": row.views_count,
                "is_viewed": row.is_viewed
            })
        
        return {"stories": stories}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stories/{story_id}/view")
async def view_story(
    story_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Marcar story como vista"""
    try:
        # Verificar si ya fue vista
        check_query = text("SELECT id FROM story_views WHERE story_id = :story_id AND viewer_id = :viewer_id")
        existing_view = db.execute(check_query, {
            "story_id": story_id,
            "viewer_id": current_user.userid
        }).fetchone()
        
        if not existing_view:
            # Agregar vista
            view_id = str(uuid.uuid4())
            insert_query = text("""
                INSERT INTO story_views (id, story_id, viewer_id, viewed_at)
                VALUES (:id, :story_id, :viewer_id, :viewed_at)
            """)
            db.execute(insert_query, {
                "id": view_id,
                "story_id": story_id,
                "viewer_id": current_user.userid,
                "viewed_at": datetime.utcnow()
            })
            db.commit()
        
        return {"message": "Story viewed"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# ENDPOINTS PARA COMENTARIOS
# =====================================================

@router.post("/posts/{post_id}/comments")
async def create_comment(
    post_id: str,
    content: str = Form(...),
    parent_comment_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear comentario en un post"""
    try:
        comment_id = str(uuid.uuid4())
        
        query = text("""
            INSERT INTO post_comments (id, post_id, user_id, content, parent_comment_id, created_at)
            VALUES (:id, :post_id, :user_id, :content, :parent_comment_id, :created_at)
        """)
        
        db.execute(query, {
            "id": comment_id,
            "post_id": post_id,
            "user_id": current_user.userid,
            "content": content,
            "parent_comment_id": parent_comment_id,
            "created_at": datetime.utcnow()
        })
        db.commit()
        
        return {"message": "Comment created successfully", "comment_id": comment_id}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/posts/{post_id}/comments")
async def get_comments(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener comentarios de un post"""
    try:
        query = text("""
            SELECT pc.*, u.nombre, u.apellido, u.avatar_url,
                   COUNT(cl.id) as likes_count,
                   CASE WHEN cl2.id IS NOT NULL THEN true ELSE false END as is_liked
            FROM post_comments pc
            JOIN "User" u ON pc.user_id = u.userid
            LEFT JOIN comment_likes cl ON pc.id = cl.comment_id
            LEFT JOIN comment_likes cl2 ON pc.id = cl2.comment_id AND cl2.user_id = :user_id
            WHERE pc.post_id = :post_id AND pc.deleted_at IS NULL
            GROUP BY pc.id, u.nombre, u.apellido, u.avatar_url, cl2.id
            ORDER BY pc.created_at ASC
        """)
        
        result = db.execute(query, {
            "post_id": post_id,
            "user_id": current_user.userid
        }).fetchall()
        
        comments = []
        for row in result:
            comments.append({
                "id": str(row.id),
                "post_id": str(row.post_id),
                "user_id": str(row.user_id),
                "content": row.content,
                "parent_comment_id": str(row.parent_comment_id) if row.parent_comment_id else None,
                "created_at": row.created_at.isoformat(),
                "author": {
                    "nombre": row.nombre,
                    "apellido": row.apellido,
                    "avatar_url": row.avatar_url
                },
                "likes_count": row.likes_count,
                "is_liked": row.is_liked
            })
        
        return {"comments": comments}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# ENDPOINTS PARA FOLLOWS
# =====================================================

@router.post("/users/{user_id}/follow")
async def follow_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Seguir a un usuario"""
    try:
        if user_id == str(current_user.userid):
            raise HTTPException(status_code=400, detail="Cannot follow yourself")
        
        # Verificar si ya existe el follow
        check_query = text("SELECT id FROM user_follows WHERE follower_id = :follower_id AND following_id = :following_id")
        existing_follow = db.execute(check_query, {
            "follower_id": current_user.userid,
            "following_id": user_id
        }).fetchone()
        
        if existing_follow:
            # Dejar de seguir
            delete_query = text("DELETE FROM user_follows WHERE follower_id = :follower_id AND following_id = :following_id")
            db.execute(delete_query, {
                "follower_id": current_user.userid,
                "following_id": user_id
            })
            action = "unfollowed"
        else:
            # Seguir
            follow_id = str(uuid.uuid4())
            insert_query = text("""
                INSERT INTO user_follows (id, follower_id, following_id, created_at)
                VALUES (:id, :follower_id, :following_id, :created_at)
            """)
            db.execute(insert_query, {
                "id": follow_id,
                "follower_id": current_user.userid,
                "following_id": user_id,
                "created_at": datetime.utcnow()
            })
            action = "followed"
        
        db.commit()
        return {"action": action}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}/followers")
async def get_followers(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener seguidores de un usuario"""
    try:
        query = text("""
            SELECT u.userid, u.nombre, u.apellido, u.avatar_url, uf.created_at,
                   CASE WHEN uf2.id IS NOT NULL THEN true ELSE false END as is_following
            FROM user_follows uf
            JOIN "User" u ON uf.follower_id = u.userid
            LEFT JOIN user_follows uf2 ON uf.follower_id = uf2.follower_id AND uf2.following_id = :current_user_id
            WHERE uf.following_id = :user_id
            ORDER BY uf.created_at DESC
        """)
        
        result = db.execute(query, {
            "user_id": user_id,
            "current_user_id": current_user.userid
        }).fetchall()
        
        followers = []
        for row in result:
            followers.append({
                "user_id": str(row.userid),
                "nombre": row.nombre,
                "apellido": row.apellido,
                "avatar_url": row.avatar_url,
                "followed_at": row.created_at.isoformat(),
                "is_following": row.is_following
            })
        
        return {"followers": followers}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}/following")
async def get_following(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener usuarios que sigue un usuario"""
    try:
        query = text("""
            SELECT u.userid, u.nombre, u.apellido, u.avatar_url, uf.created_at,
                   CASE WHEN uf2.id IS NOT NULL THEN true ELSE false END as is_following
            FROM user_follows uf
            JOIN "User" u ON uf.following_id = u.userid
            LEFT JOIN user_follows uf2 ON uf.following_id = uf2.follower_id AND uf2.following_id = :current_user_id
            WHERE uf.follower_id = :user_id
            ORDER BY uf.created_at DESC
        """)
        
        result = db.execute(query, {
            "user_id": user_id,
            "current_user_id": current_user.userid
        }).fetchall()
        
        following = []
        for row in result:
            following.append({
                "user_id": str(row.userid),
                "nombre": row.nombre,
                "apellido": row.apellido,
                "avatar_url": row.avatar_url,
                "followed_at": row.created_at.isoformat(),
                "is_following": row.is_following
            })
        
        return {"following": following}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# ENDPOINTS PARA NOTIFICACIONES
# =====================================================

@router.get("/notifications")
async def get_notifications(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener notificaciones del usuario"""
    try:
        query = text("""
            SELECT sn.*, u.nombre, u.apellido, u.avatar_url
            FROM social_notifications sn
            JOIN "User" u ON sn.from_user_id = u.userid
            WHERE sn.user_id = :user_id
            ORDER BY sn.created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        
        result = db.execute(query, {
            "user_id": current_user.userid,
            "limit": limit,
            "offset": offset
        }).fetchall()
        
        notifications = []
        for row in result:
            notifications.append({
                "id": str(row.id),
                "type": row.type,
                "is_read": row.is_read,
                "created_at": row.created_at.isoformat(),
                "read_at": row.read_at.isoformat() if row.read_at else None,
                "from_user": {
                    "user_id": str(row.from_user_id),
                    "nombre": row.nombre,
                    "apellido": row.apellido,
                    "avatar_url": row.avatar_url
                },
                "post_id": str(row.post_id) if row.post_id else None,
                "comment_id": str(row.comment_id) if row.comment_id else None,
                "story_id": str(row.story_id) if row.story_id else None
            })
        
        return {"notifications": notifications}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Marcar notificación como leída"""
    try:
        query = text("""
            UPDATE social_notifications 
            SET is_read = true, read_at = :read_at
            WHERE id = :notification_id AND user_id = :user_id
        """)
        
        db.execute(query, {
            "notification_id": notification_id,
            "user_id": current_user.userid,
            "read_at": datetime.utcnow()
        })
        db.commit()
        
        return {"message": "Notification marked as read"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
