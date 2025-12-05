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
