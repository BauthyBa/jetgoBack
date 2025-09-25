import os
from supabase import create_client, Client


_supabase_admin: Client | None = None
_supabase_anon: Client | None = None


def get_supabase_admin() -> Client:
    global _supabase_admin
    if _supabase_admin is None:
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        if not url or not key:
            raise RuntimeError('SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not configured')
        _supabase_admin = create_client(url, key)
    return _supabase_admin


def get_supabase_anon() -> Client:
    global _supabase_anon
    if _supabase_anon is None:
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_ANON_KEY')
        if not url or not key:
            raise RuntimeError('SUPABASE_URL or SUPABASE_ANON_KEY not configured')
        _supabase_anon = create_client(url, key)
    return _supabase_anon


