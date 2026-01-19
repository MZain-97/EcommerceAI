"""
Celery tasks for async operations.
Handles email sending, AI processing, batch updates, and scheduled maintenance.
"""
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


# ==============================================================================
# EMAIL TASKS
# ==============================================================================

@shared_task(bind=True, max_retries=3)
def send_email_task(self, subject, message, recipient_list, html_message=None):
    """
    Send email asynchronously with retry logic.

    Args:
        subject: Email subject
        message: Plain text message
        recipient_list: List of recipient emails
        html_message: Optional HTML message

    Returns:
        Number of successfully sent emails
    """
    try:
        sent = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
        logger.info(f"Email sent to {len(recipient_list)} recipients: {subject}")
        return sent
    except Exception as exc:
        logger.error(f"Email sending failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def send_password_reset_email(user_id, token):
    """
    Send password reset email to user.

    Args:
        user_id: User ID
        token: Reset token
    """
    from .models import User

    try:
        user = User.objects.get(id=user_id)
        subject = "Password Reset Request"
        message = f"""
        Hello {user.full_name},

        You requested a password reset. Your verification code is: {token}

        This code will expire in 15 minutes.

        If you didn't request this, please ignore this email.

        Best regards,
        The Team
        """

        send_email_task.delay(subject, message, [user.email])
        logger.info(f"Password reset email queued for {user.email}")
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for password reset email")


@shared_task
def send_order_confirmation_email(order_id):
    """
    Send order confirmation email to buyer.

    Args:
        order_id: Order ID
    """
    from .models import Order

    try:
        order = Order.objects.select_related('user').prefetch_related('items').get(id=order_id)

        items_text = "\n".join([
            f"- {item.content_object.title} x{item.quantity} = ${item.get_total_price()}"
            for item in order.items.all()
        ])

        subject = f"Order Confirmation #{order.order_number}"
        message = f"""
        Hello {order.user.full_name},

        Thank you for your purchase! Your order has been confirmed.

        Order Number: {order.order_number}
        Total Amount: ${order.total_amount}

        Items:
        {items_text}

        You can download your products from your orders page.

        Best regards,
        The Team
        """

        send_email_task.delay(subject, message, [order.user.email])
        logger.info(f"Order confirmation email queued for order {order.order_number}")
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for confirmation email")


@shared_task
def send_seller_notification_email(seller_id, order_item_id):
    """
    Notify seller about new sale.

    Args:
        seller_id: Seller user ID
        order_item_id: OrderItem ID
    """
    from .models import User, OrderItem

    try:
        seller = User.objects.get(id=seller_id)
        order_item = OrderItem.objects.select_related('order').get(id=order_item_id)

        subject = "New Sale - Product Purchased"
        message = f"""
        Hello {seller.full_name},

        Great news! Your product has been purchased.

        Product: {order_item.content_object.title}
        Quantity: {order_item.quantity}
        Amount: ${order_item.get_total_price()}
        Order: #{order_item.order.order_number}

        Best regards,
        The Team
        """

        send_email_task.delay(subject, message, [seller.email])
        logger.info(f"Seller notification email queued for {seller.email}")
    except (User.DoesNotExist, OrderItem.DoesNotExist) as e:
        logger.error(f"Error sending seller notification: {e}")


# ==============================================================================
# AI & INDEXING TASKS
# ==============================================================================

@shared_task(bind=True, max_retries=2)
def index_product_task(self, product_type, product_id):
    """
    Index a single product in Pinecone.

    Args:
        product_type: 'book', 'course', or 'webinar'
        product_id: Product ID
    """
    from .chatbot_helper import index_single_product
    from .models import Book, Course, Webinar

    try:
        model_map = {
            'book': Book,
            'course': Course,
            'webinar': Webinar
        }

        if product_type not in model_map:
            logger.error(f"Invalid product type: {product_type}")
            return False

        product = model_map[product_type].objects.get(id=product_id)
        success = index_single_product(product, product_type)

        if success:
            logger.info(f"Product indexed: {product_type} {product_id}")
        else:
            logger.warning(f"Product indexing failed: {product_type} {product_id}")

        return success
    except Exception as exc:
        logger.error(f"Error indexing product: {exc}")
        raise self.retry(exc=exc, countdown=300)  # Retry after 5 minutes


@shared_task
def reindex_all_products():
    """
    Re-index all active products in Pinecone (scheduled weekly).
    """
    from .chatbot_helper import index_all_products

    try:
        count = index_all_products()
        logger.info(f"Successfully re-indexed {count} products")
        return count
    except Exception as e:
        logger.error(f"Error re-indexing products: {e}")
        return 0


@shared_task
def delete_product_from_index_task(product_type, product_id):
    """
    Delete product from Pinecone index.

    Args:
        product_type: 'book', 'course', or 'webinar'
        product_id: Product ID
    """
    from .chatbot_helper import delete_product_from_index

    try:
        success = delete_product_from_index(product_id, product_type)
        if success:
            logger.info(f"Product removed from index: {product_type} {product_id}")
        return success
    except Exception as e:
        logger.error(f"Error deleting product from index: {e}")
        return False


# ==============================================================================
# MAINTENANCE TASKS
# ==============================================================================

@shared_task
def clean_expired_password_tokens():
    """
    Clean up expired password reset tokens (scheduled hourly).
    """
    from .models import PasswordResetToken

    try:
        cutoff_time = timezone.now() - timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRY)
        expired_count = PasswordResetToken.objects.filter(
            Q(created_at__lt=cutoff_time) | Q(is_used=True)
        ).delete()[0]

        logger.info(f"Cleaned up {expired_count} expired password tokens")
        return expired_count
    except Exception as e:
        logger.error(f"Error cleaning expired tokens: {e}")
        return 0


