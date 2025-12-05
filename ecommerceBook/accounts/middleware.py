"""
Custom middleware for the accounts app.
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve


class PaymentRequiredMiddleware:
    """
    Middleware to block access to dashboards until role-specific payment is complete.
    Users must pay separately for buyer and seller dashboard access.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # URLs that don't require payment (accessible even with pending status)
        self.allowed_url_names = [
            'registration_payment',
            'role_upgrade_payment',  # New: for paying for additional role
            'payment_success',
            'payment_cancelled',
            'stripe_webhook',
            'logout',
            'user_logout',
            'login',
            'user_login',
            'register',
            'forgot_password',
            'verify_password',
            'confirm_password',
        ]

        # URL paths that don't require payment
        self.allowed_paths = [
            '/accounts/logout/',
            '/logout/',
            '/accounts/login/',
            '/login/',
            '/accounts/register/',
            '/register/',
            '/admin/',  # Allow admin access
            '/static/',
            '/media/',
        ]

        # Dashboard URLs that require role-specific payment
        self.buyer_dashboard_urls = ['buyer_dashboard', 'product_detail', 'cart', 'chatbot']
        self.seller_dashboard_urls = ['seller_dashboard', 'seller_product_detail', 'add_new_book',
                                       'add_new_course', 'add_new_webinar', 'add_new_service',
                                       'seller_messages']

    def __call__(self, request):
        # Skip middleware for unauthenticated users
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Skip for superusers
        if request.user.is_superuser:
            return self.get_response(request)

        # Check if URL is in allowed list
        current_url_name = resolve(request.path_info).url_name
        if current_url_name in self.allowed_url_names:
            return self.get_response(request)

        # Check if path starts with allowed paths
        if any(request.path.startswith(path) for path in self.allowed_paths):
            return self.get_response(request)

        # NEW: Check role-specific access for dashboards
        # If trying to access buyer dashboard without paying for buyer access
        if current_url_name in self.buyer_dashboard_urls:
            if not request.user.buyer_access_paid:
                messages.warning(
                    request,
                    'Please complete payment for Buyer access to use the buyer dashboard.'
                )
                return redirect('role_upgrade_payment', role='buyer')

        # If trying to access seller dashboard without paying for seller access
        if current_url_name in self.seller_dashboard_urls:
            if not request.user.seller_access_paid:
                messages.warning(
                    request,
                    'Please complete payment for Seller access to use the seller dashboard.'
                )
                return redirect('role_upgrade_payment', role='seller')

        # BACKWARD COMPATIBILITY: Check if user hasn't paid for ANY role yet
        if (
            not request.user.buyer_access_paid
            and not request.user.seller_access_paid
            and request.user.account_status == 'pending'
        ):
            messages.warning(
                request,
                'Please complete payment to activate your account and access the platform.'
            )
            return redirect('registration_payment')

        # Continue with request
        return self.get_response(request)
