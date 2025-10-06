from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Review


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'document_number', 'sex', 'birth_date', 'age')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'document_number', 'sex', 'birth_date', 'age'),
        }),
    )
    list_display = ('email', 'first_name', 'last_name', 'document_number', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name', 'document_number')
    ordering = ('email',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('reviewer', 'reviewed_user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('reviewer__email', 'reviewed_user__email', 'comment')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')

# Register your models here.
