from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Trip(models.Model):
    TRAVEL_STYLES = [
        ('mochilero', 'Mochilero'),
        ('relax', 'Relax'),
        ('aventura', 'Aventura'),
        ('cultural', 'Cultural'),
        ('gastronomico', 'Gastronómico'),
        ('naturaleza', 'Naturaleza'),
    ]
    
    TRANSPORT_TYPES = [
        ('auto', 'Auto'),
        ('colectivo', 'Colectivo'),
        ('avion', 'Avión'),
        ('tren', 'Tren'),
        ('barco', 'Barco'),
        ('combinado', 'Combinado'),
    ]
    
    ACCOMMODATION_TYPES = [
        ('hotel', 'Hotel'),
        ('hostel', 'Hostel'),
        ('airbnb', 'Airbnb'),
        ('camping', 'Camping'),
        ('casa', 'Casa'),
        ('combinado', 'Combinado'),
    ]
    
    FLEXIBILITY_LEVELS = [
        ('bajo', 'Bajo'),
        ('medio', 'Medio'),
        ('alto', 'Alto'),
    ]
    
    STATUS_CHOICES = [
        ('abierto', 'Abierto'),
        ('cerrado', 'Cerrado'),
        ('completado', 'Completado'),
        ('cancelado', 'Cancelado'),
    ]

    # Información básica
    name = models.CharField(max_length=200, help_text="Nombre del viaje")
    description = models.TextField(blank=True, help_text="Descripción del viaje")
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_trips')
    
    # Fechas
    start_date = models.DateField(help_text="Fecha de ida")
    end_date = models.DateField(help_text="Fecha de vuelta")
    
    # Destino y origen
    origin = models.CharField(max_length=100, help_text="Ciudad de origen")
    destination = models.CharField(max_length=100, help_text="Ciudad de destino")
    
    # Detalles del viaje
    travel_style = models.CharField(max_length=20, choices=TRAVEL_STYLES, help_text="Estilo de viaje")
    transport_type = models.CharField(max_length=20, choices=TRANSPORT_TYPES, help_text="Tipo de transporte")
    accommodation_type = models.CharField(max_length=20, choices=ACCOMMODATION_TYPES, help_text="Tipo de hospedaje")
    planned_activities = models.TextField(blank=True, help_text="Actividades previstas")
    
    # Participantes
    max_participants = models.PositiveIntegerField(default=2, help_text="Cantidad máxima de personas")
    current_participants = models.PositiveIntegerField(default=1, help_text="Cantidad actual de participantes")
    
    # Presupuesto
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Presupuesto mínimo")
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Presupuesto máximo")
    
    # Flexibilidad
    flexibility_level = models.CharField(max_length=10, choices=FLEXIBILITY_LEVELS, default='medio', help_text="Nivel de flexibilidad")
    
    # Estado
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='abierto', help_text="Estado del viaje")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.origin} a {self.destination}"
    
    @property
    def available_spots(self):
        return self.max_participants - self.current_participants
    
    @property
    def is_full(self):
        return self.current_participants >= self.max_participants


class Application(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('accepted', 'Aceptada'),
        ('rejected', 'Rechazada'),
        ('withdrawn', 'Retirada'),
    ]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Mensaje opcional del aplicante
    message = models.TextField(blank=True, help_text="Mensaje del aplicante al anfitrión")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['trip', 'applicant']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.applicant.first_name} aplicó a {self.trip.name}"
    
    def accept(self):
        """Aceptar la aplicación y actualizar contadores"""
        if self.status != 'pending':
            raise ValueError("Solo se pueden aceptar aplicaciones pendientes")
        
        self.status = 'accepted'
        self.responded_at = timezone.now()
        self.save()
        
        # Actualizar contador de participantes
        self.trip.current_participants += 1
        self.trip.save()

        # Registrar participante en tabla TripParticipant
        try:
            TripParticipant.objects.get_or_create(
                trip=self.trip,
                user=self.applicant,
                defaults={'is_creator': False}
            )
        except Exception:
            # No bloquear el flujo por errores de concurrencia
            pass
        
        # Rechazar automáticamente otras aplicaciones pendientes si el viaje se llena
        if self.trip.is_full:
            Application.objects.filter(
                trip=self.trip,
                status='pending'
            ).exclude(id=self.id).update(
                status='rejected',
                responded_at=timezone.now()
            )
    
    def reject(self):
        """Rechazar la aplicación"""
        if self.status != 'pending':
            raise ValueError("Solo se pueden rechazar aplicaciones pendientes")
        
        self.status = 'rejected'
        self.responded_at = timezone.now()
        self.save()


class TripParticipant(models.Model):
    """Modelo para rastrear participantes de un viaje"""
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trip_participations')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_creator = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['trip', 'user']
    
    def __str__(self):
        return f"{self.user.first_name} en {self.trip.name}"