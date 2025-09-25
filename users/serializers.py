from datetime import datetime
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from .models import User
from api.supabase_client import get_supabase_admin, get_supabase_anon
import logging
logger = logging.getLogger(__name__)
import unicodedata
import re


def parse_dni_barcode_payload(payload: str):
    # Expected format:
    # 'nrodetramite'@'apellido1 apellido2'@'nombre1 nombre2'@'sexo'(M/F)@'nrodedocumento'@'ejemplar'@'fechadenacimiento'(DD/MM/YYYY)@'fechadeemision'(DD/MM/YYYY)@'CUIL'
    parts = payload.split('@')
    if len(parts) < 9:
        raise serializers.ValidationError('Formato de código inválido')
    raw_lastnames = parts[1].strip().strip("'")
    raw_names = parts[2].strip().strip("'")
    sex = parts[3].strip().strip("'")
    document_number = parts[4].strip().strip("'")
    birth_str = parts[6].strip().strip("'")

    try:
        birth_date = datetime.strptime(birth_str, '%d/%m/%Y').date()
    except Exception:
        raise serializers.ValidationError('Fecha de nacimiento inválida')

    names = raw_names.split()
    first_name = ' '.join(names)
    last_name = raw_lastnames

    return {
        'first_name': first_name,
        'last_name': last_name,
        'sex': sex,
        'document_number': document_number,
        'birth_date': birth_date,
    }


def calculate_age(birth_date):
    today = datetime.utcnow().date()
    years = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return years


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize('NFD', text or '')
    return ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')


def _normalize_name_tokens(value: str) -> list[str]:
    if value is None:
        return []
    no_accents = _strip_accents(str(value)).upper()
    # Replace non-letter characters with spaces; keep A-Z and 0-9 (some DNI may have numerics in compound names)
    cleaned = re.sub(r'[^A-Z0-9]+', ' ', no_accents)
    return [part for part in cleaned.split(' ') if part]


def names_match(input_value: str, parsed_value: str) -> bool:
    """Allow one or two names/lastnames: consider it a match if one set of tokens
    is contained within the other set (order-insensitive, simple token subset)."""
    input_tokens = set(_normalize_name_tokens(input_value))
    parsed_tokens = set(_normalize_name_tokens(parsed_value))
    if not input_tokens or not parsed_tokens:
        return False
    return input_tokens.issubset(parsed_tokens) or parsed_tokens.issubset(input_tokens)


class RegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    document_number = serializers.CharField()
    sex = serializers.ChoiceField(choices=['M', 'F'])
    birth_date = serializers.DateField()
    age = serializers.IntegerField(read_only=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    estuserid = serializers.IntegerField(required=False, allow_null=True)
    dni_front_payload = serializers.CharField(write_only=True, help_text='Cadena leída del código de barras')

    def validate(self, attrs):
        payload = attrs.get('dni_front_payload')
        parsed = parse_dni_barcode_payload(payload)

        # Compare entered vs parsed
        # Names/lastnames allow one or two tokens
        if not names_match(attrs.get('first_name'), parsed['first_name']):
            raise serializers.ValidationError({'first_name': 'No coincide con el DNI'})
        if not names_match(attrs.get('last_name'), parsed['last_name']):
            raise serializers.ValidationError({'last_name': 'No coincide con el DNI'})

        # Exact match for sex and document number with normalization
        # Sex: compare first char upper (accept 'M'/'F')
        entered_sex = str(attrs.get('sex') or '').strip().upper()[:1]
        parsed_sex = str(parsed['sex'] or '').strip().upper()[:1]
        if entered_sex != parsed_sex:
            raise serializers.ValidationError({'sex': 'No coincide con el DNI'})

        # Document: compare digits-only
        entered_doc = re.sub(r'\D', '', str(attrs.get('document_number') or ''))
        parsed_doc = re.sub(r'\D', '', str(parsed['document_number'] or ''))
        if entered_doc != parsed_doc:
            raise serializers.ValidationError({'document_number': 'No coincide con el DNI'})

        if attrs.get('birth_date') != parsed['birth_date']:
            raise serializers.ValidationError({'birth_date': 'No coincide con el DNI'})

        age = calculate_age(parsed['birth_date'])
        if age < 18:
            raise serializers.ValidationError({'age': 'Debe ser mayor de edad'})
        attrs['age'] = age
        return attrs

    def create(self, validated_data):
        payload = validated_data.pop('dni_front_payload', None)
        password = validated_data.pop('password')
        anon = get_supabase_anon()
        # Store additional fields in user_metadata
        metadata = {
            'first_name': validated_data.get('first_name'),
            'last_name': validated_data.get('last_name'),
            'document_number': validated_data.get('document_number'),
            'sex': validated_data.get('sex'),
            'birth_date': str(validated_data.get('birth_date')),
            'age': validated_data.get('age'),
        }
        # Email confirmation flow: send confirmation email
        import os
        redirect_url = os.environ.get('FRONTEND_CONFIRM_URL', 'http://localhost:5173/login?confirmed=1')
        try:
            res = anon.auth.sign_up({
                'email': validated_data.get('email'),
                'password': password,
                'options': {
                    'data': metadata,
                    'email_redirect_to': redirect_url,
                },
            })
        except Exception as e:
            logger.error('Supabase sign_up failed (with redirect): %s', e)
            # Fallback: retry without redirect URL (in case not allowed in project settings)
            try:
                res = anon.auth.sign_up({
                    'email': validated_data.get('email'),
                    'password': password,
                    'options': {
                        'data': metadata,
                    },
                })
            except Exception as e2:
                raise serializers.ValidationError(f'No se pudo crear el usuario en Supabase: {e2}')
        user = getattr(res, 'user', None)
        if not user:
            raise serializers.ValidationError('No se pudo crear el usuario en Supabase')
        # Update the Postgres row created by trigger (identified by userid)
        try:
            from os import environ
            table_name = environ.get('SUPABASE_USERS_TABLE', 'User')
            schema = environ.get('SUPABASE_SCHEMA', 'public')
            admin = get_supabase_admin()
            base_row = {
                'userid': str(user.id),
                'dni': metadata['document_number'],
                'nombre': metadata['first_name'],
                'apellido': metadata['last_name'],
                'sexo': metadata['sex'],
                'fecha_nacimiento': metadata['birth_date'],
            }
            # estuserid from request or default env
            est_from_req = validated_data.get('estuserid', None)
            if est_from_req is not None:
                base_row['estuserid'] = est_from_req
            else:
                default_est = environ.get('SUPABASE_DEFAULT_ESTUSERID')
                if default_est is not None and default_est != '':
                    try:
                        base_row['estuserid'] = int(default_est)
                    except Exception:
                        base_row['estuserid'] = default_est
            # Try update first
            resp = admin.schema(schema).table(table_name).update({k:v for k,v in base_row.items() if k != 'userid'}).eq('userid', str(user.id)).execute()
            data = getattr(resp, 'data', None)
            logger.warning('Supabase update into %s.%s result: %s', schema, table_name, data)
            # If no row updated, insert
            if not data:
                resp = admin.schema(schema).table(table_name).insert(base_row).execute()
                logger.warning('Supabase insert into %s.%s result: %s', schema, table_name, getattr(resp, 'data', None))
        except Exception as e:
            logger.warning('Supabase update to %s failed: %s', table_name, e)
        # Return minimal representation; user must confirm email
        return {'id': user.id, **validated_data}


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, attrs):
        # Authenticate against Supabase
        anon = get_supabase_anon()
        try:
            res = anon.auth.sign_in_with_password({'email': attrs['email'], 'password': attrs['password']})
        except Exception:
            raise serializers.ValidationError('Credenciales inválidas')
        session = getattr(res, 'session', None)
        user = getattr(res, 'user', None)
        # Block if not confirmed
        confirmed_at = getattr(user, 'email_confirmed_at', None) if user else None
        if not confirmed_at:
            raise serializers.ValidationError('Debes confirmar tu email antes de iniciar sesión')
        if not session or not session.access_token:
            raise serializers.ValidationError('Credenciales inválidas')
        # Mark confirmed in table
        try:
            from os import environ
            table_name = environ.get('SUPABASE_USERS_TABLE', 'User')
            schema = environ.get('SUPABASE_SCHEMA', 'public')
            admin = get_supabase_admin()
            resp = admin.schema(schema).table(table_name).update({'mail_confirmacion': True}).eq('userid', str(user.id)).execute()
            logger.warning('Supabase update %s.%s mail_confirmacion result: %s', schema, table_name, getattr(resp, 'data', None))
        except Exception as e:
            logger.warning('Supabase update mail_confirmacion failed: %s', e)
        attrs['supabase_access'] = session.access_token
        attrs['supabase_refresh'] = session.refresh_token
        return attrs

