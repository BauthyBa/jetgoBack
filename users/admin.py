from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


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

# Register your models here.
