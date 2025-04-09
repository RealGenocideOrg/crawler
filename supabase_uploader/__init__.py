"""
Supabase Uploader module for storing extracted domains in Supabase.
"""

try:
    from .uploader import (
        SupabaseUploader,
        upload_domains
    )
except ImportError:
    from supabase_uploader.uploader import (
        SupabaseUploader,
        upload_domains
    ) 