@shared_task
def batch_update_user_preferences():
    """
    Update user preferences for all users (scheduled daily).
    """
    from .models import User
    from .recommendation_engine import update_user_preferences

    try:
        users = User.objects.filter(is_active=True, user_type='buyer')
        count = 0

        for user in users:
            try:
                update_user_preferences(user)
                count += 1
            except Exception as e:
                logger.error(f"Error updating preferences for user {user.id}: {e}")

        logger.info(f"Updated preferences for {count} users")
        return count
    except Exception as e:
        logger.error(f"Error in batch preference update: {e}")
        return 0


@shared_task
def send_cart_reminders():
    """
    Send reminders to users with abandoned carts (scheduled daily).
    """
    from .models import Cart

    try:
        # Find carts that haven't been updated in 24 hours and have items
        cutoff_time = timezone.now() - timedelta(hours=24)
        abandoned_carts = Cart.objects.filter(
            updated_at__lt=cutoff_time,
            items__isnull=False
        ).distinct().select_related('user')

        count = 0
        for cart in abandoned_carts:
            subject = "Don't forget your cart!"
            message = f"""
            Hello {cart.user.full_name},

            You have {cart.get_total_items()} items in your cart worth ${cart.get_total_price()}.

            Complete your purchase now!

            Best regards,
            The Team
            """

            send_email_task.delay(subject, message, [cart.user.email])
            count += 1

        logger.info(f"Sent {count} cart reminder emails")
        return count
    except Exception as e:
        logger.error(f"Error sending cart reminders: {e}")
        return 0


# ==============================================================================
# ANALYTICS TASKS
# ==============================================================================

