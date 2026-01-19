from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.safestring import mark_safe
from .models import (
    User, PasswordResetToken, Category, SiteSettings, Book, Course, Webinar, Service,
    UserBrowsingHistory, UserSearchHistory, UserPreference,
    ServiceChat, ServiceChatMessage, ContactMessage
)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'full_name', 'phone_number', 'user_type', 'has_profile_image', 'is_staff', 'date_joined')
    list_filter = ('user_type', 'is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'full_name', 'phone_number')
    ordering = ('-date_joined',)
    readonly_fields = ('profile_image_preview',)

    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('full_name', 'phone_number', 'user_type')}),
        ('Profile Image', {'fields': ('profile_image', 'profile_image_preview')}),
    )

    def has_profile_image(self, obj):
        """Show if user has a profile image"""
        return bool(obj.profile_image)
    has_profile_image.boolean = True
    has_profile_image.short_description = 'Has Profile Image'

    def profile_image_preview(self, obj):
        """Show profile image preview in admin"""
        if obj.profile_image:
            return mark_safe(f'<img src="{obj.profile_image.url}" style="max-width: 100px; max-height: 100px; border-radius: 50%; object-fit: cover;" />')
        return "No image uploaded"
    profile_image_preview.short_description = 'Profile Image Preview'

@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'is_used', 'is_expired')
    list_filter = ('is_used', 'created_at')
    search_fields = ('user__email', 'user__username', 'token')
    ordering = ('-created_at',)
    readonly_fields = ('token', 'created_at')
    
    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_category_type', 'parent', 'get_subcategory_count', 'is_active', 'approval_status', 'created_by', 'created_at')
    list_filter = ('is_main_category', 'is_active', 'approval_status', 'created_at')
    search_fields = ('name', 'slug', 'description', 'created_by__username')
    ordering = ('parent__name', 'name')
    readonly_fields = ('slug', 'created_at', 'updated_at', 'subcategory_list')
    autocomplete_fields = ['parent', 'created_by']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'parent', 'is_main_category', 'is_active')
        }),
        ('Approval', {
            'fields': ('is_approved', 'approval_status', 'created_by'),
            'description': 'Category approval settings'
        }),
        ('Subcategories', {
            'fields': ('subcategory_list',),
            'classes': ('collapse',),
            'description': 'List of subcategories under this category'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_category_type(self, obj):
        """Display category type"""
        return "Main Category" if obj.is_main_category else "Sub-Category"
    get_category_type.short_description = 'Type'

    def get_subcategory_count(self, obj):
        """Display count of subcategories"""
        if obj.is_main_category:
            count = obj.subcategories.count()
            return f"{count} sub-categories"
        return "-"
    get_subcategory_count.short_description = 'Subcategories'

    def subcategory_list(self, obj):
        """Display list of subcategories"""
        if obj.is_main_category:
            subs = obj.subcategories.all()
            if subs:
                html = '<ul style="margin-left: 20px;">'
                for sub in subs:
                    status_color = 'green' if sub.is_approved else 'orange'
                    html += f'<li><strong>{sub.name}</strong> <span style="color: {status_color};">({sub.approval_status})</span></li>'
                html += '</ul>'
                return mark_safe(html)
            return "No subcategories yet"
        return "Not applicable (this is a sub-category)"
    subcategory_list.short_description = 'Subcategories List'

    def save_model(self, request, obj, form, change):
        """Auto-generate slug if not provided"""
        if not obj.slug:
            from django.utils.text import slugify
            base_slug = slugify(obj.name)
            slug = base_slug
            counter = 1

            # Ensure uniqueness
            while Category.objects.filter(slug=slug).exclude(pk=obj.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            obj.slug = slug

        super().save_model(request, obj, form, change)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """
    Admin interface for site-wide marketplace settings.
    Only one instance is allowed (singleton).
    """
    list_display = ('platform_name', 'commission_percentage', 'commission_enabled', 'has_platform_account', 'updated_at')
    readonly_fields = ('created_at', 'updated_at', 'commission_preview')

    fieldsets = (
        ('Platform Information', {
            'fields': ('platform_name',),
            'description': 'Basic platform information'
        }),
        ('Commission Settings', {
            'fields': ('commission_enabled', 'commission_percentage', 'commission_preview'),
            'description': 'Configure marketplace commission rates'
        }),
        ('Payment Account', {
            'fields': ('platform_stripe_account_id',),
            'description': 'Platform owner\'s Stripe Account ID for receiving commissions. Get this from your Stripe Dashboard.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_platform_account(self, obj):
        """Check if platform Stripe account is configured"""
        return bool(obj.platform_stripe_account_id)
    has_platform_account.boolean = True
    has_platform_account.short_description = 'Stripe Account Set'

    def commission_preview(self, obj):
        """Show commission calculation examples"""
        if not obj.commission_enabled:
            return mark_safe('<p style="color: #dc3545;">Commission is currently <strong>DISABLED</strong></p>')

        examples = [
            ('$10.00', 10),
            ('$50.00', 50),
            ('$100.00', 100),
            ('$500.00', 500),
        ]

        html = '<table style="border-collapse: collapse; margin-top: 10px;">'
        html += '<tr style="background-color: #f8f9fa;"><th style="padding: 8px; border: 1px solid #dee2e6;">Sale Price</th><th style="padding: 8px; border: 1px solid #dee2e6;">Platform Gets</th><th style="padding: 8px; border: 1px solid #dee2e6;">Seller Gets</th></tr>'

        for price_str, price_val in examples:
            from decimal import Decimal
            price = Decimal(str(price_val))
            commission = obj.get_commission_amount(price)
            seller_amount = obj.get_seller_amount(price)
            html += f'<tr><td style="padding: 8px; border: 1px solid #dee2e6; text-align: center;">{price_str}</td>'
            html += f'<td style="padding: 8px; border: 1px solid #dee2e6; text-align: center; color: #28a745; font-weight: bold;">${commission}</td>'
            html += f'<td style="padding: 8px; border: 1px solid #dee2e6; text-align: center;">${seller_amount}</td></tr>'

        html += '</table>'
        html += f'<p style="margin-top: 10px; color: #6c757d;"><small>Current commission rate: <strong>{obj.commission_percentage}%</strong></small></p>'
        return mark_safe(html)
    commission_preview.short_description = 'Commission Examples'

    def has_add_permission(self, request):
        """Prevent adding more than one instance"""
        if SiteSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the settings instance"""
        return False


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'category', 'price', 'is_active', 'created_at')
    list_filter = ('category', 'is_active', 'created_at', 'seller__user_type')
    search_fields = ('title', 'description', 'seller__username', 'seller__full_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'book_image_preview')

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'price', 'category', 'seller', 'is_active')
        }),
        ('Files', {
            'fields': ('book_image', 'book_image_preview', 'book_file')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def book_image_preview(self, obj):
        """Show book image preview in admin"""
        if obj.book_image:
            return mark_safe(f'<img src="{obj.book_image.url}" style="max-width: 200px; max-height: 200px; object-fit: cover;" />')
        return "No image uploaded"
    book_image_preview.short_description = 'Book Image Preview'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'category', 'price', 'is_active', 'created_at')
    list_filter = ('category', 'is_active', 'created_at', 'seller__user_type')
    search_fields = ('title', 'description', 'seller__username', 'seller__full_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'course_image_preview')

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'price', 'category', 'seller', 'is_active')
        }),
        ('Files', {
            'fields': ('course_image', 'course_image_preview', 'course_file')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def course_image_preview(self, obj):
        """Show course image preview in admin"""
        if obj.course_image:
            return mark_safe(f'<img src="{obj.course_image.url}" style="max-width: 200px; max-height: 200px; object-fit: cover;" />')
        return "No image uploaded"
    course_image_preview.short_description = 'Course Image Preview'


@admin.register(Webinar)
class WebinarAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'category', 'price', 'is_active', 'created_at')
    list_filter = ('category', 'is_active', 'created_at', 'seller__user_type')
    search_fields = ('title', 'description', 'seller__username', 'seller__full_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'webinar_image_preview')

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'price', 'category', 'seller', 'is_active')
        }),
        ('Files', {
            'fields': ('webinar_image', 'webinar_image_preview', 'webinar_file')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def webinar_image_preview(self, obj):
        """Show webinar image preview in admin"""
        if obj.webinar_image:
            return mark_safe(f'<img src="{obj.webinar_image.url}" style="max-width: 200px; max-height: 200px; object-fit: cover;" />')
        return "No image uploaded"
    webinar_image_preview.short_description = 'Webinar Image Preview'


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'category', 'price', 'is_active', 'created_at')
    list_filter = ('category', 'is_active', 'created_at', 'seller__user_type')
    search_fields = ('title', 'description', 'seller__username', 'seller__full_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'service_image_preview')

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'price', 'category', 'seller', 'is_active')
        }),
        ('Image', {
            'fields': ('service_image', 'service_image_preview')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def service_image_preview(self, obj):
        """Show service image preview in admin"""
        if obj.service_image:
            return mark_safe(f'<img src="{obj.service_image.url}" style="max-width: 200px; max-height: 200px; object-fit: cover;" />')
        return "No image uploaded"
    service_image_preview.short_description = 'Service Image Preview'


@admin.register(UserBrowsingHistory)
class UserBrowsingHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_product_title', 'content_type', 'viewed_at')
    list_filter = ('content_type', 'viewed_at')
    search_fields = ('user__username', 'user__full_name')
    ordering = ('-viewed_at',)
    readonly_fields = ('user', 'content_type', 'object_id', 'viewed_at')

    def get_product_title(self, obj):
        """Get the title of the viewed product"""
        if obj.product:
            return obj.product.title
        return "N/A"
    get_product_title.short_description = 'Product'


@admin.register(UserSearchHistory)
class UserSearchHistoryAdmin(admin.ModelAdmin):
    list_display = ('get_user', 'query', 'results_count', 'searched_at')
    list_filter = ('searched_at',)
    search_fields = ('user__username', 'user__full_name', 'query')
    ordering = ('-searched_at',)
    readonly_fields = ('user', 'query', 'results_count', 'searched_at')

    def get_user(self, obj):
        """Get username or Anonymous"""
        return obj.user.username if obj.user else "Anonymous"
    get_user.short_description = 'User'


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_categories_count', 'get_keywords_count', 'last_updated')
    list_filter = ('last_updated',)
    search_fields = ('user__username', 'user__full_name')
    ordering = ('-last_updated',)
    readonly_fields = ('user', 'favorite_categories', 'interests_keywords', 'last_updated')

    def get_categories_count(self, obj):
        """Get count of favorite categories"""
        return len(obj.favorite_categories) if obj.favorite_categories else 0
    get_categories_count.short_description = 'Favorite Categories'

    def get_keywords_count(self, obj):
        """Get count of interest keywords"""
        return len(obj.interests_keywords) if obj.interests_keywords else 0
    get_keywords_count.short_description = 'Interest Keywords'


class ServiceChatMessageInline(admin.TabularInline):
    """Inline display of chat messages within ServiceChat admin"""
    model = ServiceChatMessage
    extra = 0
    readonly_fields = ('sender', 'message', 'is_read', 'created_at')
    can_delete = False
    max_num = 10  # Show only last 10 messages in inline
    ordering = ('-created_at',)


@admin.register(ServiceChat)
class ServiceChatAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'seller', 'service', 'get_last_message_preview', 'get_unread_messages', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('buyer__username', 'buyer__full_name', 'seller__username', 'seller__full_name', 'service__title')
    ordering = ('-updated_at',)
    readonly_fields = ('buyer', 'seller', 'service', 'created_at', 'updated_at')
    inlines = [ServiceChatMessageInline]

    def get_last_message_preview(self, obj):
        """Show preview of last message"""
        last_msg = obj.get_last_message()
        if last_msg:
            return f"{last_msg.sender.full_name}: {last_msg.message[:50]}..."
        return "No messages yet"
    get_last_message_preview.short_description = 'Last Message'

    def get_unread_messages(self, obj):
        """Show count of unread messages"""
        return obj.messages.filter(is_read=False).count()
    get_unread_messages.short_description = 'Unread Messages'


@admin.register(ServiceChatMessage)
class ServiceChatMessageAdmin(admin.ModelAdmin):
    list_display = ('get_chat_info', 'sender', 'get_message_preview', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at', 'sender__user_type')
    search_fields = ('chat__buyer__username', 'chat__seller__username', 'sender__username', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('chat', 'sender', 'message', 'is_read', 'created_at')

    def get_chat_info(self, obj):
        """Show chat participants"""
        return f"{obj.chat.buyer.full_name} <-> {obj.chat.seller.full_name}"
    get_chat_info.short_description = 'Chat'

    def get_message_preview(self, obj):
        """Show message preview"""
        return obj.message[:100] + "..." if len(obj.message) > 100 else obj.message
    get_message_preview.short_description = 'Message'


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    """
    Admin interface for managing contact form submissions.
    Displays all submissions with filtering, search, and status management.
    """
    list_display = ('name', 'email', 'subject', 'status', 'email_sent', 'created_at', 'get_user_type')
    list_filter = ('status', 'email_sent', 'created_at', 'user__user_type')
    search_fields = ('name', 'email', 'subject', 'message', 'ip_address')
    ordering = ('-created_at',)
    readonly_fields = ('user', 'ip_address', 'user_agent', 'email_sent', 'created_at', 'read_at', 'replied_at', 'formatted_message')
    actions = ['mark_as_read', 'mark_as_replied', 'mark_as_archived']

    fieldsets = (
        ('Contact Information', {
            'fields': ('name', 'email', 'subject')
        }),
        ('Message', {
            'fields': ('formatted_message',),
            'description': 'Original message from the contact form'
        }),
        ('User Information', {
            'fields': ('user',),
            'description': 'Linked user account (if they were logged in)'
        }),
        ('Status & Response', {
            'fields': ('status', 'admin_notes'),
            'description': 'Manage message status and add internal notes'
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'email_sent'),
            'classes': ('collapse',),
            'description': 'Technical information for spam prevention'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'read_at', 'replied_at'),
            'classes': ('collapse',)
        }),
    )

    def get_user_type(self, obj):
        """Display user type if message is from a logged-in user"""
        if obj.user:
            return obj.user.user_type.upper()
        return "Guest"
    get_user_type.short_description = 'User Type'

    def formatted_message(self, obj):
        """Display message with proper formatting"""
        return mark_safe(f'<div style="white-space: pre-wrap; padding: 10px; background-color: #f8f9fa; border-radius: 5px; border-left: 4px solid #007bff;">{obj.message}</div>')
    formatted_message.short_description = 'Message Content'

    def mark_as_read(self, request, queryset):
        """Mark selected messages as read"""
        from django.utils import timezone
        updated = 0
        for message in queryset:
            if message.status == 'new':
                message.status = 'read'
                message.read_at = timezone.now()
                message.save(update_fields=['status', 'read_at'])
                updated += 1

        self.message_user(
            request,
            f"{updated} message(s) marked as read.",
            'success' if updated > 0 else 'warning'
        )
    mark_as_read.short_description = "Mark selected as Read"

    def mark_as_replied(self, request, queryset):
        """Mark selected messages as replied"""
        from django.utils import timezone
        updated = 0
        for message in queryset:
            if message.status in ['new', 'read']:
                message.status = 'replied'
                message.replied_at = timezone.now()
                message.save(update_fields=['status', 'replied_at'])
                updated += 1

        self.message_user(
            request,
            f"{updated} message(s) marked as replied.",
            'success' if updated > 0 else 'warning'
        )
    mark_as_replied.short_description = "Mark selected as Replied"

    def mark_as_archived(self, request, queryset):
        """Archive selected messages"""
        updated = queryset.update(status='archived')
        self.message_user(
            request,
            f"{updated} message(s) archived.",
            'success' if updated > 0 else 'warning'
        )
    mark_as_archived.short_description = "Archive selected messages"
