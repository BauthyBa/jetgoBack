-- Sistema de reportes de usuarios para Supabase

-- Tabla de reportes de usuarios
CREATE TABLE public.user_reports (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  reporter_id uuid NOT NULL,
  reported_user_id uuid NOT NULL,
  reason text NOT NULL,
  description text,
  evidence_image_url text,
  status text NOT NULL DEFAULT 'pending',
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  reviewed_at timestamp with time zone,
  reviewed_by uuid,
  admin_notes text,
  CONSTRAINT user_reports_pkey PRIMARY KEY (id),
  CONSTRAINT user_reports_reporter_fk FOREIGN KEY (reporter_id) REFERENCES auth.users(id),
  CONSTRAINT user_reports_reported_user_fk FOREIGN KEY (reported_user_id) REFERENCES auth.users(id),
  CONSTRAINT user_reports_reviewed_by_fk FOREIGN KEY (reviewed_by) REFERENCES auth.users(id),
  CONSTRAINT user_reports_no_self_report CHECK (reporter_id != reported_user_id),
  CONSTRAINT user_reports_status_check CHECK (status IN ('pending', 'reviewed', 'resolved', 'dismissed'))
);

-- Tabla de suspensiones de usuarios
CREATE TABLE public.user_suspensions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  reason text NOT NULL,
  suspended_by uuid,
  suspended_at timestamp with time zone NOT NULL DEFAULT now(),
  expires_at timestamp with time zone,
  is_permanent boolean DEFAULT false,
  is_active boolean DEFAULT true,
  notes text,
  CONSTRAINT user_suspensions_pkey PRIMARY KEY (id),
  CONSTRAINT user_suspensions_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id),
  CONSTRAINT user_suspensions_suspended_by_fk FOREIGN KEY (suspended_by) REFERENCES auth.users(id)
);

-- Índices para mejorar performance
CREATE INDEX idx_user_reports_reported_user ON public.user_reports(reported_user_id, status);
CREATE INDEX idx_user_reports_reporter ON public.user_reports(reporter_id);
CREATE INDEX idx_user_reports_status ON public.user_reports(status, created_at);
CREATE INDEX idx_user_suspensions_user_active ON public.user_suspensions(user_id, is_active);

-- Crear bucket para imágenes de evidencia (ejecutar en Storage)
-- INSERT INTO storage.buckets (id, name, public) VALUES ('report-evidence', 'report-evidence', false);

-- Políticas RLS (Row Level Security)
ALTER TABLE public.user_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_suspensions ENABLE ROW LEVEL SECURITY;

-- Política para reportes: usuarios pueden ver sus propios reportes hechos
CREATE POLICY "Users can view their own reports" ON public.user_reports
    FOR SELECT USING (auth.uid() = reporter_id);

-- Política para reportes: usuarios pueden crear reportes
CREATE POLICY "Users can create reports" ON public.user_reports
    FOR INSERT WITH CHECK (auth.uid() = reporter_id);

-- Política para suspensiones: usuarios pueden ver sus propias suspensiones
CREATE POLICY "Users can view their own suspensions" ON public.user_suspensions
    FOR SELECT USING (auth.uid() = user_id);

-- Políticas para Storage (report-evidence bucket)
-- Usuarios pueden subir imágenes de evidencia
CREATE POLICY "Users can upload report evidence" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'report-evidence' 
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