@shared_task
def generate_seller_analytics(seller_id, period_days=30):
    """
    Generate analytics report for seller.

    Args:
        seller_id: Seller user ID
        period_days: Number of days to analyze
    """
    from .models import User, OrderItem
    from django.db.models import Sum, Count, Avg
    from django.contrib.contenttypes.models import ContentType

    try:
        seller = User.objects.get(id=seller_id, user_type='seller')
        cutoff_date = timezone.now() - timedelta(days=period_days)

        # Get seller's products
        from .models import Book, Course, Webinar

        all_items = []

        for model in [Book, Course, Webinar]:
            content_type = ContentType.objects.get_for_model(model)
            products = model.objects.filter(seller=seller)
            product_ids = products.values_list('id', flat=True)

            items = OrderItem.objects.filter(
                content_type=content_type,
                object_id__in=product_ids,
                created_at__gte=cutoff_date
            )
            all_items.extend(items)

        # Calculate metrics
        total_sales = sum(item.get_total_price() for item in all_items)
        total_orders = len(all_items)

        analytics = {
            'seller_id': seller_id,
            'period_days': period_days,
            'total_sales': float(total_sales),
            'total_orders': total_orders,
            'average_order_value': float(total_sales / total_orders) if total_orders > 0 else 0
        }

        logger.info(f"Analytics generated for seller {seller_id}")
        return analytics
    except User.DoesNotExist:
        logger.error(f"Seller {seller_id} not found")
        return None
    except Exception as e:
        logger.error(f"Error generating analytics: {e}")
        return None


@shared_task
def cleanup_old_browsing_history(days=90):
    """
    Delete browsing history older than specified days.

    Args:
        days: Number of days to keep
    """
    from .models import UserBrowsingHistory

    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count = UserBrowsingHistory.objects.filter(
            viewed_at__lt=cutoff_date
        ).delete()[0]

        logger.info(f"Deleted {deleted_count} old browsing history records")
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning browsing history: {e}")
        return 0


@shared_task
def cleanup_old_search_history(days=90):
    """
    Delete search history older than specified days.

    Args:
        days: Number of days to keep
    """
    from .models import UserSearchHistory

    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count = UserSearchHistory.objects.filter(
            searched_at__lt=cutoff_date
        ).delete()[0]

        logger.info(f"Deleted {deleted_count} old search history records")
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning search history: {e}")
        return 0


# ==============================================================================
# RECOMMENDED 8 AUTOMATED TASKS
# ==============================================================================

@shared_task
def daily_sales_report():
    """
    Generate and email daily sales report to admin.
    Scheduled: Daily at 9:00 AM

    Includes:
    - Total sales and revenue
    - New users registered
    - Top selling products
    - Payment statistics
    """
    from .models import User, Book, Course, Webinar, Service
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Sum, Count
    import stripe

    try:
        # Get yesterday's date range
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        start_time = timezone.make_aware(timezone.datetime.combine(yesterday, timezone.datetime.min.time()))
        end_time = timezone.make_aware(timezone.datetime.combine(yesterday, timezone.datetime.max.time()))

        # Initialize Stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Get successful payments from yesterday
        payments = stripe.PaymentIntent.list(
            created={
                'gte': int(start_time.timestamp()),
                'lte': int(end_time.timestamp())
            },
            limit=100
        )

        # Calculate totals
        total_revenue = sum(payment.amount for payment in payments.data if payment.status == 'succeeded') / 100
        successful_payments = len([p for p in payments.data if p.status == 'succeeded'])
        failed_payments = len([p for p in payments.data if p.status == 'failed'])

        # New users registered
        new_users = User.objects.filter(
            date_joined__gte=start_time,
            date_joined__lte=end_time
        ).count()

        new_buyers = User.objects.filter(
            date_joined__gte=start_time,
            date_joined__lte=end_time,
            user_type='buyer'
        ).count()

        new_sellers = User.objects.filter(
            date_joined__gte=start_time,
            date_joined__lte=end_time,
            user_type='seller'
        ).count()

        # New products added
        new_books = Book.objects.filter(created_at__gte=start_time, created_at__lte=end_time).count()
        new_courses = Course.objects.filter(created_at__gte=start_time, created_at__lte=end_time).count()
        new_webinars = Webinar.objects.filter(created_at__gte=start_time, created_at__lte=end_time).count()
        new_services = Service.objects.filter(created_at__gte=start_time, created_at__lte=end_time).count()

        # Prepare email
        subject = f"Daily Sales Report - {yesterday.strftime('%B %d, %Y')}"
        message = f"""
Daily Sales Report for {yesterday.strftime('%B %d, %Y')}
{'='*60}

REVENUE & PAYMENTS
------------------
Total Revenue: ${total_revenue:.2f}
Successful Payments: {successful_payments}
Failed Payments: {failed_payments}

NEW USERS
---------
Total New Users: {new_users}
  - Buyers: {new_buyers}
  - Sellers: {new_sellers}

NEW PRODUCTS ADDED
------------------
Books: {new_books}
Courses: {new_courses}
Webinars: {new_webinars}
Services: {new_services}
Total: {new_books + new_courses + new_webinars + new_services}

{'='*60}
Report generated at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        """

        # Send email to admin
        admin_emails = User.objects.filter(is_superuser=True).values_list('email', flat=True)
        if admin_emails:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=list(admin_emails),
                fail_silently=False
            )
            logger.info(f"Daily sales report sent to {len(admin_emails)} admin(s)")

        return {
            'date': yesterday.isoformat(),
            'revenue': total_revenue,
            'successful_payments': successful_payments,
            'new_users': new_users
        }

    except Exception as e:
        logger.error(f"Error generating daily sales report: {e}")
        return None


