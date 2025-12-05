"""
Configuration loader for environment variables.
Centralizes all environment variable loading with proper defaults and validation.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)


def get_env_variable(var_name, default=None, required=False, cast=str):
    """
    Get environment variable with optional default and type casting.

    Args:
        var_name (str): Name of the environment variable
        default: Default value if variable is not set
        required (bool): If True, raises error when variable is missing
        cast (type): Type to cast the value to (str, int, bool, list)

    Returns:
        The environment variable value cast to the specified type

    Raises:
        ValueError: If required variable is missing
    """
    value = os.getenv(var_name, default)

    if required and value is None:
        raise ValueError(f"Required environment variable '{var_name}' is not set")

    if value is None:
        return None

    # Type casting
    if cast == bool:
        return value.lower() in ('true', '1', 'yes', 'on')
    elif cast == int:
        return int(value)
    elif cast == float:
        return float(value)
    elif cast == list:
        return [item.strip() for item in value.split(',') if item.strip()]
    else:
        return str(value)


# Django Settings
SECRET_KEY = get_env_variable('DJANGO_SECRET_KEY', required=True)
DEBUG = get_env_variable('DJANGO_DEBUG', default='False', cast=bool)
ALLOWED_HOSTS = get_env_variable('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=list)

# Database Settings
DB_NAME = get_env_variable('DB_NAME', default='EcomerceDB')
DB_USER = get_env_variable('DB_USER', default='postgres')
DB_PASSWORD = get_env_variable('DB_PASSWORD', required=True)
DB_HOST = get_env_variable('DB_HOST', default='localhost')
DB_PORT = get_env_variable('DB_PORT', default='5432')

# Email Settings
EMAIL_BACKEND = get_env_variable('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = get_env_variable('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = get_env_variable('EMAIL_PORT', default='587', cast=int)
EMAIL_USE_TLS = get_env_variable('EMAIL_USE_TLS', default='True', cast=bool)
EMAIL_HOST_USER = get_env_variable('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = get_env_variable('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = get_env_variable('DEFAULT_FROM_EMAIL', default='noreply@vortexai.com')
CONTACT_EMAIL = get_env_variable('CONTACT_EMAIL', default='support@vortexai.com')

# OpenAI Settings
OPENAI_API_KEY = get_env_variable('OPENAI_API_KEY', required=True)

# Pinecone Settings
PINECONE_API_KEY = get_env_variable('PINECONE_API_KEY', required=True)
PINECONE_ENVIRONMENT = get_env_variable('PINECONE_ENVIRONMENT', default='us-east-1')
PINECONE_INDEX_NAME = get_env_variable('PINECONE_INDEX_NAME', default='ecommerce-products')

# Redis Settings
REDIS_HOST = get_env_variable('REDIS_HOST', default='localhost')
REDIS_PORT = get_env_variable('REDIS_PORT', default='6379', cast=int)
REDIS_DB = get_env_variable('REDIS_DB', default='0', cast=int)

# Sentry Settings
SENTRY_DSN = get_env_variable('SENTRY_DSN', default='')

# Security Settings
SECURE_SSL_REDIRECT = get_env_variable('SECURE_SSL_REDIRECT', default='False', cast=bool)
SESSION_COOKIE_SECURE = get_env_variable('SESSION_COOKIE_SECURE', default='False', cast=bool)
CSRF_COOKIE_SECURE = get_env_variable('CSRF_COOKIE_SECURE', default='False', cast=bool)
SECURE_BROWSER_XSS_FILTER = get_env_variable('SECURE_BROWSER_XSS_FILTER', default='True', cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = get_env_variable('SECURE_CONTENT_TYPE_NOSNIFF', default='True', cast=bool)
X_FRAME_OPTIONS = get_env_variable('X_FRAME_OPTIONS', default='DENY')

# AWS S3 Settings
USE_S3 = get_env_variable('USE_S3', default='False', cast=bool)
AWS_ACCESS_KEY_ID = get_env_variable('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = get_env_variable('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = get_env_variable('AWS_STORAGE_BUCKET_NAME', default='')
AWS_S3_REGION_NAME = get_env_variable('AWS_S3_REGION_NAME', default='us-east-1')

# Celery Settings
CELERY_BROKER_URL = get_env_variable('CELERY_BROKER_URL', default='redis://localhost:6379/1')
CELERY_RESULT_BACKEND = get_env_variable('CELERY_RESULT_BACKEND', default='redis://localhost:6379/1')