-- Usuarios pueden ver sus propias imágenes de evidencia
CREATE POLICY "Users can view their own report evidence" ON storage.objects
    FOR SELECT USING (
        bucket_id = 'report-evidence' 
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

-- Administradores pueden ver todas las imágenes de evidencia (futuro)
CREATE POLICY "Admins can view all report evidence" ON storage.objects
    FOR SELECT USING (
        bucket_id = 'report-evidence'
        -- AND auth.jwt() ->> 'role' = 'admin'  -- Descomentar cuando tengas roles
    );

-- Función para verificar reportes y suspender automáticamente
CREATE OR REPLACE FUNCTION check_and_suspend_user()
RETURNS TRIGGER AS $$
DECLARE
    report_count integer;
    reporter_name text;
    reported_user_name text;
BEGIN
    -- Contar reportes pendientes del usuario reportado
    SELECT COUNT(*)
    INTO report_count
    FROM public.user_reports
    WHERE reported_user_id = NEW.reported_user_id 
    AND status = 'pending';

    -- Si llega a 5 reportes, suspender automáticamente
    IF report_count >= 5 THEN
        -- Verificar que no esté ya suspendido
        IF NOT EXISTS (
            SELECT 1 FROM public.user_suspensions 
            WHERE user_id = NEW.reported_user_id 
            AND is_active = true
        ) THEN
            -- Crear suspensión automática
            INSERT INTO public.user_suspensions (
                user_id,
                reason,
                suspended_by,
                expires_at,
                is_permanent,
                notes
            ) VALUES (
                NEW.reported_user_id,
                'Suspensión automática por acumulación de reportes',
                NULL, -- Sistema automático
                now() + interval '30 days', -- 30 días de suspensión
                false,
                'Usuario suspendido automáticamente por acumular ' || report_count || ' reportes.'
            );

            -- Obtener nombres para la notificación
            SELECT COALESCE(nombre || ' ' || apellido, 'Un usuario')
            INTO reporter_name
            FROM public.User
            WHERE userid = NEW.reporter_id;

            SELECT COALESCE(nombre || ' ' || apellido, 'Usuario')
            INTO reported_user_name
            FROM public.User
            WHERE userid = NEW.reported_user_id;

            -- Crear notificación para el usuario suspendido
            INSERT INTO public.notifications (user_id, type, title, message, data)
            VALUES (
                NEW.reported_user_id,
                'account_suspended',
                'Cuenta suspendida',
                'Tu cuenta ha sido suspendida temporalmente por acumular múltiples reportes. La suspensión expira en 30 días.',
                jsonb_build_object(
                    'suspension_reason', 'Múltiples reportes',
                    'report_count', report_count,
                    'expires_at', (now() + interval '30 days')::text
                )
            );
        END IF;
    END IF;

    -- Crear notificación para el usuario reportado (si no está suspendido)
    IF report_count < 5 THEN
        SELECT COALESCE(nombre || ' ' || apellido, 'Un usuario')
        INTO reporter_name
        FROM public.User
        WHERE userid = NEW.reporter_id;

        INSERT INTO public.notifications (user_id, type, title, message, data)
        VALUES (
            NEW.reported_user_id,
            'user_reported',
            'Has sido reportado',
            'Un usuario ha reportado tu cuenta por: ' || NEW.reason,
            jsonb_build_object(
                'report_id', NEW.id,
                'reason', NEW.reason,
                'reporter_name', 'Usuario anónimo' -- Por privacidad
            )
        );
    END IF;

    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para verificar reportes automáticamente
CREATE TRIGGER check_user_reports_trigger
    AFTER INSERT ON public.user_reports
    FOR EACH ROW
    EXECUTE FUNCTION check_and_suspend_user();

-- Función para verificar si un usuario está suspendido
CREATE OR REPLACE FUNCTION is_user_suspended(user_uuid uuid)
RETURNS boolean AS $$
DECLARE
    suspension_exists boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM public.user_suspensions
        WHERE user_id = user_uuid
        AND is_active = true
        AND (expires_at IS NULL OR expires_at > now())
    ) INTO suspension_exists;
    
    RETURN suspension_exists;
END;
$$ language 'plpgsql';

-- Vista para obtener estadísticas de reportes por usuario
CREATE OR REPLACE VIEW user_report_stats AS
SELECT 
    reported_user_id,
    COUNT(*) as total_reports,
    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_reports,
    COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved_reports,
    COUNT(CASE WHEN status = 'dismissed' THEN 1 END) as dismissed_reports,
    MAX(created_at) as last_report_date,
    MIN(created_at) as first_report_date
FROM public.user_reports
GROUP BY reported_user_id;

-- Insertar motivos predefinidos como referencia (opcional)
COMMENT ON COLUMN public.user_reports.reason IS 
'Motivos válidos: 
- Comportamiento inapropiado
- Cancelación sin aviso  
- Conducta sospechosa o engañosa
- Incumplimiento de las normas de la app
- Problemas con el pago o gastos
- Conducción peligrosa o imprudente
- Falta de higiene o condiciones inapropiadas del vehículo
- Acoso o comportamiento sexual inapropiado
- Perfil falso o suplantación de identidad
- Otro motivo';
