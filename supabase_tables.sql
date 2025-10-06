-- Tablas para el sistema de reseñas y notificaciones en Supabase

-- Tabla de reseñas
CREATE TABLE public.reviews (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  reviewer_id uuid NOT NULL,
  reviewed_user_id uuid NOT NULL,
  rating integer NOT NULL CHECK (rating >= 1 AND rating <= 5),
  comment text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT reviews_pkey PRIMARY KEY (id),
  CONSTRAINT reviews_reviewer_fk FOREIGN KEY (reviewer_id) REFERENCES auth.users(id),
  CONSTRAINT reviews_reviewed_user_fk FOREIGN KEY (reviewed_user_id) REFERENCES auth.users(id),
  CONSTRAINT reviews_unique_reviewer_reviewed UNIQUE (reviewer_id, reviewed_user_id),
  CONSTRAINT reviews_no_self_review CHECK (reviewer_id != reviewed_user_id)
);

-- Tabla de notificaciones
CREATE TABLE public.notifications (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  type text NOT NULL,
  title text NOT NULL,
  message text NOT NULL,
  data jsonb,
  read boolean DEFAULT false,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT notifications_pkey PRIMARY KEY (id),
  CONSTRAINT notifications_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id)
);

-- Índices para mejorar performance
CREATE INDEX idx_reviews_reviewed_user ON public.reviews(reviewed_user_id);
CREATE INDEX idx_reviews_reviewer ON public.reviews(reviewer_id);
CREATE INDEX idx_notifications_user_unread ON public.notifications(user_id, read, created_at);

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para actualizar updated_at en reviews
CREATE TRIGGER update_reviews_updated_at 
    BEFORE UPDATE ON public.reviews 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Políticas RLS (Row Level Security)
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- Política para reviews: todos pueden leer, solo el reviewer puede crear/actualizar su propia reseña
CREATE POLICY "Reviews are viewable by everyone" ON public.reviews
    FOR SELECT USING (true);

CREATE POLICY "Users can create reviews" ON public.reviews
    FOR INSERT WITH CHECK (auth.uid() = reviewer_id);

CREATE POLICY "Users can update their own reviews" ON public.reviews
    FOR UPDATE USING (auth.uid() = reviewer_id);

-- Política para notificaciones: solo el usuario puede ver sus propias notificaciones
CREATE POLICY "Users can view their own notifications" ON public.notifications
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can update their own notifications" ON public.notifications
    FOR UPDATE USING (auth.uid() = user_id);

-- Función para crear notificación automática cuando se crea una reseña
CREATE OR REPLACE FUNCTION create_review_notification()
RETURNS TRIGGER AS $$
DECLARE
    reviewer_name text;
BEGIN
    -- Obtener el nombre del reviewer
    SELECT COALESCE(nombre || ' ' || apellido, 'Un usuario')
    INTO reviewer_name
    FROM public.User
    WHERE userid = NEW.reviewer_id;

    -- Crear notificación para el usuario reseñado
    INSERT INTO public.notifications (user_id, type, title, message, data)
    VALUES (
        NEW.reviewed_user_id,
        'new_review',
        'Nueva reseña recibida',
        reviewer_name || ' te ha dejado una reseña de ' || NEW.rating || ' estrella' || 
        CASE WHEN NEW.rating = 1 THEN '' ELSE 's' END,
        jsonb_build_object(
            'review_id', NEW.id,
            'reviewer_id', NEW.reviewer_id,
            'reviewer_name', reviewer_name,
            'rating', NEW.rating
        )
    );

    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para crear notificación cuando se crea una reseña
CREATE TRIGGER create_review_notification_trigger
    AFTER INSERT ON public.reviews
    FOR EACH ROW
    EXECUTE FUNCTION create_review_notification();

-- Función para crear notificación cuando alguien se une a un viaje
CREATE OR REPLACE FUNCTION create_trip_join_notification()
RETURNS TRIGGER AS $$
DECLARE
    joiner_name text;
    trip_name text;
    creator_id uuid;
BEGIN
    -- Obtener información del usuario que se unió
    SELECT COALESCE(nombre || ' ' || apellido, 'Un usuario')
    INTO joiner_name
    FROM public.User
    WHERE userid = NEW.user_id;

    -- Obtener información del viaje y su creador
    SELECT name, creator_id
    INTO trip_name, creator_id
    FROM public.trips
    WHERE id = NEW.trip_id;

    -- Solo crear notificación si no es el creador del viaje
    IF NEW.user_id != creator_id THEN
        -- Crear notificación para el creador del viaje
        INSERT INTO public.notifications (user_id, type, title, message, data)
        VALUES (
            creator_id,
            'trip_join',
            'Nuevo miembro en tu viaje',
            joiner_name || ' se ha unido a tu viaje "' || trip_name || '"',
            jsonb_build_object(
                'trip_id', NEW.trip_id,
                'trip_name', trip_name,
                'joiner_id', NEW.user_id,
                'joiner_name', joiner_name
            )
        );
    END IF;

    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para crear notificación cuando alguien se une a un viaje
CREATE TRIGGER create_trip_join_notification_trigger
    AFTER INSERT ON public.trip_members
    FOR EACH ROW
    EXECUTE FUNCTION create_trip_join_notification();
