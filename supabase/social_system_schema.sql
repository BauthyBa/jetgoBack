-- =====================================================
-- SISTEMA SOCIAL JETGO - ESQUEMA COMPLETO
-- =====================================================
-- Este archivo contiene todas las tablas necesarias para un sistema social
-- similar a Instagram con posts, stories, likes, comentarios y seguimiento

-- =====================================================
-- 1. TABLA DE POSTS (Publicaciones principales)
-- =====================================================
CREATE TABLE public.posts (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    content text,
    image_url text,
    video_url text,
    location text,
    is_public boolean DEFAULT true,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    deleted_at timestamp with time zone,
    
    CONSTRAINT posts_pkey PRIMARY KEY (id),
    CONSTRAINT posts_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
);

-- =====================================================
-- 2. TABLA DE STORIES (Historias que duran 24h)
-- =====================================================
CREATE TABLE public.stories (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    content text,
    media_url text NOT NULL,
    media_type text NOT NULL CHECK (media_type IN ('image', 'video')),
    background_color text,
    text_color text,
    font_family text,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    is_archived boolean DEFAULT false,
    
    CONSTRAINT stories_pkey PRIMARY KEY (id),
    CONSTRAINT stories_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
);

-- =====================================================
-- 3. TABLA DE LIKES (Me gusta en posts)
-- =====================================================
CREATE TABLE public.post_likes (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    post_id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    
    CONSTRAINT post_likes_pkey PRIMARY KEY (id),
    CONSTRAINT post_likes_post_fk FOREIGN KEY (post_id) REFERENCES public.posts(id) ON DELETE CASCADE,
    CONSTRAINT post_likes_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
    CONSTRAINT post_likes_unique UNIQUE (post_id, user_id)
);

-- =====================================================
-- 4. TABLA DE COMENTARIOS EN POSTS
-- =====================================================
CREATE TABLE public.post_comments (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    post_id uuid NOT NULL,
    user_id uuid NOT NULL,
    content text NOT NULL,
    parent_comment_id uuid,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    deleted_at timestamp with time zone,
    
    CONSTRAINT post_comments_pkey PRIMARY KEY (id),
    CONSTRAINT post_comments_post_fk FOREIGN KEY (post_id) REFERENCES public.posts(id) ON DELETE CASCADE,
    CONSTRAINT post_comments_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
    CONSTRAINT post_comments_parent_fk FOREIGN KEY (parent_comment_id) REFERENCES public.post_comments(id) ON DELETE CASCADE
);

-- =====================================================
-- 5. TABLA DE SEGUIMIENTO (Follows/Followers)
-- =====================================================
CREATE TABLE public.user_follows (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    follower_id uuid NOT NULL,
    following_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    
    CONSTRAINT user_follows_pkey PRIMARY KEY (id),
    CONSTRAINT user_follows_follower_fk FOREIGN KEY (follower_id) REFERENCES auth.users(id) ON DELETE CASCADE,
    CONSTRAINT user_follows_following_fk FOREIGN KEY (following_id) REFERENCES auth.users(id) ON DELETE CASCADE,
    CONSTRAINT user_follows_unique UNIQUE (follower_id, following_id),
    CONSTRAINT user_follows_no_self_follow CHECK (follower_id != following_id)
);

-- =====================================================
-- 6. TABLA DE LIKES EN COMENTARIOS
-- =====================================================
CREATE TABLE public.comment_likes (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    comment_id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    
    CONSTRAINT comment_likes_pkey PRIMARY KEY (id),
    CONSTRAINT comment_likes_comment_fk FOREIGN KEY (comment_id) REFERENCES public.post_comments(id) ON DELETE CASCADE,
    CONSTRAINT comment_likes_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
    CONSTRAINT comment_likes_unique UNIQUE (comment_id, user_id)
);

-- =====================================================
-- 7. TABLA DE VISTAS DE STORIES
-- =====================================================
CREATE TABLE public.story_views (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    story_id uuid NOT NULL,
    viewer_id uuid NOT NULL,
    viewed_at timestamp with time zone NOT NULL DEFAULT now(),
    
    CONSTRAINT story_views_pkey PRIMARY KEY (id),
    CONSTRAINT story_views_story_fk FOREIGN KEY (story_id) REFERENCES public.stories(id) ON DELETE CASCADE,
    CONSTRAINT story_views_viewer_fk FOREIGN KEY (viewer_id) REFERENCES auth.users(id) ON DELETE CASCADE,
    CONSTRAINT story_views_unique UNIQUE (story_id, viewer_id)
);

