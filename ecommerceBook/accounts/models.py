"""
Database models for ecommerceBook application.
Refactored for better organization, DRY principles, and database constraints.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from decimal import Decimal
import secrets
import logging

from .validators import (
    validate_image_size, validate_image_extension,
    validate_book_file_size, validate_book_extension,
    validate_course_file_size, validate_course_extension,
    validate_webinar_file_size, validate_webinar_extension,
    validate_positive_price
)

logger = logging.getLogger(__name__)


# ==============================================================================
# USER & AUTHENTICATION MODELS
# ==============================================================================

class User(AbstractUser):
    """
    Custom user model with buyer/seller role support.
    Extends Django's AbstractUser with additional fields.
    """
    USER_TYPE_CHOICES = [
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
    ]

    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPE_CHOICES,
        default='buyer',
        db_index=True,
        help_text="User role in the system"
    )
    full_name = models.CharField(max_length=255, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)  # Keep for buyers

    # Seller's Stripe Connect Account ID for receiving payments
    stripe_account_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Seller's Stripe Connect Account ID for receiving payments"
    )
    stripe_account_verified = models.BooleanField(
        default=False,
        help_text="Whether the Stripe account has been verified"
    )
    stripe_connect_status = models.CharField(
        max_length=20,
        choices=[
            ('not_started', 'Not Started'),
            ('pending', 'Pending'),
            ('active', 'Active'),
            ('restricted', 'Restricted'),
        ],
        default='not_started',
        help_text="Stripe Connect onboarding status"
    )

    profile_image = models.ImageField(
        upload_to='profile_images/',
        blank=True,
        null=True,
        validators=[validate_image_size, validate_image_extension]
    )

    # Account status and payment tracking
    ACCOUNT_STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
    ]
    account_status = models.CharField(
        max_length=20,
        choices=ACCOUNT_STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Account activation status"
    )

    # DEPRECATED: Kept for backward compatibility, use buyer_access_paid/seller_access_paid instead
    registration_paid = models.BooleanField(
        default=False,
        help_text="DEPRECATED: Whether registration fee has been paid"
    )

    # Separate payment tracking for buyer and seller roles
    buyer_access_paid = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether buyer dashboard access has been paid"
    )
    seller_access_paid = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether seller dashboard access has been paid"
    )

    # Buyer role payment details
    buyer_payment_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When buyer access payment was completed"
    )
    buyer_payment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Amount paid for buyer access"
    )
    buyer_stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Stripe payment intent ID for buyer access"
    )

    # Seller role payment details
    seller_payment_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When seller access payment was completed"
    )
    seller_payment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Amount paid for seller access"
    )
    seller_stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Stripe payment intent ID for seller access"
    )

    # Shared Stripe customer ID
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Stripe customer ID"
    )

    # DEPRECATED: Kept for backward compatibility
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="DEPRECATED: Stripe payment intent ID for registration"
    )
    registration_paid_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="DEPRECATED: When registration payment was completed"
    )
    registration_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="DEPRECATED: Amount paid for registration"
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=['user_type', 'is_active']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"{self.username} ({self.user_type})"

    def get_full_name(self):
        """Return full name or username as fallback"""
        return self.full_name or self.username

    def has_buyer_access(self):
        """Check if user has paid for buyer dashboard access"""
        return self.buyer_access_paid

    def has_seller_access(self):
        """Check if user has paid for seller dashboard access"""
        return self.seller_access_paid

    def has_current_role_access(self):
        """Check if user has paid for their current role"""
        if self.user_type == 'buyer':
            return self.buyer_access_paid
        elif self.user_type == 'seller':
            return self.seller_access_paid
        return False

    def get_unpaid_roles(self):
        """Get list of roles that haven't been paid for"""
        unpaid = []
        if not self.buyer_access_paid:
            unpaid.append('buyer')
        if not self.seller_access_paid:
            unpaid.append('seller')
        return unpaid

    def get_total_paid_amount(self):
        """Calculate total amount paid for all roles"""
        total = 0
        if self.buyer_access_paid:
            total += float(self.buyer_payment_amount)
        if self.seller_access_paid:
            total += float(self.seller_payment_amount)
        return total

    def can_add_products(self):
        """Check if seller can add products (requires Stripe Account ID)"""
        if self.user_type != 'seller' and not self.seller_access_paid:
            return False
        return bool(self.stripe_account_id)

    def needs_stripe_account_setup(self):
        """Check if seller needs to set up Stripe account"""
        return self.seller_access_paid and not self.stripe_account_id


