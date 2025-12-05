"""
Initialize Celery app for Django project.
This ensures Celery is loaded when Django starts.
"""
# Make Celery optional for development/testing
try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Celery not installed - async features will be disabled
    pass