-- =====================================================
-- 8. TABLA DE NOTIFICACIONES SOCIALES
-- =====================================================
CREATE TABLE public.social_notifications (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    from_user_id uuid NOT NULL,
    type text NOT NULL CHECK (type IN ('like', 'comment', 'follow', 'story_view', 'mention')),
    post_id uuid,
    comment_id uuid,
    story_id uuid,
    is_read boolean DEFAULT false,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    read_at timestamp with time zone,
    
    CONSTRAINT social_notifications_pkey PRIMARY KEY (id),
    CONSTRAINT social_notifications_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
    CONSTRAINT social_notifications_from_user_fk FOREIGN KEY (from_user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
    CONSTRAINT social_notifications_post_fk FOREIGN KEY (post_id) REFERENCES public.posts(id) ON DELETE CASCADE,
    CONSTRAINT social_notifications_comment_fk FOREIGN KEY (comment_id) REFERENCES public.post_comments(id) ON DELETE CASCADE,
    CONSTRAINT social_notifications_story_fk FOREIGN KEY (story_id) REFERENCES public.stories(id) ON DELETE CASCADE
);

-- =====================================================
-- 9. TABLA DE MENCIONES EN POSTS Y COMENTARIOS
-- =====================================================
CREATE TABLE public.mentions (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    post_id uuid,
    comment_id uuid,
    mentioned_user_id uuid NOT NULL,
    mentioned_by_user_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    
    CONSTRAINT mentions_pkey PRIMARY KEY (id),
    CONSTRAINT mentions_post_fk FOREIGN KEY (post_id) REFERENCES public.posts(id) ON DELETE CASCADE,
    CONSTRAINT mentions_comment_fk FOREIGN KEY (comment_id) REFERENCES public.post_comments(id) ON DELETE CASCADE,
    CONSTRAINT mentions_mentioned_user_fk FOREIGN KEY (mentioned_user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
    CONSTRAINT mentions_mentioned_by_fk FOREIGN KEY (mentioned_by_user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
    CONSTRAINT mentions_post_or_comment CHECK (
        (post_id IS NOT NULL AND comment_id IS NULL) OR 
        (post_id IS NULL AND comment_id IS NOT NULL)
    )
);

-- =====================================================
-- 10. TABLA DE HASHTAGS
-- =====================================================
CREATE TABLE public.hashtags (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    usage_count integer DEFAULT 0,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    
    CONSTRAINT hashtags_pkey PRIMARY KEY (id)
);

-- =====================================================
-- 11. TABLA DE RELACIÓN POST-HASHTAG
-- =====================================================
CREATE TABLE public.post_hashtags (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    post_id uuid NOT NULL,
    hashtag_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    
    CONSTRAINT post_hashtags_pkey PRIMARY KEY (id),
    CONSTRAINT post_hashtags_post_fk FOREIGN KEY (post_id) REFERENCES public.posts(id) ON DELETE CASCADE,
    CONSTRAINT post_hashtags_hashtag_fk FOREIGN KEY (hashtag_id) REFERENCES public.hashtags(id) ON DELETE CASCADE,
    CONSTRAINT post_hashtags_unique UNIQUE (post_id, hashtag_id)
);

-- =====================================================
-- ÍNDICES PARA OPTIMIZACIÓN
-- =====================================================

-- Índices para posts
CREATE INDEX idx_posts_user_id ON public.posts(user_id);
CREATE INDEX idx_posts_created_at ON public.posts(created_at DESC);
CREATE INDEX idx_posts_is_public ON public.posts(is_public);

-- Índices para stories
CREATE INDEX idx_stories_user_id ON public.stories(user_id);
CREATE INDEX idx_stories_expires_at ON public.stories(expires_at);
CREATE INDEX idx_stories_created_at ON public.stories(created_at DESC);

-- Índices para likes
CREATE INDEX idx_post_likes_post_id ON public.post_likes(post_id);
CREATE INDEX idx_post_likes_user_id ON public.post_likes(user_id);

-- Índices para comentarios
CREATE INDEX idx_post_comments_post_id ON public.post_comments(post_id);
CREATE INDEX idx_post_comments_user_id ON public.post_comments(user_id);
CREATE INDEX idx_post_comments_parent_id ON public.post_comments(parent_comment_id);

-- Índices para follows
CREATE INDEX idx_user_follows_follower ON public.user_follows(follower_id);
CREATE INDEX idx_user_follows_following ON public.user_follows(following_id);

-- Índices para notificaciones
CREATE INDEX idx_social_notifications_user_id ON public.social_notifications(user_id);
CREATE INDEX idx_social_notifications_is_read ON public.social_notifications(is_read);
CREATE INDEX idx_social_notifications_created_at ON public.social_notifications(created_at DESC);

-- =====================================================
-- FUNCIONES Y TRIGGERS
-- =====================================================

-- Función para limpiar stories expiradas
CREATE OR REPLACE FUNCTION cleanup_expired_stories()
RETURNS void AS $$
BEGIN
    DELETE FROM public.stories 
    WHERE expires_at < NOW() AND is_archived = false;
END;
$$ LANGUAGE plpgsql;

-- Función para actualizar contador de hashtags
CREATE OR REPLACE FUNCTION update_hashtag_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE public.hashtags 
        SET usage_count = usage_count + 1 
        WHERE id = NEW.hashtag_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE public.hashtags 
        SET usage_count = usage_count - 1 
        WHERE id = OLD.hashtag_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger para actualizar contador de hashtags
CREATE TRIGGER trigger_update_hashtag_count
    AFTER INSERT OR DELETE ON public.post_hashtags
    FOR EACH ROW EXECUTE FUNCTION update_hashtag_count();

-- Función para crear notificaciones automáticas
CREATE OR REPLACE FUNCTION create_social_notification()
RETURNS TRIGGER AS $$
BEGIN
    -- Notificación de like en post
    IF TG_TABLE_NAME = 'post_likes' THEN
        INSERT INTO public.social_notifications (user_id, from_user_id, type, post_id)
        SELECT p.user_id, NEW.user_id, 'like', NEW.post_id
        FROM public.posts p
        WHERE p.id = NEW.post_id AND p.user_id != NEW.user_id;
    END IF;
    
    -- Notificación de comentario en post
    IF TG_TABLE_NAME = 'post_comments' THEN
        INSERT INTO public.social_notifications (user_id, from_user_id, type, post_id, comment_id)
        SELECT p.user_id, NEW.user_id, 'comment', NEW.post_id, NEW.id
        FROM public.posts p
        WHERE p.id = NEW.post_id AND p.user_id != NEW.user_id;
    END IF;
    
    -- Notificación de follow
    IF TG_TABLE_NAME = 'user_follows' THEN
        INSERT INTO public.social_notifications (user_id, from_user_id, type)
        VALUES (NEW.following_id, NEW.follower_id, 'follow');
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para notificaciones automáticas
CREATE TRIGGER trigger_post_like_notification
    AFTER INSERT ON public.post_likes
    FOR EACH ROW EXECUTE FUNCTION create_social_notification();

CREATE TRIGGER trigger_post_comment_notification
    AFTER INSERT ON public.post_comments
    FOR EACH ROW EXECUTE FUNCTION create_social_notification();

CREATE TRIGGER trigger_follow_notification
    AFTER INSERT ON public.user_follows
    FOR EACH ROW EXECUTE FUNCTION create_social_notification();

-- =====================================================
-- RLS (Row Level Security) POLICIES
-- =====================================================

-- Habilitar RLS en todas las tablas
ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.post_likes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.post_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_follows ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.comment_likes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.story_views ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.social_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mentions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hashtags ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.post_hashtags ENABLE ROW LEVEL SECURITY;

-- Políticas para posts
CREATE POLICY "Users can view public posts" ON public.posts
    FOR SELECT USING (is_public = true);

CREATE POLICY "Users can view their own posts" ON public.posts
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can create posts" ON public.posts
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Políticas para stories
CREATE POLICY "Users can view non-expired stories" ON public.stories
    FOR SELECT USING (expires_at > NOW());

CREATE POLICY "Users can manage their own stories" ON public.stories
    FOR ALL USING (auth.uid() = user_id);

-- Políticas para likes
CREATE POLICY "Users can view likes" ON public.post_likes
    FOR SELECT USING (true);

CREATE POLICY "Users can manage their own likes" ON public.post_likes
    FOR ALL USING (auth.uid() = user_id);

-- Políticas para comentarios
CREATE POLICY "Users can view comments" ON public.post_comments
    FOR SELECT USING (deleted_at IS NULL);

CREATE POLICY "Users can manage their own comments" ON public.post_comments
    FOR ALL USING (auth.uid() = user_id);

-- Políticas para follows
CREATE POLICY "Users can view follows" ON public.user_follows
    FOR SELECT USING (true);

CREATE POLICY "Users can manage their own follows" ON public.user_follows
    FOR ALL USING (auth.uid() = follower_id);

-- Políticas para notificaciones
CREATE POLICY "Users can view their own notifications" ON public.social_notifications
    FOR ALL USING (auth.uid() = user_id);

-- =====================================================
-- COMENTARIOS FINALES
-- =====================================================

-- Este esquema incluye:
-- ✅ Posts con imágenes/videos
-- ✅ Stories que expiran en 24h
-- ✅ Sistema de likes y comentarios
-- ✅ Sistema de seguimiento
-- ✅ Notificaciones automáticas
-- ✅ Hashtags
-- ✅ Menciones
-- ✅ RLS para seguridad
-- ✅ Índices para optimización
-- ✅ Triggers para automatización

-- Próximos pasos:
-- 1. Ejecutar este SQL en Supabase
-- 2. Crear buckets para media
-- 3. Configurar funciones de limpieza automática
-- 4. Implementar frontend