class PasswordResetToken(models.Model):
    """
    Secure password reset tokens with expiration.
    Auto-invalidates old tokens when new ones are created.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.CharField(max_length=6, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_used', 'created_at']),
        ]

    def __str__(self):
        return f"Token for {self.user.email} - {self.token}"

    def is_expired(self):
        """Check if token has expired (15 minutes)"""
        from django.conf import settings
        expiry_minutes = getattr(settings, 'PASSWORD_RESET_TOKEN_EXPIRY', 15)
        expiry_time = self.created_at + timedelta(minutes=expiry_minutes)
        return timezone.now() > expiry_time

    def is_valid(self):
        """Check if token is valid (not used and not expired)"""
        return not self.is_used and not self.is_expired()

    @staticmethod
    def generate_token():
        """Generate a secure random 6-digit token"""
        return str(secrets.randbelow(900000) + 100000)

    @classmethod
    def create_token(cls, user):
        """
        Create new token for user and invalidate old ones.

        Args:
            user: User instance

        Returns:
            PasswordResetToken instance
        """
        # Invalidate any existing unused tokens
        cls.objects.filter(user=user, is_used=False).update(is_used=True)

        # Create new token
        token = cls.generate_token()
        return cls.objects.create(user=user, token=token)


# ==============================================================================
# PRODUCT MODELS
# ==============================================================================

class Category(models.Model):
    """Product categories for organizing books, courses, and webinars"""
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, help_text="Category description")
    is_active = models.BooleanField(default=True, help_text="Active categories shown to users")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_products_count(self):
        """Get total count of products in this category"""
        cache_key = f'category_{self.id}_products_count'
        count = cache.get(cache_key)

        if count is None:
            count = (
                self.books.filter(is_active=True, is_deleted=False).count() +
                self.courses.filter(is_active=True, is_deleted=False).count() +
                self.webinars.filter(is_active=True, is_deleted=False).count() +
                self.services.filter(is_active=True, is_deleted=False).count()
            )
            cache.set(cache_key, count, 300)  # Cache for 5 minutes

        return count


class SiteSettings(models.Model):
    """
    Site-wide settings for the marketplace platform.
    This is a singleton model - only one instance should exist.
    """
    platform_name = models.CharField(
        max_length=100,
        default="Marketplace Platform",
        help_text="Name of the marketplace platform"
    )
    platform_stripe_account_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Platform owner's Stripe Account ID for receiving commissions (starts with 'acct_')"
    )
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of each sale that goes to platform (0-100)"
    )
    commission_enabled = models.BooleanField(
        default=True,
        help_text="Enable/disable commission system"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return f"{self.platform_name} Settings"

    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)"""
        if not self.pk and SiteSettings.objects.exists():
            # If trying to create a new instance when one already exists
            raise ValidationError('Only one SiteSettings instance is allowed')
        return super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Get or create the site settings instance"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings

    def get_commission_amount(self, total_amount):
        """Calculate commission amount from total"""
        if not self.commission_enabled:
            return Decimal('0.00')
        commission = (total_amount * self.commission_percentage) / Decimal('100')
        return commission.quantize(Decimal('0.01'))

    def get_seller_amount(self, total_amount):
        """Calculate seller amount after commission"""
        commission = self.get_commission_amount(total_amount)
        return total_amount - commission