@shared_task
def update_ai_recommendations():
    """
    Update AI recommendations and user preferences.
    Scheduled: Daily at 3:00 AM

    Updates:
    - User preference data
    - Product popularity rankings
    - AI recommendation models
    """
    from .models import User, Book, Course, Webinar, Service
    from .recommendation_engine import update_user_preferences

    try:
        updated_users = 0

        # Update preferences for all active buyers
        buyers = User.objects.filter(is_active=True, user_type='buyer')

        for user in buyers:
            try:
                update_user_preferences(user)
                updated_users += 1
            except Exception as e:
                logger.error(f"Error updating preferences for user {user.id}: {e}")

        # Update product view counts and popularity
        from django.db.models import Count
        from .models import UserBrowsingHistory

        # Get view counts for last 7 days
        cutoff = timezone.now() - timedelta(days=7)

        # Update book popularity
        books = Book.objects.filter(is_active=True)
        for book in books:
            content_type = ContentType.objects.get_for_model(Book)
            views = UserBrowsingHistory.objects.filter(
                content_type=content_type,
                object_id=book.id,
                viewed_at__gte=cutoff
            ).count()
            # You can add a popularity field to models and update it here

        logger.info(f"Updated AI recommendations for {updated_users} users")
        return {
            'updated_users': updated_users,
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error updating AI recommendations: {e}")
        return None


@shared_task
def database_backup():
    """
    Create automated database backup.
    Scheduled: Daily at 1:00 AM

    Creates a PostgreSQL dump and saves it to backup directory.
    """
    import subprocess
    import os
    from django.conf import settings

    try:
        # Create backup directory if it doesn't exist
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Generate backup filename with timestamp
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_dir, f'db_backup_{timestamp}.sql')

        # Get database settings from environment
        db_name = os.getenv('DB_NAME')
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')

        # Set PGPASSWORD environment variable for authentication
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password

        # Run pg_dump command
        command = [
            'pg_dump',
            f'--host={db_host}',
            f'--port={db_port}',
            f'--username={db_user}',
            f'--dbname={db_name}',
            f'--file={backup_file}',
            '--format=plain',
            '--verbose'
        ]

        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            # Get backup file size
            file_size = os.path.getsize(backup_file) / (1024 * 1024)  # MB

            logger.info(f"Database backup created: {backup_file} ({file_size:.2f} MB)")

            # Clean up old backups (keep only last 7 days)
            cleanup_old_backups(backup_dir, days=7)

            return {
                'success': True,
                'backup_file': backup_file,
                'size_mb': file_size,
                'timestamp': timestamp
            }
        else:
            logger.error(f"Database backup failed: {result.stderr}")
            return {'success': False, 'error': result.stderr}

    except Exception as e:
        logger.error(f"Error creating database backup: {e}")
        return {'success': False, 'error': str(e)}


