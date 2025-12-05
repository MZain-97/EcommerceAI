"""
Celery configuration for ecommerceBook project.
Handles async tasks like email sending, AI processing, and batch operations.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerceBook.settings')

app = Celery('ecommerceBook')

# Load config from Django settings using CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Clean expired password reset tokens every hour
    'clean-expired-tokens': {
        'task': 'accounts.tasks.clean_expired_password_tokens',
        'schedule': crontab(minute=0),  # Every hour
    },
    # Update user preferences daily
    'update-user-preferences': {
        'task': 'accounts.tasks.batch_update_user_preferences',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    # Re-index products in Pinecone weekly
    'reindex-products': {
        'task': 'accounts.tasks.reindex_all_products',
        'schedule': crontab(day_of_week=1, hour=3, minute=0),  # Monday at 3 AM
    },
    # Send cart abandonment reminders
    'cart-reminders': {
        'task': 'accounts.tasks.send_cart_reminders',
        'schedule': crontab(hour=10, minute=0),  # Daily at 10 AM
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')