class BaseProduct(models.Model):
    """
    Abstract base model for all product types (Book, Course, Webinar).
    Implements common fields and methods to follow DRY principle.
    """
    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,  # Prevent deletion of categories with products
        related_name='%(class)ss'  # Dynamic related name: books, courses, webinars
    )
    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='%(class)ss',
        limit_choices_to={'user_type': 'seller'}
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)  # Soft delete
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'is_deleted', '-created_at']),
            models.Index(fields=['seller', 'is_active']),
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self):
        return self.title

    def soft_delete(self):
        """Soft delete the product instead of hard delete"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['is_deleted', 'deleted_at', 'is_active'])
        logger.info(f"{self.__class__.__name__} {self.id} soft deleted")

    def restore(self):
        """Restore a soft-deleted product"""
        self.is_deleted = False
        self.deleted_at = None
        self.is_active = True
        self.save(update_fields=['is_deleted', 'deleted_at', 'is_active'])
        logger.info(f"{self.__class__.__name__} {self.id} restored")

    def get_average_rating(self):
        """
        Calculate average rating from order items.
        Cached for performance.
        """
        cache_key = f'{self.__class__.__name__.lower()}_{self.id}_avg_rating'
        avg_rating = cache.get(cache_key)

        if avg_rating is None:
            from django.db.models import Avg
            content_type = ContentType.objects.get_for_model(self)
            ratings = Rating.objects.filter(
                order_item__content_type=content_type,
                order_item__object_id=self.id
            ).aggregate(avg=Avg('rating'))

            avg_rating = round(ratings['avg'], 1) if ratings['avg'] else 0
            cache.set(cache_key, avg_rating, 300)  # Cache for 5 minutes

        return avg_rating

    def get_ratings_count(self):
        """Get total number of ratings"""
        cache_key = f'{self.__class__.__name__.lower()}_{self.id}_ratings_count'
        count = cache.get(cache_key)

        if count is None:
            content_type = ContentType.objects.get_for_model(self)
            count = Rating.objects.filter(
                order_item__content_type=content_type,
                order_item__object_id=self.id
            ).count()
            cache.set(cache_key, count, 300)

        return count

    def clear_rating_cache(self):
        """Clear cached rating data"""
        cache_key_avg = f'{self.__class__.__name__.lower()}_{self.id}_avg_rating'
        cache_key_count = f'{self.__class__.__name__.lower()}_{self.id}_ratings_count'
        cache.delete_many([cache_key_avg, cache_key_count])


class Book(BaseProduct):
    """Digital book products (PDF, EPUB, MOBI)"""
    book_image = models.ImageField(
        upload_to='book_images/',
        blank=True,
        null=True,
        validators=[validate_image_size, validate_image_extension]
    )
    book_file = models.FileField(
        upload_to='book_files/',
        validators=[validate_book_file_size, validate_book_extension]
    )

    class Meta(BaseProduct.Meta):
        verbose_name = "Book"
        verbose_name_plural = "Books"


class Course(BaseProduct):
    """Online course products"""
    course_image = models.ImageField(
        upload_to='course_images/',
        blank=True,
        null=True,
        validators=[validate_image_size, validate_image_extension]
    )
    course_file = models.FileField(
        upload_to='course_files/',
        validators=[validate_course_file_size, validate_course_extension]
    )
    duration_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Course duration in hours"
    )

    class Meta(BaseProduct.Meta):
        verbose_name = "Course"
        verbose_name_plural = "Courses"


class Webinar(BaseProduct):
    """Recorded webinar products"""
    webinar_image = models.ImageField(
        upload_to='webinar_images/',
        blank=True,
        null=True,
        validators=[validate_image_size, validate_image_extension]
    )
    webinar_file = models.FileField(
        upload_to='webinar_files/',
        validators=[validate_webinar_file_size, validate_webinar_extension]
    )
    scheduled_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Original webinar date"
    )

    class Meta(BaseProduct.Meta):
        verbose_name = "Webinar"
        verbose_name_plural = "Webinars"


class Service(BaseProduct):
    """Professional services offered by sellers"""
    service_image = models.ImageField(
        upload_to='service_images/',
        blank=True,
        null=True,
        validators=[validate_image_size, validate_image_extension],
        help_text="Optional service image"
    )

    class Meta(BaseProduct.Meta):
        verbose_name = "Service"
        verbose_name_plural = "Services"


# ==============================================================================
# SHOPPING CART & ORDERS
# ==============================================================================

class Cart(models.Model):
    """Shopping cart for buyers"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cart"
        verbose_name_plural = "Carts"

    def __str__(self):
        return f"Cart for {self.user.username}"

    def get_total_price(self):
        """Calculate total cart price"""
        return sum(item.get_total_price() for item in self.items.all())

    def get_total_items(self):
        """Count total items in cart"""
        return self.items.count()

    def clear(self):
        """Remove all items from cart"""
        self.items.all().delete()
        logger.info(f"Cart {self.id} cleared for user {self.user.username}")