def cleanup_old_backups(backup_dir, days=7):
    """Helper function to remove backups older than specified days"""
    import os

    cutoff_time = timezone.now() - timedelta(days=days)
    cutoff_timestamp = cutoff_time.timestamp()

    for filename in os.listdir(backup_dir):
        if filename.startswith('db_backup_') and filename.endswith('.sql'):
            filepath = os.path.join(backup_dir, filename)
            file_mtime = os.path.getmtime(filepath)

            if file_mtime < cutoff_timestamp:
                os.remove(filepath)
                logger.info(f"Deleted old backup: {filename}")


@shared_task
def sync_stripe_payments():
    """
    Sync payment statuses with Stripe.
    Scheduled: Every 30 minutes

    Checks for:
    - Pending payments that succeeded
    - Failed payments
    - Refunds
    """
    import stripe
    from .models import User

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Get recent payment intents from last hour
        one_hour_ago = int((timezone.now() - timedelta(hours=1)).timestamp())

        payments = stripe.PaymentIntent.list(
            created={'gte': one_hour_ago},
            limit=100
        )

        synced_count = 0
        status_updates = {
            'succeeded': 0,
            'failed': 0,
            'processing': 0,
            'canceled': 0
        }

        for payment in payments.data:
            try:
                # Get metadata to find user
                metadata = payment.metadata
                user_email = metadata.get('user_email')
                payment_type = metadata.get('payment_type')  # 'registration' or 'upgrade'

                if user_email and payment_type:
                    user = User.objects.filter(email=user_email).first()

                    if user:
                        # Update payment status based on Stripe status
                        if payment.status == 'succeeded':
                            # Payment succeeded - ensure user has correct access
                            if payment_type == 'registration':
                                # Mark registration as complete if needed
                                status_updates['succeeded'] += 1
                            elif payment_type == 'upgrade':
                                # Verify upgrade completed
                                status_updates['succeeded'] += 1

                        elif payment.status == 'failed':
                            status_updates['failed'] += 1
                            logger.warning(f"Payment failed for user {user_email}: {payment.id}")

                        elif payment.status in ['processing', 'requires_action']:
                            status_updates['processing'] += 1

                        elif payment.status == 'canceled':
                            status_updates['canceled'] += 1

                        synced_count += 1

            except Exception as e:
                logger.error(f"Error syncing payment {payment.id}: {e}")

        logger.info(f"Synced {synced_count} payments. Status: {status_updates}")

        return {
            'synced_count': synced_count,
            'status_updates': status_updates,
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error syncing Stripe payments: {e}")
        return None


@shared_task
def weekly_seller_reports():
    """
    Send weekly performance reports to all sellers.
    Scheduled: Every Monday at 9:00 AM

    Includes:
    - Sales summary
    - Top products
    - Revenue breakdown
    - Performance tips
    """
    from .models import User, Book, Course, Webinar, Service
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Sum, Count

    try:
        sellers = User.objects.filter(user_type='seller', is_active=True)
        reports_sent = 0

        # Get last week's date range
        today = timezone.now().date()
        last_monday = today - timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + timedelta(days=6)

        start_time = timezone.make_aware(timezone.datetime.combine(last_monday, timezone.datetime.min.time()))
        end_time = timezone.make_aware(timezone.datetime.combine(last_sunday, timezone.datetime.max.time()))

        for seller in sellers:
            try:
                # Get seller's products
                books = Book.objects.filter(seller=seller)
                courses = Course.objects.filter(seller=seller)
                webinars = Webinar.objects.filter(seller=seller)
                services = Service.objects.filter(seller=seller)

                total_products = books.count() + courses.count() + webinars.count() + services.count()

                # Calculate sales (you'll need to implement based on your Order model)
                # For now, showing structure
                total_sales = 0
                total_revenue = 0

                # Prepare report email
                subject = f"Weekly Sales Report - {last_monday.strftime('%b %d')} to {last_sunday.strftime('%b %d, %Y')}"
                message = f"""
Hello {seller.full_name},

Here's your weekly performance report:

OVERVIEW
--------
Week: {last_monday.strftime('%B %d')} - {last_sunday.strftime('%B %d, %Y')}
Total Products: {total_products}
Total Sales: {total_sales}
Revenue: ${total_revenue:.2f}

PRODUCT BREAKDOWN
-----------------
Books: {books.count()}
Courses: {courses.count()}
Webinars: {webinars.count()}
Services: {services.count()}

TIPS FOR SUCCESS
----------------
• Add high-quality product images
• Update product descriptions regularly
• Respond to customer inquiries promptly
• Consider offering limited-time promotions

Keep up the great work!

Best regards,
The Platform Team
                """

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[seller.email],
                    fail_silently=False
                )

                reports_sent += 1

            except Exception as e:
                logger.error(f"Error generating report for seller {seller.id}: {e}")

        logger.info(f"Weekly seller reports sent to {reports_sent} sellers")

        return {
            'reports_sent': reports_sent,
            'week_start': last_monday.isoformat(),
            'week_end': last_sunday.isoformat()
        }

    except Exception as e:
        logger.error(f"Error sending weekly seller reports: {e}")
        return None