class CartItem(models.Model):
    """Individual items in shopping cart using generic foreign keys"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        unique_together = ('cart', 'content_type', 'object_id')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.content_object.title} in {self.cart.user.username}'s cart"

    def get_total_price(self):
        """Calculate total price for this cart item"""
        return self.content_object.price * self.quantity


class Order(models.Model):
    """Customer orders"""
    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(
        max_length=25,
        unique=True,
        db_index=True,
        help_text="Unique order number in format: ORD-YYYY-MM-NNNNNN"
    )
    status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS_CHOICES,
        default='completed',
        db_index=True
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    stripe_session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text="Stripe Checkout Session ID to prevent duplicate orders"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Order #{self.order_number} by {self.user.username}"

    @classmethod
    def generate_order_number(cls):
        """
        Generate professional unique order number with pattern: ORD-YYYY-MM-NNNNNN
        Example: ORD-2025-12-000001

        - ORD: Prefix for order
        - YYYY: Current year
        - MM: Current month
        - NNNNNN: Sequential 6-digit number (resets monthly)
        """
        from django.db import transaction
        import random

        # Get current year and month (timezone aware)
        now = timezone.now()
        year = now.strftime('%Y')
        month = now.strftime('%m')

        # Use database transaction to ensure thread-safe order number generation
        with transaction.atomic():
            # Get the count of orders in current month for sequential numbering
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Find the highest existing order number for this month
            existing_orders = cls.objects.filter(
                order_number__startswith=f"ORD-{year}-{month}-"
            ).values_list('order_number', flat=True)

            if existing_orders:
                # Extract the sequential numbers and find the max
                max_seq = 0
                for order_num in existing_orders:
                    try:
                        seq_part = order_num.split('-')[-1]
                        max_seq = max(max_seq, int(seq_part))
                    except (ValueError, IndexError):
                        continue
                next_seq = max_seq + 1
            else:
                next_seq = 1

            # Generate order number with sequential counter
            max_attempts = 100
            for attempt in range(max_attempts):
                sequential_number = next_seq + attempt
                order_number = f"ORD-{year}-{month}-{sequential_number:06d}"

                # Check if this order number already exists
                if not cls.objects.filter(order_number=order_number).exists():
                    return order_number

            # Fallback to random if sequential fails (extremely unlikely)
            max_fallback_attempts = 1000
            for _ in range(max_fallback_attempts):
                random_number = random.randint(1, 999999)
                order_number = f"ORD-{year}-{month}-{random_number:06d}"
                if not cls.objects.filter(order_number=order_number).exists():
                    return order_number

            # If all else fails, raise an error
            raise ValueError("Unable to generate unique order number after multiple attempts")


class OrderItem(models.Model):
    """Items within an order using generic foreign keys"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Price at time of purchase"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.content_object.title} in Order #{self.order.order_number}"

    def get_total_price(self):
        """Calculate total price for this order item"""
        return self.price * self.quantity


# ==============================================================================
# AI & CHATBOT MODELS
# ==============================================================================

class ChatSession(models.Model):
    """Chat sessions for AI chatbot"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Chat Session"
        verbose_name_plural = "Chat Sessions"
        ordering = ['-created_at']

    def __str__(self):
        return f"Session {self.session_id} - {self.user.full_name}"

    def get_messages_count(self):
        """Get count of messages in session"""
        return self.messages.count()


class ChatMessage(models.Model):
    """Individual chat messages"""
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    question = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.full_name}: {self.question[:50]}..."


# ==============================================================================
# NOTIFICATION SYSTEM
# ==============================================================================

class Notification(models.Model):
    """User notifications"""
    NOTIFICATION_TYPES = [
        ('order_created', 'Order Created'),
        ('order_completed', 'Order Completed'),
        ('new_sale', 'New Sale'),
        ('product_purchased', 'Product Purchased'),
        ('cart_reminder', 'Cart Reminder'),
        ('price_change', 'Price Change'),
        ('new_message', 'New Message'),
        ('account_update', 'Account Update'),
        ('general', 'General'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        default='general',
        db_index=True
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True, null=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.title}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])


# ==============================================================================
# RATING & REVIEW SYSTEM
# ==============================================================================

class Rating(models.Model):
    """Product ratings by buyers"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='rating')
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    review = models.TextField(blank=True, help_text="Optional review text")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rating"
        verbose_name_plural = "Ratings"
        ordering = ['-created_at']
        unique_together = ('user', 'order_item')
        indexes = [
            models.Index(fields=['rating', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.rating} stars for {self.order_item.content_object.title}"

    def save(self, *args, **kwargs):
        """Override save to clear product rating cache"""
        super().save(*args, **kwargs)
        # Clear the cached rating for the product
        product = self.order_item.content_object
        if hasattr(product, 'clear_rating_cache'):
            product.clear_rating_cache()


# ==============================================================================
# RECOMMENDATION ENGINE MODELS
# ==============================================================================

class UserBrowsingHistory(models.Model):
    """Track which products users view"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='browsing_history')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    product = GenericForeignKey('content_type', 'object_id')
    viewed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "User Browsing History"
        verbose_name_plural = "User Browsing Histories"
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['user', '-viewed_at']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.user.username} viewed {self.content_type.model} at {self.viewed_at}"


class UserSearchHistory(models.Model):
    """Track user search queries"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='search_history',
        null=True,
        blank=True
    )
    query = models.CharField(max_length=255, db_index=True)
    searched_at = models.DateTimeField(auto_now_add=True, db_index=True)
    results_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = "User Search History"
        verbose_name_plural = "User Search Histories"
        ordering = ['-searched_at']
        indexes = [
            models.Index(fields=['user', '-searched_at']),
            models.Index(fields=['query', '-searched_at']),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        return f"{user_str} searched '{self.query}' at {self.searched_at}"


class UserPreference(models.Model):
    """Store computed user preferences for faster recommendations"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preference')
    favorite_categories = models.JSONField(
        default=list,
        blank=True,
        help_text="List of category IDs"
    )
    interests_keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Keywords from searches and chatbot"
    )
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Preference"
        verbose_name_plural = "User Preferences"

    def __str__(self):
        return f"{self.user.username}'s preferences"


# ==============================================================================
# BUYER-SELLER CHAT SYSTEM
# ==============================================================================

class ServiceChat(models.Model):
    """
    Direct messaging between buyers and sellers for purchased services.
    Each buyer-seller-service combination has one conversation.
    """
    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='buyer_chats',
        limit_choices_to={'user_type': 'buyer'}
    )
    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='seller_chats',
        limit_choices_to={'user_type': 'seller'}
    )
    service = models.ForeignKey(
        'Service',
        on_delete=models.CASCADE,
        related_name='service_chats'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Service Chat"
        verbose_name_plural = "Service Chats"
        ordering = ['-updated_at']
        unique_together = ('buyer', 'seller', 'service')
        indexes = [
            models.Index(fields=['buyer', '-updated_at']),
            models.Index(fields=['seller', '-updated_at']),
        ]

    def __str__(self):
        return f"Chat: {self.buyer.full_name} <-> {self.seller.full_name} about {self.service.title}"

    def get_unread_count(self, user):
        """Get count of unread messages for a specific user"""
        return self.messages.filter(is_read=False).exclude(sender=user).count()

    def get_last_message(self):
        """Get the most recent message in this chat"""
        return self.messages.order_by('-created_at').first()


class ServiceChatMessage(models.Model):
    """Individual messages in a service chat conversation"""
    chat = models.ForeignKey(
        ServiceChat,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_service_messages'
    )
    message = models.TextField(help_text="Message content")
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Service Chat Message"
        verbose_name_plural = "Service Chat Messages"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['chat', 'created_at']),
            models.Index(fields=['chat', 'is_read']),
        ]

    def __str__(self):
        return f"{self.sender.full_name}: {self.message[:50]}..."

    def save(self, *args, **kwargs):
        """Update chat's updated_at when new message is saved"""
        super().save(*args, **kwargs)
        # Update the parent chat's updated_at timestamp
        self.chat.save(update_fields=['updated_at'])