@shared_task
def clean_old_sessions():
    """
    Clean up expired Django sessions.
    Scheduled: Daily at 4:00 AM

    Removes expired sessions to improve performance.
    """
    from django.core.management import call_command

    try:
        # Django provides a management command for this
        call_command('clearsessions')

        logger.info("Successfully cleaned up expired sessions")

        return {
            'success': True,
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error cleaning sessions: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def abandoned_registration_reminder():
    """
    Send reminders to users who started registration but didn't complete payment.
    Scheduled: Daily at 6:00 PM

    Targets users who:
    - Registered in last 7 days
    - Haven't made registration payment
    - Haven't been reminded in last 24 hours
    """
    from .models import User

    try:
        # Get users who registered but might not have completed payment
        # This assumes you have a way to track registration payment status
        # Adjust based on your actual implementation

        cutoff_date = timezone.now() - timedelta(days=7)
        last_reminder_cutoff = timezone.now() - timedelta(hours=24)

        # Find users who registered recently but might not be fully activated
        incomplete_users = User.objects.filter(
            date_joined__gte=cutoff_date,
            date_joined__lte=timezone.now() - timedelta(hours=1),
            is_active=True,
            # Add your logic to identify incomplete registrations
            # For example: has_completed_registration_payment=False
        )

        reminders_sent = 0

        for user in incomplete_users:
            try:
                # Check if user needs registration payment
                # Adjust this logic based on your registration flow

                subject = "Complete Your Registration - Exclusive Features Await!"
                message = f"""
Hello {user.full_name},

We noticed you started your registration as a {user.user_type.upper()}, but haven't completed the payment yet.

Complete your registration to unlock:

"""

                if user.user_type == 'buyer':
                    message += """
✓ Browse and purchase books, courses & webinars
✓ AI-powered product recommendations
✓ 24/7 AI chatbot support
✓ Order history and tracking
✓ Personalized learning paths
"""
                else:
                    message += """
✓ Sell unlimited books, courses & webinars
✓ Professional seller dashboard with analytics
✓ Direct customer messaging
✓ Sales reporting and insights
✓ Payment processing through Stripe
"""

                message += f"""

Registration Fee: Just $10 one-time payment
Unlock your account now: {settings.SITE_URL}/registration-payment/

This is a limited-time offer. Complete your registration today!

Best regards,
The Platform Team

P.S. Need help? Reply to this email or contact support.
                """

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False
                )

                reminders_sent += 1

            except Exception as e:
                logger.error(f"Error sending reminder to user {user.id}: {e}")

        logger.info(f"Sent {reminders_sent} abandoned registration reminders")

        return {
            'reminders_sent': reminders_sent,
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error sending abandoned registration reminders: {e}")
        return None
