from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from .forms import UserRegistrationForm, UserLoginForm, ForgotPasswordForm, VerifyTokenForm, ResetPasswordForm, BookForm, CourseForm, WebinarForm, ServiceForm
from .models import User, PasswordResetToken, Category, SiteSettings, Book, Course, Webinar, Service, Cart, CartItem, Order, OrderItem, ServiceChat, ServiceChatMessage, Notification
from .utils import send_verification_email
import logging
import json
import stripe
import os

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Initialize logger
logger = logging.getLogger(__name__)


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # Set account as pending payment
            user.account_status = 'pending'
            user.registration_paid = False
            user.save()

            messages.success(
                request,
                f'Account created successfully for {user.full_name}! Please complete payment to activate your account.'
            )

            # Auto-login the user after successful registration
            login(request, user)

            # Redirect to payment page
            return redirect('registration_payment')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserRegistrationForm()

    return render(request, 'src/Register.html', {'form': form})


def user_login(request):
    if request.user.is_authenticated:
        # Redirect authenticated users based on their user type
        if request.user.user_type == 'buyer':
            return redirect('buyer_dashboard')
        elif request.user.user_type == 'seller':
            return redirect('seller_dashboard')
        else:
            return redirect('home')
    
    if request.method == 'POST':
        form = UserLoginForm(request.POST, request=request)
        if form.is_valid():
            user = form.cleaned_data['user']
            remember_me = form.cleaned_data.get('remember_me', False)
            
            login(request, user)
            
            # Handle remember me functionality
            if not remember_me:
                request.session.set_expiry(0)  # Session expires when browser closes
            
            messages.success(request, f'Welcome back, {user.full_name}!')
            
            # Redirect based on user type
            if user.user_type == 'buyer':
                return redirect('buyer_dashboard')
            elif user.user_type == 'seller':
                return redirect('seller_dashboard')
            else:
                # For other user types, redirect to home
                next_url = request.GET.get('next', 'home')
                return redirect(next_url)
        else:
            messages.error(request, 'Invalid email or password.')
    else:
        form = UserLoginForm()
    
    return render(request, 'src/Login.html', {'form': form})


def user_logout(request):
    logout(request)
    return redirect('home')


def forgot_password(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.get(email=email)
            
            # Create password reset token
            reset_token = PasswordResetToken.create_token(user)
            
            # Send verification email
            email_sent = send_verification_email(email, reset_token.token)
            
            if email_sent:
                messages.success(
                    request, 
                    f'A verification code has been sent to {email}. Please check your email and enter the code on the next page.'
                )
                # Store email in session for next step
                request.session['reset_email'] = email
                return redirect('verify_password')
            else:
                messages.error(
                    request, 
                    'Failed to send verification email. Please try again or contact support.'
                )
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ForgotPasswordForm()
    
    return render(request, 'src/Forget_Password.html', {'form': form})


def verify_password(request):
    reset_email = request.session.get('reset_email')
    if not reset_email:
        messages.error(request, 'Please start the password reset process from the beginning.')
        return redirect('forgot_password')
    
    user = User.objects.get(email=reset_email)
    
    if request.method == 'POST':
        form = VerifyTokenForm(request.POST, user=user)
        if form.is_valid():
            token = form.cleaned_data['token']
            
            # Mark token as used
            reset_token = PasswordResetToken.objects.get(
                user=user, 
                token=token, 
                is_used=False
            )
            
            # Store token in session for final step
            request.session['reset_token'] = token
            
            return redirect('confirm_password')
        else:
            messages.error(request, 'Please enter a valid verification code.')
    else:
        form = VerifyTokenForm(user=user)
    
    return render(request, 'src/Verify_Password.html', {
        'form': form,
        'email': reset_email
    })


def confirm_password(request):
    reset_email = request.session.get('reset_email')
    reset_token = request.session.get('reset_token')
    
    if not reset_email or not reset_token:
        messages.error(request, 'Please start the password reset process from the beginning.')
        return redirect('forgot_password')
    
    user = User.objects.get(email=reset_email)
    
    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password2']
            
            # Update user password
            user.set_password(new_password)
            user.save()
            
            # Mark token as used
            PasswordResetToken.objects.filter(
                user=user,
                token=reset_token,
                is_used=False
            ).update(is_used=True)
            
            # Clear session data
            del request.session['reset_email']
            del request.session['reset_token']
            
            messages.success(request, 'Your password has been reset successfully! Please login with your new password.')
            return redirect('login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ResetPasswordForm()
    
    return render(request, 'src/Confirm_Password.html', {'form': form})


@login_required
def buyer_dashboard(request):
    """
    Buyer dashboard view - accessible to all logged-in users
    OPTIMIZED for fast performance (<5 seconds)
    """
    from django.db.models import Avg, Count, Q, Prefetch
    from .models import Rating, OrderItem
    from django.contrib.contenttypes.models import ContentType
    from django.core.cache import cache
    import threading

    # Get search query
    search_query = request.GET.get('search', '')

    # Get all services, books, courses, and webinars from all sellers with ratings pre-fetched
    all_services = Service.objects.filter(is_active=True).select_related('category', 'seller')
    all_books = Book.objects.filter(is_active=True).select_related('category', 'seller')
    all_courses = Course.objects.filter(is_active=True).select_related('category', 'seller')
    all_webinars = Webinar.objects.filter(is_active=True).select_related('category', 'seller')

    # Apply search filter if search query exists (title only)
    if search_query:
        all_services = all_services.filter(title__icontains=search_query)
        all_books = all_books.filter(title__icontains=search_query)
        all_courses = all_courses.filter(title__icontains=search_query)
        all_webinars = all_webinars.filter(title__icontains=search_query)

        # Track search query asynchronously to avoid blocking
        results_count = all_services.count() + all_books.count() + all_courses.count() + all_webinars.count()

        def async_track_search():
            from .recommendation_engine import track_search_query
            track_search_query(request.user, search_query, results_count)

        # Run in background thread
        thread = threading.Thread(target=async_track_search)
        thread.daemon = True
        thread.start()

    # Get cached recommendations or calculate if not cached
    cache_key = f'user_recommendations_{request.user.id}'
    recommendations = cache.get(cache_key)

    if recommendations is None:
        from .recommendation_engine import get_personalized_recommendations
        recommendations = get_personalized_recommendations(request.user, limit=50)
        # Cache for 5 minutes
        cache.set(cache_key, recommendations, 300)

    # Create a dict of recommended product IDs with their rank
    recommended_ids = {}
    for idx, rec in enumerate(recommendations):
        key = f"{rec['type']}_{rec['id']}"
        recommended_ids[key] = idx  # Lower index = higher priority

    # Sort products: recommended first, then by creation date
    def sort_by_recommendation(product, product_type):
        key = f"{product_type}_{product.id}"
        if key in recommended_ids:
            return (0, recommended_ids[key])  # Recommended products first
        else:
            return (1, -product.created_at.timestamp())  # Then by newest

    all_services_list = list(all_services)
    all_books_list = list(all_books)
    all_courses_list = list(all_courses)
    all_webinars_list = list(all_webinars)

    all_services_list.sort(key=lambda x: sort_by_recommendation(x, 'service'))
    all_books_list.sort(key=lambda x: sort_by_recommendation(x, 'book'))
    all_courses_list.sort(key=lambda x: sort_by_recommendation(x, 'course'))
    all_webinars_list.sort(key=lambda x: sort_by_recommendation(x, 'webinar'))

    # OPTIMIZED: Get all ratings in just 4 queries instead of N queries
    service_content_type = ContentType.objects.get_for_model(Service)
    book_content_type = ContentType.objects.get_for_model(Book)
    course_content_type = ContentType.objects.get_for_model(Course)
    webinar_content_type = ContentType.objects.get_for_model(Webinar)

    # Get all service ratings in one query
    service_ratings_dict = {}
    if all_services_list:
        service_ids = [service.id for service in all_services_list]
        service_ratings = Rating.objects.filter(
            order_item__content_type=service_content_type,
            order_item__object_id__in=service_ids
        ).values('order_item__object_id').annotate(
            avg_rating=Avg('rating'),
            total_ratings=Count('id')
        )
        service_ratings_dict = {r['order_item__object_id']: r for r in service_ratings}

    # Get all book ratings in one query
    book_ratings_dict = {}
    if all_books_list:
        book_ids = [book.id for book in all_books_list]
        book_ratings = Rating.objects.filter(
            order_item__content_type=book_content_type,
            order_item__object_id__in=book_ids
        ).values('order_item__object_id').annotate(
            avg_rating=Avg('rating'),
            total_ratings=Count('id')
        )
        book_ratings_dict = {r['order_item__object_id']: r for r in book_ratings}

    # Get all course ratings in one query
    course_ratings_dict = {}
    if all_courses_list:
        course_ids = [course.id for course in all_courses_list]
        course_ratings = Rating.objects.filter(
            order_item__content_type=course_content_type,
            order_item__object_id__in=course_ids
        ).values('order_item__object_id').annotate(
            avg_rating=Avg('rating'),
            total_ratings=Count('id')
        )
        course_ratings_dict = {r['order_item__object_id']: r for r in course_ratings}

    # Get all webinar ratings in one query
    webinar_ratings_dict = {}
    if all_webinars_list:
        webinar_ids = [webinar.id for webinar in all_webinars_list]
        webinar_ratings = Rating.objects.filter(
            order_item__content_type=webinar_content_type,
            order_item__object_id__in=webinar_ids
        ).values('order_item__object_id').annotate(
            avg_rating=Avg('rating'),
            total_ratings=Count('id')
        )
        webinar_ratings_dict = {r['order_item__object_id']: r for r in webinar_ratings}

    # Assign ratings to products
    for service in all_services_list:
        rating_data = service_ratings_dict.get(service.id, {})
        service.avg_rating = round(rating_data.get('avg_rating', 0), 1) if rating_data.get('avg_rating') else 0
        service.total_ratings = rating_data.get('total_ratings', 0)

    for book in all_books_list:
        rating_data = book_ratings_dict.get(book.id, {})
        book.avg_rating = round(rating_data.get('avg_rating', 0), 1) if rating_data.get('avg_rating') else 0
        book.total_ratings = rating_data.get('total_ratings', 0)

    for course in all_courses_list:
        rating_data = course_ratings_dict.get(course.id, {})
        course.avg_rating = round(rating_data.get('avg_rating', 0), 1) if rating_data.get('avg_rating') else 0
        course.total_ratings = rating_data.get('total_ratings', 0)

    for webinar in all_webinars_list:
        rating_data = webinar_ratings_dict.get(webinar.id, {})
        webinar.avg_rating = round(rating_data.get('avg_rating', 0), 1) if rating_data.get('avg_rating') else 0
        webinar.total_ratings = rating_data.get('total_ratings', 0)

    # Get all categories from database
    categories = Category.objects.all().order_by('name')

    # Get cart count for the user (both buyers and sellers can have carts)
    cart_count = 0
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_count = cart.get_total_items()

    # Get purchased service IDs for this buyer
    purchased_service_ids = []
    if request.user.is_authenticated:
        purchased_service_ids = OrderItem.objects.filter(
            order__user=request.user,
            content_type=service_content_type
        ).values_list('object_id', flat=True).distinct()

    # Get total counts for dashboard
    services_count = len(all_services_list)
    books_count = len(all_books_list)
    courses_count = len(all_courses_list)
    webinars_count = len(all_webinars_list)

    # Limit to 8 products per section for dashboard display (rest available in "View All")
    all_services_list = all_services_list[:8]
    all_books_list = all_books_list[:8]
    all_courses_list = all_courses_list[:8]
    all_webinars_list = all_webinars_list[:8]

    # Get user data for the template
    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'can_switch_to_seller': True,  # Allow switching to seller dashboard
        'current_dashboard': 'buyer',
        'services': all_services_list,  # Services appear first (limited to 8)
        'books': all_books_list,  # Limited to 8
        'courses': all_courses_list,  # Limited to 8
        'webinars': all_webinars_list,  # Limited to 8
        'categories': categories,
        'cart_count': cart_count,
        'search_query': search_query,
        'purchased_service_ids': list(purchased_service_ids),  # For chat button
        'books_count': books_count,  # Total count (not limited)
        'courses_count': courses_count,  # Total count (not limited)
        'webinars_count': webinars_count,  # Total count (not limited)
        'services_count': services_count,  # Total count (not limited)
    }

    return render(request, 'src/Buyers_dashboard.html', context)


@login_required
def seller_dashboard(request):
    """
    Seller dashboard view - accessible to logged-in sellers
    Sellers have dual access: can sell AND buy
    OPTIMIZED for fast performance
    """
    from django.db.models import Q

    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('buyer_dashboard')

    # Get search query
    search_query = request.GET.get('search', '')

    # OPTIMIZATION: select_related() to prefetch related objects
    # Get seller's own books, courses, webinars, and services
    seller_books = Book.objects.filter(seller=request.user, is_active=True).select_related('category', 'seller')
    seller_courses = Course.objects.filter(seller=request.user, is_active=True).select_related('category', 'seller')
    seller_webinars = Webinar.objects.filter(seller=request.user, is_active=True).select_related('category', 'seller')
    seller_services = Service.objects.filter(seller=request.user, is_active=True).select_related('category', 'seller')

    # Apply search filter if search query exists (title only)
    if search_query:
        seller_books = seller_books.filter(title__icontains=search_query)
        seller_courses = seller_courses.filter(title__icontains=search_query)
        seller_webinars = seller_webinars.filter(title__icontains=search_query)
        seller_services = seller_services.filter(title__icontains=search_query)

    # Order by creation date
    seller_books = seller_books.order_by('-created_at')
    seller_courses = seller_courses.order_by('-created_at')
    seller_webinars = seller_webinars.order_by('-created_at')
    seller_services = seller_services.order_by('-created_at')

    # Get all categories from database
    categories = Category.objects.all().order_by('name')

    # Get cart count for the seller (sellers can also shop)
    cart_count = 0
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_count = cart.get_total_items()

    # Get service buyers (for chat functionality)
    # Attach buyers list directly to each service object
    seller_services_list = list(seller_services)
    if seller_services_list:
        service_content_type = ContentType.objects.get_for_model(Service)
        sold_services = OrderItem.objects.filter(
            content_type=service_content_type,
            object_id__in=[s.id for s in seller_services_list]
        ).select_related('order__user').values('object_id', 'order__user__id', 'order__user__full_name').distinct()

        # Create a dict mapping service_id to buyers
        service_buyers_dict = {}
        for item in sold_services:
            service_id = item['object_id']
            if service_id not in service_buyers_dict:
                service_buyers_dict[service_id] = []
            service_buyers_dict[service_id].append({
                'id': item['order__user__id'],
                'name': item['order__user__full_name']
            })

        # Attach buyers to each service object
        for service in seller_services_list:
            service.buyers = service_buyers_dict.get(service.id, [])

    # Get counts for dashboard
    books_count = seller_books.count()
    courses_count = seller_courses.count()
    webinars_count = seller_webinars.count()
    services_count = len(seller_services_list) if seller_services_list else seller_services.count()

    # Get user data for the template
    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'services': seller_services_list if seller_services_list else seller_services,
        'books': seller_books,
        'courses': seller_courses,
        'webinars': seller_webinars,
        'categories': categories,
        'cart_count': cart_count,
        'search_query': search_query,
        'books_count': books_count,
        'courses_count': courses_count,
        'webinars_count': webinars_count,
        'services_count': services_count,
    }

    return render(request, 'src/seller_dashboard.html', context)


@login_required
def add_new_book(request):
    """
    Add new book page - only accessible to logged-in sellers
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('home')

    # Check if seller has Stripe Account ID
    if not request.user.can_add_products():
        messages.warning(
            request,
            'Please add your Stripe Account ID in Settings before adding products. '
            'This is required to receive payments from buyers.'
        )
        return redirect('settings')

    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)
            book.seller = request.user
            book.save()

            # Index the new book in Pinecone
            from .chatbot_helper import index_single_product
            try:
                index_single_product(book, 'book')
            except Exception as e:
                print(f"Error indexing book: {e}")

            # Create notification for seller
            from .models import Notification
            from django.urls import reverse
            Notification.objects.create(
                user=request.user,
                notification_type='general',
                title='Product Added!',
                message=f'Your book "{book.title}" has been added successfully.',
                link=reverse('seller_dashboard')
            )

            messages.success(request, f'Book "{book.title}" has been added successfully!')
            return redirect('seller_dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BookForm()

    # Get all categories for the dropdown
    categories = Category.objects.all().order_by('name')

    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'form': form,
        'categories': categories,
    }
    return render(request, 'src/Add_new_book.html', context)


@login_required
def add_new_course(request):
    """
    Add new course page - only accessible to logged-in sellers
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('home')

    # Check if seller has Stripe Account ID
    if not request.user.can_add_products():
        messages.warning(
            request,
            'Please add your Stripe Account ID in Settings before adding products. '
            'This is required to receive payments from buyers.'
        )
        return redirect('settings')

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            course.seller = request.user
            course.save()

            # Index the new course in Pinecone
            from .chatbot_helper import index_single_product
            try:
                index_single_product(course, 'course')
            except Exception as e:
                print(f"Error indexing course: {e}")

            # Create notification for seller
            from .models import Notification
            from django.urls import reverse
            Notification.objects.create(
                user=request.user,
                notification_type='general',
                title='Course Added!',
                message=f'Your course "{course.title}" has been added successfully.',
                link=reverse('seller_dashboard')
            )

            messages.success(request, f'Course "{course.title}" has been added successfully!')
            return redirect('seller_dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CourseForm()

    # Get all categories for the dropdown
    categories = Category.objects.all().order_by('name')

    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'form': form,
        'categories': categories,
    }
    return render(request, 'src/Add_new_course.html', context)


@login_required
def add_new_webinar(request):
    """
    Add new webinar page - only accessible to logged-in sellers
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('home')

    # Check if seller has Stripe Account ID
    if not request.user.can_add_products():
        messages.warning(
            request,
            'Please add your Stripe Account ID in Settings before adding products. '
            'This is required to receive payments from buyers.'
        )
        return redirect('settings')

    if request.method == 'POST':
        form = WebinarForm(request.POST, request.FILES)
        if form.is_valid():
            webinar = form.save(commit=False)
            webinar.seller = request.user
            webinar.save()

            # Index the new webinar in Pinecone
            from .chatbot_helper import index_single_product
            try:
                index_single_product(webinar, 'webinar')
            except Exception as e:
                print(f"Error indexing webinar: {e}")

            # Create notification for seller
            from .models import Notification
            from django.urls import reverse
            Notification.objects.create(
                user=request.user,
                notification_type='general',
                title='Webinar Added!',
                message=f'Your webinar "{webinar.title}" has been added successfully.',
                link=reverse('seller_dashboard')
            )

            messages.success(request, f'Webinar "{webinar.title}" has been added successfully!')
            return redirect('seller_dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = WebinarForm()

    # Get all categories for the dropdown
    categories = Category.objects.all().order_by('name')

    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'form': form,
        'categories': categories,
    }
    return render(request, 'src/Add_new_webinar.html', context)


@login_required
def add_new_service(request):
    """
    Add new service page - only accessible to logged-in sellers
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('home')

    # Check if seller has Stripe Account ID
    if not request.user.can_add_products():
        messages.warning(
            request,
            'Please add your Stripe Account ID in Settings before adding products. '
            'This is required to receive payments from buyers.'
        )
        return redirect('settings')

    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            service = form.save(commit=False)
            service.seller = request.user
            service.save()

            # Index the new service in Pinecone
            from .chatbot_helper import index_single_product
            try:
                index_single_product(service, 'service')
            except Exception as e:
                print(f"Error indexing service: {e}")

            # Create notification for seller
            from .models import Notification
            from django.urls import reverse
            Notification.objects.create(
                user=request.user,
                notification_type='general',
                title='Service Added!',
                message=f'Your service "{service.title}" has been added successfully.',
                link=reverse('seller_dashboard')
            )

            messages.success(request, f'Service "{service.title}" has been added successfully!')
            return redirect('seller_dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ServiceForm()

    # Get all categories for the dropdown
    categories = Category.objects.all().order_by('name')

    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'form': form,
        'categories': categories,
    }
    return render(request, 'src/Add_new_service.html', context)


@login_required
def settings(request):
    """
    Settings page view - only accessible to logged-in users
    """
    if request.method == 'POST':
        # Handle settings update
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        profile_image = request.FILES.get('profile_image')

        # Update basic information
        if full_name:
            request.user.full_name = full_name
        if email and email != request.user.email:
            # Check if email already exists
            if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                # Email already exists - silently ignore or redirect
                return redirect('settings')
            request.user.email = email

        # Handle Stripe Account ID for sellers
        stripe_account_id = request.POST.get('stripe_account_id', '').strip()
        if stripe_account_id:
            if stripe_account_id.startswith('acct_'):
                request.user.stripe_account_id = stripe_account_id
                messages.success(request, 'Stripe Account ID updated successfully!')
            else:
                messages.error(request, 'Invalid Stripe Account ID format. It should start with "acct_"')

        if profile_image:
            request.user.profile_image = profile_image

        # Handle password change
        if current_password and new_password and confirm_password:
            if not request.user.check_password(current_password):
                # Wrong password - silently ignore
                return redirect('settings')
            if new_password != confirm_password:
                # Passwords don't match - silently ignore
                return redirect('settings')
            if len(new_password) < 8:
                # Password too short - silently ignore
                return redirect('settings')

            request.user.set_password(new_password)

        # Save user changes
        request.user.save()

        # No messages or notifications for settings updates
        # Settings changes are immediate and visible on the page

        return redirect('settings')

    # GET request - display settings page
    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'email': request.user.email,
        'user_type': request.user.get_user_type_display(),
        'stripe_account_id': request.user.stripe_account_id or '',
        'is_seller': request.user.user_type == 'seller' or request.user.seller_access_paid,
        'needs_stripe_account': request.user.needs_stripe_account_setup(),
    }

    return render(request, 'src/setting.html', context)


@login_required
def product_detail(request, product_type, product_id):
    """
    Product detail view - shows detailed information about a specific product
    OPTIMIZED for fast performance
    """
    from django.core.cache import cache
    import threading

    try:
        # OPTIMIZATION: select_related() to prefetch related objects
        if product_type == 'book':
            product = Book.objects.select_related('category', 'seller').get(id=product_id, is_active=True)
        elif product_type == 'course':
            product = Course.objects.select_related('category', 'seller').get(id=product_id, is_active=True)
        elif product_type == 'webinar':
            product = Webinar.objects.select_related('category', 'seller').get(id=product_id, is_active=True)
        elif product_type == 'service':
            product = Service.objects.select_related('category', 'seller').get(id=product_id, is_active=True)
        else:
            messages.error(request, 'Invalid product type.')
            return redirect('buyer_dashboard')
    except (Book.DoesNotExist, Course.DoesNotExist, Webinar.DoesNotExist, Service.DoesNotExist):
        messages.error(request, 'Product not found.')
        return redirect('buyer_dashboard')

    # OPTIMIZATION 1: Track product view asynchronously (non-blocking)
    from .recommendation_engine import track_product_view, get_similar_products
    def async_track_view():
        track_product_view(request.user, product, product_type)
    thread = threading.Thread(target=async_track_view)
    thread.daemon = True
    thread.start()

    # OPTIMIZATION 2: Cache similar products for 10 minutes
    cache_key = f'similar_products_{product_type}_{product_id}'
    similar_products = cache.get(cache_key)
    if similar_products is None:
        similar_products = get_similar_products(product, product_type, limit=4)
        cache.set(cache_key, similar_products, 600)  # 10 min cache

    # Get recently viewed products for this user
    recently_viewed = []
    if request.user.is_authenticated:
        from .models import UserBrowsingHistory
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Max

        # Get the 4 most recently viewed products (excluding current product)
        recent_views = UserBrowsingHistory.objects.filter(
            user=request.user
        ).exclude(
            content_type=ContentType.objects.get_for_model(product.__class__),
            object_id=product.id
        ).values('content_type', 'object_id').annotate(
            last_viewed=Max('viewed_at')
        ).order_by('-last_viewed')[:4]

        # Get the actual product objects
        for view in recent_views:
            content_type = ContentType.objects.get(id=view['content_type'])
            try:
                product_obj = content_type.get_object_for_this_type(id=view['object_id'], is_active=True)
                # Determine product type
                if content_type.model == 'book':
                    product_obj.type = 'book'
                elif content_type.model == 'course':
                    product_obj.type = 'course'
                elif content_type.model == 'webinar':
                    product_obj.type = 'webinar'
                elif content_type.model == 'service':
                    product_obj.type = 'service'
                recently_viewed.append(product_obj)
            except:
                continue

    context = {
        'product': product,
        'product_type': product_type,
        'user': request.user,
        'similar_products': similar_products,
        'recently_viewed': recently_viewed,
    }

    return render(request, 'src/Buyers_dashboard_product.html', context)


@login_required
def seller_product_detail(request, product_type, product_id):
    """
    Seller product detail view - shows detailed information about seller's own product
    OPTIMIZED for fast performance
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('buyer_dashboard')

    try:
        # OPTIMIZATION: select_related() to prefetch related objects
        if product_type == 'book':
            product = Book.objects.select_related('category', 'seller').get(id=product_id, seller=request.user, is_active=True)
        elif product_type == 'course':
            product = Course.objects.select_related('category', 'seller').get(id=product_id, seller=request.user, is_active=True)
        elif product_type == 'webinar':
            product = Webinar.objects.select_related('category', 'seller').get(id=product_id, seller=request.user, is_active=True)
        elif product_type == 'service':
            product = Service.objects.select_related('category', 'seller').get(id=product_id, seller=request.user, is_active=True)
        else:
            messages.error(request, 'Invalid product type.')
            return redirect('seller_dashboard')
    except (Book.DoesNotExist, Course.DoesNotExist, Webinar.DoesNotExist, Service.DoesNotExist):
        messages.error(request, 'Product not found or you do not have permission to view this product.')
        return redirect('seller_dashboard')

    # Calculate product performance metrics
    from django.contrib.contenttypes.models import ContentType
    from .models import OrderItem, UserBrowsingHistory

    # Get content type for the product
    content_type = ContentType.objects.get_for_model(product.__class__)

    # Get sales count (number of times this product was purchased)
    sales_count = OrderItem.objects.filter(
        content_type=content_type,
        object_id=product.id,
        order__status='completed'
    ).count()

    # Get views count (number of times this product was viewed)
    views_count = UserBrowsingHistory.objects.filter(
        content_type=content_type,
        object_id=product.id
    ).count()

    context = {
        'product': product,
        'product_type': product_type,
        'user': request.user,
        'sales_count': sales_count,
        'views_count': views_count,
    }

    return render(request, 'src/seller_dashboard_product.html', context)


@login_required
def edit_book(request, book_id):
    """
    Edit book page - only accessible to logged-in sellers who own the book
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('home')

    try:
        book = Book.objects.get(id=book_id, seller=request.user)
    except Book.DoesNotExist:
        messages.error(request, 'Book not found or you do not have permission to edit this book.')
        return redirect('seller_dashboard')

    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            book = form.save(commit=False)
            book.seller = request.user
            book.save()

            # Update the book in Pinecone index
            from .chatbot_helper import index_single_product
            try:
                index_single_product(book, 'book')
            except Exception as e:
                print(f"Error updating book in index: {e}")

            # Create notification for seller
            from .models import Notification
            from django.urls import reverse
            Notification.objects.create(
                user=request.user,
                notification_type='general',
                title='Book Updated!',
                message=f'Your book "{book.title}" has been updated successfully.',
                link=reverse('seller_product_detail', args=['book', book.id])
            )

            messages.success(request, f'Book "{book.title}" has been updated successfully!')
            return redirect('seller_product_detail', 'book', book.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BookForm(instance=book)

    # Get all categories for the dropdown
    categories = Category.objects.all().order_by('name')

    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'form': form,
        'categories': categories,
        'book': book,
        'is_edit': True,
    }
    return render(request, 'src/Add_new_book.html', context)


@login_required
def edit_course(request, course_id):
    """
    Edit course page - only accessible to logged-in sellers who own the course
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('home')

    try:
        course = Course.objects.get(id=course_id, seller=request.user)
    except Course.DoesNotExist:
        messages.error(request, 'Course not found or you do not have permission to edit this course.')
        return redirect('seller_dashboard')

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            course = form.save(commit=False)
            course.seller = request.user
            course.save()

            # Update the course in Pinecone index
            from .chatbot_helper import index_single_product
            try:
                index_single_product(course, 'course')
            except Exception as e:
                print(f"Error updating course in index: {e}")

            # Create notification for seller
            from .models import Notification
            from django.urls import reverse
            Notification.objects.create(
                user=request.user,
                notification_type='general',
                title='Course Updated!',
                message=f'Your course "{course.title}" has been updated successfully.',
                link=reverse('seller_product_detail', args=['course', course.id])
            )

            messages.success(request, f'Course "{course.title}" has been updated successfully!')
            return redirect('seller_product_detail', 'course', course.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CourseForm(instance=course)

    # Get all categories for the dropdown
    categories = Category.objects.all().order_by('name')

    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'form': form,
        'categories': categories,
        'course': course,
        'is_edit': True,
    }
    return render(request, 'src/Add_new_course.html', context)


@login_required
def edit_webinar(request, webinar_id):
    """
    Edit webinar page - only accessible to logged-in sellers who own the webinar
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('home')

    try:
        webinar = Webinar.objects.get(id=webinar_id, seller=request.user)
    except Webinar.DoesNotExist:
        messages.error(request, 'Webinar not found or you do not have permission to edit this webinar.')
        return redirect('seller_dashboard')

    if request.method == 'POST':
        form = WebinarForm(request.POST, request.FILES, instance=webinar)
        if form.is_valid():
            webinar = form.save(commit=False)
            webinar.seller = request.user
            webinar.save()

            # Update the webinar in Pinecone index
            from .chatbot_helper import index_single_product
            try:
                index_single_product(webinar, 'webinar')
            except Exception as e:
                print(f"Error updating webinar in index: {e}")

            # Create notification for seller
            from .models import Notification
            from django.urls import reverse
            Notification.objects.create(
                user=request.user,
                notification_type='general',
                title='Webinar Updated!',
                message=f'Your webinar "{webinar.title}" has been updated successfully.',
                link=reverse('seller_product_detail', args=['webinar', webinar.id])
            )

            messages.success(request, f'Webinar "{webinar.title}" has been updated successfully!')
            return redirect('seller_product_detail', 'webinar', webinar.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = WebinarForm(instance=webinar)

    # Get all categories for the dropdown
    categories = Category.objects.all().order_by('name')

    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'form': form,
        'categories': categories,
        'webinar': webinar,
        'is_edit': True,
    }
    return render(request, 'src/Add_new_webinar.html', context)


@login_required
def delete_book(request, book_id):
    """
    Delete book - only accessible to logged-in sellers who own the book
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('home')

    try:
        book = Book.objects.get(id=book_id, seller=request.user)
    except Book.DoesNotExist:
        messages.error(request, 'Book not found or you do not have permission to delete this book.')
        return redirect('seller_dashboard')

    if request.method == 'POST':
        book_title = book.title
        book_id = book.id
        book.delete()

        # Delete the book from Pinecone index
        from .chatbot_helper import delete_product_from_index
        try:
            delete_product_from_index(book_id, 'book')
        except Exception as e:
            print(f"Error deleting book from index: {e}")

        # Create notification for seller
        from .models import Notification
        from django.urls import reverse
        Notification.objects.create(
            user=request.user,
            notification_type='general',
            title='Book Deleted!',
            message=f'Your book "{book_title}" has been deleted successfully.',
            link=reverse('seller_dashboard')
        )

        messages.success(request, f'Book "{book_title}" has been deleted successfully!')
        return redirect('seller_dashboard')

    # If not POST, redirect back to product detail
    return redirect('seller_product_detail', 'book', book_id)


@login_required
def delete_course(request, course_id):
    """
    Delete course - only accessible to logged-in sellers who own the course
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('home')

    try:
        course = Course.objects.get(id=course_id, seller=request.user)
    except Course.DoesNotExist:
        messages.error(request, 'Course not found or you do not have permission to delete this course.')
        return redirect('seller_dashboard')

    if request.method == 'POST':
        course_title = course.title
        course_id = course.id
        course.delete()

        # Delete the course from Pinecone index
        from .chatbot_helper import delete_product_from_index
        try:
            delete_product_from_index(course_id, 'course')
        except Exception as e:
            print(f"Error deleting course from index: {e}")

        # Create notification for seller
        from .models import Notification
        from django.urls import reverse
        Notification.objects.create(
            user=request.user,
            notification_type='general',
            title='Course Deleted!',
            message=f'Your course "{course_title}" has been deleted successfully.',
            link=reverse('seller_dashboard')
        )

        messages.success(request, f'Course "{course_title}" has been deleted successfully!')
        return redirect('seller_dashboard')

    # If not POST, redirect back to product detail
    return redirect('seller_product_detail', 'course', course_id)


@login_required
def delete_webinar(request, webinar_id):
    """
    Delete webinar - only accessible to logged-in sellers who own the webinar
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('home')

    try:
        webinar = Webinar.objects.get(id=webinar_id, seller=request.user)
    except Webinar.DoesNotExist:
        messages.error(request, 'Webinar not found or you do not have permission to delete this webinar.')
        return redirect('seller_dashboard')

    if request.method == 'POST':
        webinar_title = webinar.title
        webinar_id = webinar.id
        webinar.delete()

        # Delete the webinar from Pinecone index
        from .chatbot_helper import delete_product_from_index
        try:
            delete_product_from_index(webinar_id, 'webinar')
        except Exception as e:
            print(f"Error deleting webinar from index: {e}")

        # Create notification for seller
        from .models import Notification
        from django.urls import reverse
        Notification.objects.create(
            user=request.user,
            notification_type='general',
            title='Webinar Deleted!',
            message=f'Your webinar "{webinar_title}" has been deleted successfully.',
            link=reverse('seller_dashboard')
        )

        messages.success(request, f'Webinar "{webinar_title}" has been deleted successfully!')
        return redirect('seller_dashboard')

    # If not POST, redirect back to product detail
    return redirect('seller_product_detail', 'webinar', webinar_id)


@login_required
def edit_service(request, service_id):
    """
    Edit service page - only accessible to logged-in sellers who own the service
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('home')

    try:
        service = Service.objects.get(id=service_id, seller=request.user)
    except Service.DoesNotExist:
        messages.error(request, 'Service not found or you do not have permission to edit this service.')
        return redirect('seller_dashboard')

    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            service = form.save(commit=False)
            service.seller = request.user
            service.save()

            # Update the service in Pinecone index
            from .chatbot_helper import index_single_product
            try:
                index_single_product(service, 'service')
            except Exception as e:
                print(f"Error updating service in index: {e}")

            # Create notification for seller
            from .models import Notification
            from django.urls import reverse
            Notification.objects.create(
                user=request.user,
                notification_type='general',
                title='Service Updated!',
                message=f'Your service "{service.title}" has been updated successfully.',
                link=reverse('seller_product_detail', args=['service', service.id])
            )

            messages.success(request, f'Service "{service.title}" has been updated successfully!')
            return redirect('seller_product_detail', 'service', service.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ServiceForm(instance=service)

    # Get all categories for the dropdown
    categories = Category.objects.all().order_by('name')

    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'form': form,
        'categories': categories,
        'service': service,
        'is_edit': True,
    }
    return render(request, 'src/Add_new_service.html', context)


@login_required
def delete_service(request, service_id):
    """
    Delete service - only accessible to logged-in sellers who own the service
    """
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. This page is only available for sellers.')
        return redirect('home')

    try:
        service = Service.objects.get(id=service_id, seller=request.user)
    except Service.DoesNotExist:
        messages.error(request, 'Service not found or you do not have permission to delete this service.')
        return redirect('seller_dashboard')

    if request.method == 'POST':
        service_title = service.title
        service_id = service.id
        service.delete()

        # Delete the service from Pinecone index
        from .chatbot_helper import delete_product_from_index
        try:
            delete_product_from_index(service_id, 'service')
        except Exception as e:
            print(f"Error deleting service from index: {e}")

        # Create notification for seller
        from .models import Notification
        from django.urls import reverse
        Notification.objects.create(
            user=request.user,
            notification_type='general',
            title='Service Deleted!',
            message=f'Your service "{service_title}" has been deleted successfully.',
            link=reverse('seller_dashboard')
        )

        messages.success(request, f'Service "{service_title}" has been deleted successfully!')
        return redirect('seller_dashboard')

    # If not POST, redirect back to product detail
    return redirect('seller_product_detail', 'service', service_id)


@login_required
def cart(request):
    """
    Cart page view - shows user's cart items
    """
    # Get or create cart for the user
    cart, created = Cart.objects.get_or_create(user=request.user)

    # Get all cart items
    cart_items = cart.items.all()

    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'cart': cart,
        'cart_items': cart_items,
        'total_items': cart.get_total_items(),
        'total_price': cart.get_total_price(),
    }

    return render(request, 'src/cart.html', context)


@login_required
def add_to_cart(request, product_type, product_id):
    """
    Add product to cart - AJAX endpoint
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})

    # Both buyers and sellers can add items to cart (sellers can also shop)
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'You must be logged in to add items to cart'})

    try:
        # Get the product based on type
        if product_type == 'book':
            product = get_object_or_404(Book, id=product_id, is_active=True)
            content_type = ContentType.objects.get_for_model(Book)
        elif product_type == 'course':
            product = get_object_or_404(Course, id=product_id, is_active=True)
            content_type = ContentType.objects.get_for_model(Course)
        elif product_type == 'webinar':
            product = get_object_or_404(Webinar, id=product_id, is_active=True)
            content_type = ContentType.objects.get_for_model(Webinar)
        elif product_type == 'service':
            product = get_object_or_404(Service, id=product_id, is_active=True)
            content_type = ContentType.objects.get_for_model(Service)
        else:
            return JsonResponse({'success': False, 'message': 'Invalid product type'})

        # Prevent sellers from adding their own products to cart
        if hasattr(product, 'seller') and product.seller == request.user:
            return JsonResponse({'success': False, 'message': 'You cannot add your own products to cart'})

        # Get or create cart for the user
        cart, created = Cart.objects.get_or_create(user=request.user)

        # Check if item already exists in cart
        cart_item, item_created = CartItem.objects.get_or_create(
            cart=cart,
            content_type=content_type,
            object_id=product_id,
            defaults={'quantity': 1}
        )

        if not item_created:
            # Item already exists, increase quantity
            cart_item.quantity += 1
            cart_item.save()
            message = f'{product.title} quantity updated in cart'
        else:
            message = f'{product.title} added to cart'

        return JsonResponse({
            'success': True,
            'message': message,
            'cart_count': cart.get_total_items(),
            'cart_total': float(cart.get_total_price())
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': 'Failed to add item to cart'})


@login_required
def remove_from_cart(request, item_id):
    """
    Remove item from cart - AJAX endpoint
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})

    # Both buyers and sellers can remove items from cart (sellers can also shop)
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'You must be logged in to remove items from cart'})

    try:
        # Get the cart item
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        product_title = cart_item.content_object.title
        cart_item.delete()

        # Get updated cart totals
        cart = Cart.objects.get(user=request.user)

        return JsonResponse({
            'success': True,
            'message': f'{product_title} removed from cart',
            'cart_count': cart.get_total_items(),
            'cart_total': float(cart.get_total_price())
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': 'Failed to remove item from cart'})


@login_required
def clear_cart(request):
    """
    Clear all items from cart - AJAX endpoint
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})

    # Both buyers and sellers can clear their cart
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'You must be logged in to clear cart'})

    try:
        # Get the user's cart
        cart = Cart.objects.get(user=request.user)

        # Count items before deletion
        item_count = cart.get_total_items()

        # Delete all cart items
        CartItem.objects.filter(cart=cart).delete()

        return JsonResponse({
            'success': True,
            'message': f'Cart cleared! {item_count} item(s) removed',
            'cart_count': 0,
            'cart_total': 0.0
        })

    except Cart.DoesNotExist:
        return JsonResponse({'success': True, 'message': 'Cart is already empty'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'Failed to clear cart'})


@login_required
def orders(request):
    """
    Orders page view - shows user's order history (buyer) or sales (seller)
    Based on the user's current user_type in the database
    """
    # Get current mode from user's actual user_type
    current_mode = request.user.user_type

    if current_mode == 'seller':
        # Seller viewing their sales
        # Get all orders that contain items sold by this seller
        from django.db.models import Q

        # Get all order items where the product belongs to this seller
        seller_order_items = OrderItem.objects.filter(
            Q(content_type__model='book', object_id__in=Book.objects.filter(seller=request.user).values_list('id', flat=True)) |
            Q(content_type__model='course', object_id__in=Course.objects.filter(seller=request.user).values_list('id', flat=True)) |
            Q(content_type__model='webinar', object_id__in=Webinar.objects.filter(seller=request.user).values_list('id', flat=True)) |
            Q(content_type__model='service', object_id__in=Service.objects.filter(seller=request.user).values_list('id', flat=True))
        ).select_related('order', 'content_type').prefetch_related('order__user')

        # Group by orders
        order_ids = seller_order_items.values_list('order_id', flat=True).distinct()
        orders = Order.objects.filter(id__in=order_ids).prefetch_related('items__content_object')

    else:
        # Buyer viewing their purchases
        orders = Order.objects.filter(user=request.user).prefetch_related('items__content_object', 'items__rating')

    # Add rating information to order items for buyers
    from .models import Rating
    if current_mode == 'buyer':
        for order in orders:
            for item in order.items.all():
                try:
                    item.user_rating = Rating.objects.get(user=request.user, order_item=item)
                except Rating.DoesNotExist:
                    item.user_rating = None

    context = {
        'user': request.user,
        'full_name': request.user.full_name,
        'orders': orders,
        'current_mode': current_mode,
        'can_switch_mode': True,  # All users can switch modes
    }

    return render(request, 'src/order.html', context)


@login_required
def purchase_product(request, product_type, product_id):
    """
    Purchase a single product directly through Stripe
    Creates Stripe Checkout Session and redirects to payment
    """
    try:
        # Get the product
        if product_type == 'book':
            product = Book.objects.get(id=product_id, is_active=True)
        elif product_type == 'course':
            product = Course.objects.get(id=product_id, is_active=True)
        elif product_type == 'webinar':
            product = Webinar.objects.get(id=product_id, is_active=True)
        elif product_type == 'service':
            product = Service.objects.get(id=product_id, is_active=True)
        else:
            messages.error(request, 'Invalid product type')
            return redirect('buyer_dashboard')

        # Prevent sellers from purchasing their own products
        if hasattr(product, 'seller') and product.seller == request.user:
            messages.error(request, 'You cannot purchase your own product')
            return redirect('product_detail', product_type=product_type, product_id=product_id)

        # Check if seller has Stripe Account ID (for marketplace payments)
        seller = getattr(product, 'seller', None)
        if seller and not seller.stripe_account_id:
            messages.error(request, 'This seller has not set up their payment account yet. Please try again later.')
            return redirect('product_detail', product_type=product_type, product_id=product_id)

        logger.info(f"Creating Stripe session for product purchase: {product.title}")

        # Get site settings for commission
        site_settings = SiteSettings.get_settings()

        # Calculate commission
        commission_amount = site_settings.get_commission_amount(product.price)
        commission_cents = int(commission_amount * 100)  # Convert to cents for Stripe

        logger.info(f"Product price: ${product.price}, Commission: ${commission_amount} ({site_settings.commission_percentage}%)")

        # Build Stripe Checkout Session parameters
        session_params = {
            'payment_method_types': ['card'],
            'line_items': [{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': int(product.price * 100),  # Convert to cents
                    'product_data': {
                        'name': product.title,
                        'description': product.description[:500] if len(product.description) > 500 else product.description,
                    },
                },
                'quantity': 1,
            }],
            'mode': 'payment',
            'success_url': request.build_absolute_uri(
                reverse('purchase_success_callback')
            ) + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': request.build_absolute_uri(
                reverse('product_detail', kwargs={'product_type': product_type, 'product_id': product_id})
            ),
            'customer_email': request.user.email,
            'client_reference_id': str(request.user.id),
            'metadata': {
                'user_id': request.user.id,
                'product_type': product_type,
                'product_id': product.id,
                'seller_id': seller.id if seller else None,
                'purchase_type': 'single',
                'commission_amount': str(commission_amount),
            }
        }

        # Add Stripe Connect payment_intent_data if commission is enabled and seller has account
        if site_settings.commission_enabled and seller and seller.stripe_account_id and commission_cents > 0:
            if not site_settings.platform_stripe_account_id:
                logger.error("COMMISSION WARNING: Platform Stripe Account ID not set! Commission split will NOT work.")
                messages.warning(
                    request,
                    'Platform payment account not configured. Please contact support.'
                )
            else:
                session_params['payment_intent_data'] = {
                    'application_fee_amount': commission_cents,  # Platform commission in cents
                    'transfer_data': {
                        'destination': seller.stripe_account_id,  # Seller receives the rest
                    },
                }
                logger.info(f"Commission enabled: Platform gets ${commission_amount}, Seller gets ${product.price - commission_amount}")

        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(**session_params)

        logger.info(f"Stripe session created: {checkout_session.id}")
        return redirect(checkout_session.url, code=303)

    except Exception as e:
        logger.error(f"Error creating purchase session: {str(e)}")
        messages.error(request, 'Failed to initiate purchase. Please try again.')
        return redirect('buyer_dashboard')


@login_required
def create_stripe_connect_account(request):
    """
    Create a Stripe Connect Express account for the seller and return onboarding link
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})

    try:
        # Create a Stripe Connect Express account
        account = stripe.Account.create(
            type='express',
            country='US',
            email=request.user.email,
            capabilities={
                'card_payments': {'requested': True},
                'transfers': {'requested': True},
            },
            business_type='individual',
            metadata={
                'user_id': request.user.id,
                'username': request.user.username,
                'email': request.user.email,
            }
        )

        # Save the account ID to user
        request.user.stripe_account_id = account.id
        request.user.stripe_connect_status = 'pending'
        request.user.save()

        logger.info(f"Created Stripe Connect account {account.id} for user {request.user.username}")

        # Create account link for onboarding
        account_link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=request.build_absolute_uri(reverse('settings')),
            return_url=request.build_absolute_uri(reverse('stripe_connect_return')),
            type='account_onboarding',
        )

        return JsonResponse({
            'success': True,
            'onboarding_url': account_link.url,
            'message': 'Stripe Connect account created. Redirecting to onboarding...'
        })

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating Connect account: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Stripe error: {str(e)}'})
    except Exception as e:
        logger.error(f"Error creating Stripe Connect account: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


@login_required
def stripe_connect_return(request):
    """
    Handle return from Stripe Connect onboarding
    """
    try:
        # Retrieve the account to check status
        if request.user.stripe_account_id:
            account = stripe.Account.retrieve(request.user.stripe_account_id)

            # Check if account is fully onboarded
            if account.details_submitted:
                request.user.stripe_connect_status = 'active'
                request.user.save()
                messages.success(request, 'Stripe Connect account setup completed! You can now receive payments automatically.')
                logger.info(f"Stripe Connect onboarding completed for user {request.user.username}")
            else:
                request.user.stripe_connect_status = 'pending'
                request.user.save()
                messages.warning(request, 'Stripe Connect setup incomplete. Please complete all required information.')
        else:
            messages.error(request, 'No Stripe Connect account found.')

    except stripe.error.StripeError as e:
        logger.error(f"Error checking Stripe Connect status: {str(e)}")
        messages.error(request, 'Error verifying Stripe Connect account.')

    return redirect('settings')


@login_required
def refresh_stripe_connect_link(request):
    """
    Generate a new onboarding link for existing Stripe Connect account
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})

    if not request.user.stripe_account_id:
        return JsonResponse({'success': False, 'message': 'No Stripe Connect account found. Please create one first.'})

    try:
        # Create a new account link
        account_link = stripe.AccountLink.create(
            account=request.user.stripe_account_id,
            refresh_url=request.build_absolute_uri(reverse('settings')),
            return_url=request.build_absolute_uri(reverse('stripe_connect_return')),
            type='account_onboarding',
        )

        return JsonResponse({
            'success': True,
            'onboarding_url': account_link.url,
            'message': 'Redirecting to Stripe Connect onboarding...'
        })

    except stripe.error.StripeError as e:
        logger.error(f"Error creating account link: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Stripe error: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def purchase_cart(request):
    """
    Purchase all items in cart through Stripe - Returns JSON for toast notifications
    """
    logger.info(f"purchase_cart called for user: {request.user.username}")

    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'You must be logged in to purchase'})

    try:
        # Get user's cart
        cart = Cart.objects.get(user=request.user)
        logger.info(f"Cart found with {cart.items.count()} items")

        if not cart.items.exists():
            return JsonResponse({'success': False, 'message': 'Your cart is empty'})

        # Build cart items data for order creation
        cart_items_data = []
        for cart_item in cart.items.all():
            product = cart_item.content_object

            # Get seller if product has one
            if hasattr(product, 'seller'):
                seller = product.seller
            else:
                seller = None

            # Store cart item data for metadata
            cart_items_data.append({
                'content_type_id': cart_item.content_type.id,
                'object_id': cart_item.object_id,
                'quantity': cart_item.quantity,
                'price': str(cart_item.content_object.price),
                'seller_id': seller.id if seller else None
            })

        # Get site settings for commission
        site_settings = SiteSettings.get_settings()

        # Calculate total and commission for each item
        total_amount = Decimal('0.00')
        total_commission = Decimal('0.00')

        for cart_item in cart.items.all():
            product = cart_item.content_object
            item_total = product.price * cart_item.quantity
            item_commission = site_settings.get_commission_amount(item_total)
            total_amount += item_total
            total_commission += item_commission

        logger.info(f"Cart total: ${total_amount}, Total commission: ${total_commission} ({site_settings.commission_percentage}%)")

        # Check if all items are from the same seller
        unique_sellers = set()
        for item_data in cart_items_data:
            if item_data['seller_id']:
                unique_sellers.add(item_data['seller_id'])

        single_seller = None
        if len(unique_sellers) == 1:
            single_seller = User.objects.get(id=list(unique_sellers)[0])
            logger.info(f"Cart has single seller: {single_seller.username}")
        elif len(unique_sellers) > 1:
            logger.warning(f"Cart has multiple sellers ({len(unique_sellers)}). Automatic commission split not available.")

        # Build line items for Stripe
        line_items = []
        for cart_item in cart.items.all():
            product = cart_item.content_object
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': int(product.price * 100),  # Convert to cents
                    'product_data': {
                        'name': product.title,
                        'description': product.description[:500] if hasattr(product, 'description') else '',
                    },
                },
                'quantity': cart_item.quantity,
            })

        # Build Stripe Checkout Session parameters
        session_params = {
            'payment_method_types': ['card'],
            'line_items': line_items,
            'mode': 'payment',
            'success_url': request.build_absolute_uri(reverse('purchase_success_callback')) + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': request.build_absolute_uri(reverse('cart')),
            'metadata': {
                'user_id': request.user.id,
                'purchase_type': 'cart',
                'cart_items': json.dumps(cart_items_data),
                'total_commission': str(total_commission),
                'commission_percentage': str(site_settings.commission_percentage),
            }
        }

        # Apply payment strategy based on seller configuration
        if len(unique_sellers) == 1 and single_seller:
            # Single seller cart
            if single_seller.stripe_connect_status == 'active' and single_seller.stripe_account_id:
                # Seller has active Stripe Connect - use destination charge (instant split)
                commission_cents = int(total_commission * 100)
                session_params['payment_intent_data'] = {
                    'application_fee_amount': commission_cents,  # Platform commission
                    'transfer_data': {
                        'destination': single_seller.stripe_account_id,  # Seller gets the rest
                    },
                }
                logger.info(
                    f"Single seller cart ({single_seller.username}) - Using Stripe Connect destination charge | "
                    f"Platform: ${total_commission} | Seller: ${total_amount - total_commission}"
                )
            else:
                # Seller not connected - use Stripe Transfers after payment
                logger.info(
                    f"Single seller cart ({single_seller.username}) - Seller not connected. "
                    f"Will use Stripe Transfers after payment | Payout: ${total_amount - total_commission}"
                )
        elif len(unique_sellers) > 1:
            # Multiple sellers - always use Stripe Transfers after payment
            logger.info(
                f"Multiple sellers in cart ({len(unique_sellers)} sellers) - "
                f"Will distribute via Stripe Transfers after payment"
            )
        # Transfers will be processed automatically in the success callback for non-connected sellers

        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(**session_params)

        # Return checkout URL for JavaScript redirect
        return JsonResponse({
            'success': True,
            'checkout_url': checkout_session.url,
            'message': 'Redirecting to checkout...'
        })

    except Cart.DoesNotExist:
        logger.error("Cart not found for user")
        return JsonResponse({'success': False, 'message': 'Cart not found'})
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in cart purchase: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Payment error: {str(e)}'})
    except Exception as e:
        logger.error(f"Error creating cart checkout session: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Failed to initiate checkout: {str(e)}. Please try again.'})


@login_required
def purchase_success_callback(request):
    """
    Handle successful Stripe payment and create order
    """
    session_id = request.GET.get('session_id')

    if not session_id:
        messages.error(request, 'Invalid payment session')
        return redirect('buyer_dashboard')

    try:
        # Retrieve the Stripe session
        checkout_session = stripe.checkout.Session.retrieve(session_id)

        # Verify payment was successful
        if checkout_session.payment_status != 'paid':
            messages.error(request, 'Payment was not completed')
            return redirect('buyer_dashboard')

        # Get metadata
        user_id = int(checkout_session.metadata.get('user_id'))
        purchase_type = checkout_session.metadata.get('purchase_type')

        # Verify the user matches
        if user_id != request.user.id:
            messages.error(request, 'Invalid payment session')
            return redirect('buyer_dashboard')

        # Check if order already exists (prevent duplicate orders)
        existing_order = Order.objects.filter(
            user=request.user,
            stripe_session_id=session_id
        ).first()

        if existing_order:
            messages.info(request, f'Order #{existing_order.order_number} was already processed')
            return redirect('orders')

        # Create order based on purchase type
        if purchase_type == 'single':
            # Single product purchase
            product_type = checkout_session.metadata.get('product_type')
            product_id = int(checkout_session.metadata.get('product_id'))
            seller_id = checkout_session.metadata.get('seller_id')

            # Get product
            if product_type == 'book':
                product = Book.objects.get(id=product_id)
            elif product_type == 'course':
                product = Course.objects.get(id=product_id)
            elif product_type == 'webinar':
                product = Webinar.objects.get(id=product_id)
            elif product_type == 'service':
                product = Service.objects.get(id=product_id)
            else:
                raise ValueError(f'Invalid product type: {product_type}')

            # Create order
            order = Order.objects.create(
                user=request.user,
                order_number=Order.generate_order_number(),
                total_amount=product.price,
                status='completed',
                stripe_session_id=session_id
            )

            # Create order item
            content_type = ContentType.objects.get_for_model(product)
            OrderItem.objects.create(
                order=order,
                content_type=content_type,
                object_id=product.id,
                quantity=1,
                price=product.price
            )

            # Send notifications
            Notification.objects.create(
                user=request.user,
                notification_type='order_created',
                title='Order Placed Successfully!',
                message=f'Your order #{order.order_number} for "{product.title}" has been placed.',
                link=reverse('orders')
            )

            # Notify seller if exists
            if seller_id and hasattr(product, 'seller'):
                Notification.objects.create(
                    user=product.seller,
                    notification_type='new_sale',
                    title='New Sale!',
                    message=f'{request.user.full_name} purchased your product: "{product.title}"',
                    link=reverse('seller_dashboard')
                )

            # Auto-create ServiceChat for service purchases and redirect to chat
            if product_type == 'service':
                logger.info(f"Service purchased: Creating/getting ServiceChat for buyer {request.user.username} and seller {product.seller.username}")
                service_chat, created = ServiceChat.objects.get_or_create(
                    buyer=request.user,
                    seller=product.seller,
                    service=product
                )
                if created:
                    logger.info(f"ServiceChat created: ID={service_chat.id}")
                    # Notify buyer about chat
                    Notification.objects.create(
                        user=request.user,
                        notification_type='order_created',
                        title='Chat Opened!',
                        message=f'You can now chat with {product.seller.full_name} about "{product.title}"',
                        link=reverse('service_chat', kwargs={'service_id': product.id})
                    )
                else:
                    logger.info(f"ServiceChat already exists: ID={service_chat.id}")

                messages.success(request, f'Order #{order.order_number} placed successfully! Opening chat with seller...')
                # Redirect to chat instead of orders page
                return redirect('service_chat', service_id=product.id)

            messages.success(request, f'Order #{order.order_number} placed successfully!')

        elif purchase_type == 'cart':
            # Cart purchase
            cart_items_json = checkout_session.metadata.get('cart_items')
            cart_items_data = json.loads(cart_items_json)

            # Calculate total from cart items
            total_amount = sum(Decimal(item['price']) * item['quantity'] for item in cart_items_data)

            # Create order
            order = Order.objects.create(
                user=request.user,
                order_number=Order.generate_order_number(),
                total_amount=total_amount,
                status='completed',
                stripe_session_id=session_id
            )

            # Create order items, notify sellers, and create service chats
            sellers_notified = set()
            service_chats_created = []
            item_count = 0

            for item_data in cart_items_data:
                content_type = ContentType.objects.get_for_id(item_data['content_type_id'])
                product = content_type.get_object_for_this_type(id=item_data['object_id'])

                OrderItem.objects.create(
                    order=order,
                    content_type=content_type,
                    object_id=item_data['object_id'],
                    quantity=item_data['quantity'],
                    price=Decimal(item_data['price'])
                )

                # Auto-create ServiceChat if product is a service
                if content_type.model == 'service' and hasattr(product, 'seller'):
                    logger.info(f"Cart contains service: Creating ServiceChat for {product.title}")
                    service_chat, created = ServiceChat.objects.get_or_create(
                        buyer=request.user,
                        seller=product.seller,
                        service=product
                    )
                    if created:
                        logger.info(f"ServiceChat created for cart service: ID={service_chat.id}")
                        service_chats_created.append(service_chat)

                # Notify seller
                seller_id = item_data.get('seller_id')
                if seller_id and seller_id not in sellers_notified:
                    seller = User.objects.get(id=seller_id)
                    Notification.objects.create(
                        user=seller,
                        notification_type='new_sale',
                        title='New Sale!',
                        message=f'{request.user.full_name} purchased your product: "{product.title}"',
                        link=reverse('seller_dashboard')
                    )
                    sellers_notified.add(seller_id)

                item_count += 1

            # Process Stripe Transfers for each seller (commission split)
            site_settings = SiteSettings.get_settings()

            if site_settings.commission_enabled and checkout_session.payment_status == 'paid':
                # Group items by seller and calculate each seller's total
                seller_totals = {}  # {seller_id: {'total': Decimal, 'seller': User, 'items': []}}

                for item_data in cart_items_data:
                    seller_id = item_data.get('seller_id')
                    if seller_id:
                        item_total = Decimal(item_data['price']) * item_data['quantity']

                        if seller_id not in seller_totals:
                            seller_totals[seller_id] = {
                                'total': Decimal('0.00'),
                                'seller': User.objects.get(id=seller_id),
                                'items': []
                            }

                        seller_totals[seller_id]['total'] += item_total
                        seller_totals[seller_id]['items'].append(item_data)

                # Create Stripe Transfer for each seller
                for seller_id, data in seller_totals.items():
                    seller = data['seller']
                    seller_total = data['total']

                    # Calculate commission for this seller's items
                    seller_commission = site_settings.get_commission_amount(seller_total)
                    seller_payout = seller_total - seller_commission

                    # Convert to cents for Stripe
                    seller_payout_cents = int(seller_payout * 100)

                    if seller_payout_cents > 0 and seller.stripe_account_id:
                        try:
                            # Create Stripe Transfer to seller
                            transfer = stripe.Transfer.create(
                                amount=seller_payout_cents,
                                currency='usd',
                                destination=seller.stripe_account_id,
                                description=f'Payout for order #{order.order_number}',
                                metadata={
                                    'order_id': order.id,
                                    'order_number': order.order_number,
                                    'seller_id': seller.id,
                                    'seller_username': seller.username,
                                    'seller_total': str(seller_total),
                                    'commission': str(seller_commission),
                                    'payout': str(seller_payout),
                                }
                            )

                            logger.info(
                                f"Stripe Transfer created: {transfer.id} | "
                                f"Order: {order.order_number} | "
                                f"Seller: {seller.username} | "
                                f"Total: ${seller_total} | "
                                f"Commission: ${seller_commission} ({site_settings.commission_percentage}%) | "
                                f"Payout: ${seller_payout}"
                            )

                            # Notify seller about payout
                            Notification.objects.create(
                                user=seller,
                                notification_type='new_sale',
                                title='Payment Received!',
                                message=f'${seller_payout} transferred to your account for order #{order.order_number}',
                                link=reverse('seller_dashboard')
                            )

                        except stripe.error.StripeError as e:
                            error_msg = str(e)
                            logger.error(
                                f"Stripe Transfer FAILED for seller {seller.username}: {error_msg} | "
                                f"Order: {order.order_number} | Amount: ${seller_payout}"
                            )

                            # Determine if it's a connection issue
                            if "No such destination" in error_msg or "platform_account_required" in error_msg:
                                logger.critical(
                                    f"STRIPE CONNECT NOT CONFIGURED: Seller {seller.username} account ID '{seller.stripe_account_id}' "
                                    f"is not a connected account. Payout ${seller_payout} is PENDING for order {order.order_number}"
                                )

                                # Notify seller about pending payout
                                Notification.objects.create(
                                    user=seller,
                                    notification_type='new_sale',
                                    title='New Sale! (Payout Pending)',
                                    message=f'You made a sale! ${seller_payout} is pending. Please complete Stripe Connect setup to receive automatic payouts. Order: #{order.order_number}',
                                    link=reverse('seller_dashboard')
                                )
                            elif "insufficient" in error_msg.lower() and "funds" in error_msg.lower():
                                # Insufficient funds error (common in test mode)
                                logger.warning(
                                    f"INSUFFICIENT FUNDS for transfer: Seller {seller.username} payout ${seller_payout} for order {order.order_number}. "
                                    f"This is normal in test mode. In production, funds from completed charges become available automatically."
                                )

                                # Notify seller - sale completed, payout pending
                                Notification.objects.create(
                                    user=seller,
                                    notification_type='new_sale',
                                    title='New Sale! (Payout Processing)',
                                    message=f'You made a sale of ${seller_total}! Your payout of ${seller_payout} (after {site_settings.commission_percentage}% commission) will be processed shortly. Order: #{order.order_number}',
                                    link=reverse('seller_dashboard')
                                )
                            else:
                                # Other Stripe errors
                                logger.critical(f"MANUAL PAYOUT NEEDED: ${seller_payout} to {seller.username} for order {order.order_number}")

                                # Notify seller about sale but payment issue
                                Notification.objects.create(
                                    user=seller,
                                    notification_type='new_sale',
                                    title='New Sale! (Payout Issue)',
                                    message=f'You made a sale! ${seller_payout} payout encountered an issue. Platform will contact you. Order: #{order.order_number}',
                                    link=reverse('seller_dashboard')
                                )
                    else:
                        if not seller.stripe_account_id:
                            logger.warning(f"Seller {seller.username} has no Stripe account ID - cannot transfer ${seller_payout}")
                        else:
                            logger.warning(f"Payout amount for seller {seller.username} is $0 or negative")

            # Send notification to buyer
            Notification.objects.create(
                user=request.user,
                notification_type='order_created',
                title='Order Placed Successfully!',
                message=f'Your order #{order.order_number} with {item_count} item(s) has been placed.',
                link=reverse('orders')
            )

            # Notify about service chats if any were created
            if service_chats_created:
                for chat in service_chats_created:
                    Notification.objects.create(
                        user=request.user,
                        notification_type='order_created',
                        title='Service Chat Opened!',
                        message=f'You can now chat with {chat.seller.full_name} about "{chat.service.title}"',
                        link=reverse('service_chat', kwargs={'service_id': chat.service.id})
                    )

            # Clear the cart
            try:
                cart = Cart.objects.get(user=request.user)
                cart.items.all().delete()
            except Cart.DoesNotExist:
                pass

            success_msg = f'Order #{order.order_number} with {item_count} items placed successfully!'
            if service_chats_created:
                success_msg += f' {len(service_chats_created)} service chat(s) opened!'
            messages.success(request, success_msg)

        else:
            messages.error(request, 'Invalid purchase type')
            return redirect('buyer_dashboard')

        # Redirect to orders page
        return redirect('orders')

    except stripe.error.StripeError as e:
        print(f"Stripe error in purchase callback: {str(e)}")
        messages.error(request, 'Failed to verify payment. Please contact support.')
        return redirect('buyer_dashboard')
    except Exception as e:
        print(f"Error in purchase callback: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, 'An error occurred while processing your order. Please contact support.')
        return redirect('buyer_dashboard')


@login_required
def switch_user_type(request):
    """
    Toggle user type between buyer and seller (same account).
    Requires payment for the target role before switching.
    """
    if request.method == 'POST':
        user = request.user

        # Determine target role
        if user.user_type == 'buyer':
            target_role = 'seller'
            target_dashboard = 'seller_dashboard'
            has_access = user.seller_access_paid
        else:
            target_role = 'buyer'
            target_dashboard = 'buyer_dashboard'
            has_access = user.buyer_access_paid

        # Check if user has paid for target role
        if not has_access:
            messages.warning(
                request,
                f'You need to purchase {target_role.title()} access to switch to the {target_role} dashboard. '
                f'Pay ${django_settings.BUYER_REGISTRATION_FEE if target_role == "buyer" else django_settings.SELLER_REGISTRATION_FEE} to unlock access.'
            )
            return redirect('role_upgrade_payment', role=target_role)

        # User has access, switch the role
        user.user_type = target_role
        user.save()

        messages.success(request, f'You have switched to {target_role.title()} mode!')
        return redirect(target_dashboard)

    # If not POST, redirect to appropriate dashboard
    if request.user.user_type == 'buyer':
        return redirect('buyer_dashboard')
    else:
        return redirect('seller_dashboard')


@login_required
def download_product(request, order_id, item_id):
    """
    Download purchased product file
    """
    try:
        # Get the order and verify ownership
        order = get_object_or_404(Order, id=order_id, user=request.user)
        order_item = get_object_or_404(OrderItem, id=item_id, order=order)

        # Only allow download for completed orders
        if order.status != 'completed':
            return JsonResponse({'success': False, 'message': 'Product can only be downloaded for completed orders'})

        # Get the product and its file
        product = order_item.content_object

        if order_item.content_type.model == 'book' and product.book_file:
            file_field = product.book_file
            filename = f"{product.title}_Book.{file_field.name.split('.')[-1]}"
        elif order_item.content_type.model == 'course' and product.course_file:
            file_field = product.course_file
            filename = f"{product.title}_Course.{file_field.name.split('.')[-1]}"
        elif order_item.content_type.model == 'webinar' and product.webinar_file:
            file_field = product.webinar_file
            filename = f"{product.title}_Webinar.{file_field.name.split('.')[-1]}"
        else:
            return JsonResponse({'success': False, 'message': 'Product file not found'})

        # Create file response for download
        from django.http import FileResponse
        import os

        if os.path.exists(file_field.path):
            response = FileResponse(
                open(file_field.path, 'rb'),
                as_attachment=True,
                filename=filename
            )
            return response
        else:
            return JsonResponse({'success': False, 'message': 'Product file not found on server'})

    except Exception as e:
        return JsonResponse({'success': False, 'message': 'Failed to download product file'})


@login_required
def chatbot(request):
    """
    AI Support chatbot page

    Note: Products are automatically indexed when added/edited/deleted,
    so no need to re-index on every page load.
    """
    context = {
        'user': request.user,
        'full_name': request.user.full_name,
    }
    return render(request, 'src/chatboat.html', context)


@csrf_exempt
def chatbot_message(request):
    """
    Handle chatbot messages via AJAX
    GET: Load chat history for session
    POST: Send new message
    (CSRF exempt for easier debugging - should use proper CSRF in production)
    """
    # Log the request for debugging
    print(f"Chatbot message request: {request.method}")
    print(f"User authenticated: {request.user.is_authenticated}")
    print(f"Request body: {request.body[:100] if request.body else 'Empty'}")

    if request.method == 'GET':
        # Load chat history
        import json
        from .models import ChatSession, ChatMessage

        session_id = request.GET.get('session_id')
        if not session_id or not request.user.is_authenticated:
            return JsonResponse({'success': True, 'messages': []})

        try:
            chat_session = ChatSession.objects.get(session_id=session_id, user=request.user)
            messages = ChatMessage.objects.filter(session=chat_session).order_by('created_at')

            message_list = []
            for msg in messages:
                message_list.append({
                    'question': msg.question,
                    'answer': msg.answer,
                    'created_at': msg.created_at.isoformat()
                })

            return JsonResponse({
                'success': True,
                'messages': message_list,
                'session_id': session_id
            })
        except ChatSession.DoesNotExist:
            return JsonResponse({'success': True, 'messages': []})

    elif request.method == 'POST':
        import json
        import uuid
        from .models import ChatSession, ChatMessage
        from .chatbot_helper import search_products, generate_chat_response
        from django.http import StreamingHttpResponse

        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            session_id = data.get('session_id', None)

            if not user_message:
                return JsonResponse({'success': False, 'message': 'Empty message'})

            # Get or create session (handle anonymous users)
            if request.user.is_authenticated:
                if session_id:
                    try:
                        chat_session = ChatSession.objects.get(session_id=session_id, user=request.user)
                    except ChatSession.DoesNotExist:
                        session_id = str(uuid.uuid4())
                        chat_session = ChatSession.objects.create(user=request.user, session_id=session_id)
                else:
                    session_id = str(uuid.uuid4())
                    chat_session = ChatSession.objects.create(user=request.user, session_id=session_id)
            else:
                # For anonymous users, don't save to database
                session_id = str(uuid.uuid4())
                chat_session = None

            # Search for relevant products using Pinecone
            context_products = search_products(user_message, n_results=5)

            # Generate AI response using OpenAI (streaming)
            stream = generate_chat_response(user_message, context_products)

            # Collect full response from stream
            full_response = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content

            # Save complete message to database (only for authenticated users)
            if chat_session:
                ChatMessage.objects.create(
                    session=chat_session,
                    user=request.user,
                    question=user_message,
                    answer=full_response
                )

            # Return complete response as JSON
            return JsonResponse({
                'success': True,
                'response': full_response,
                'session_id': session_id
            })

        except Exception as e:
            print(f"Chatbot error: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def get_notifications(request):
    """API endpoint to get user notifications"""
    from .models import Notification

    # Get unread notifications count
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

    # Get recent notifications (last 10)
    notifications = Notification.objects.filter(user=request.user)[:10]

    notifications_data = []
    for notif in notifications:
        notifications_data.append({
            'id': notif.id,
            'type': notif.notification_type,
            'title': notif.title,
            'message': notif.message,
            'link': notif.link,
            'is_read': notif.is_read,
            'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'time_ago': get_time_ago(notif.created_at)
        })

    return JsonResponse({
        'success': True,
        'unread_count': unread_count,
        'notifications': notifications_data
    })


@login_required
def mark_notifications_read(request):
    """Mark all notifications as read"""
    from .models import Notification

    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True, 'message': 'Notifications marked as read'})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    from .models import Notification

    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True, 'message': 'Notification marked as read'})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Notification not found'})


def get_time_ago(created_at):
    """Helper function to convert datetime to 'time ago' format"""
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    diff = now - created_at

    if diff < timedelta(minutes=1):
        return 'Just now'
    elif diff < timedelta(hours=1):
        minutes = int(diff.total_seconds() / 60)
        return f'{minutes} minute{"s" if minutes > 1 else ""} ago'
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f'{hours} hour{"s" if hours > 1 else ""} ago'
    elif diff < timedelta(days=7):
        days = diff.days
        return f'{days} day{"s" if days > 1 else ""} ago'
    elif diff < timedelta(days=30):
        weeks = int(diff.days / 7)
        return f'{weeks} week{"s" if weeks > 1 else ""} ago'
    else:
        months = int(diff.days / 30)
        return f'{months} month{"s" if months > 1 else ""} ago'


@login_required
def rate_product(request, order_item_id):
    """Allow buyers to rate purchased products"""
    if request.method == 'POST':
        try:
            import json
            from .models import Rating, OrderItem, Notification
            from django.urls import reverse

            data = json.loads(request.body)
            rating_value = int(data.get('rating', 0))

            # Validate rating
            if not (1 <= rating_value <= 5):
                return JsonResponse({'success': False, 'message': 'Invalid rating value'})

            # Get order item and verify ownership
            order_item = OrderItem.objects.get(id=order_item_id, order__user=request.user)

            # Create or update rating
            rating, created = Rating.objects.update_or_create(
                user=request.user,
                order_item=order_item,
                defaults={
                    'rating': rating_value
                }
            )

            # Create notification for seller
            product = order_item.content_object
            if hasattr(product, 'seller'):
                Notification.objects.create(
                    user=product.seller,
                    notification_type='general',
                    title='New Product Rating!',
                    message=f'{request.user.full_name} rated your product "{product.title}" - {rating_value} stars',
                    link=reverse('seller_dashboard')
                )

            action = 'added' if created else 'updated'
            return JsonResponse({
                'success': True,
                'message': f'Rating {action} successfully!',
                'rating': rating_value
            })

        except OrderItem.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Order item not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})


def all_products(request, product_type):
    """
    View to display all products of a specific type (books, courses, webinars, or services)
    with search and category filtering
    OPTIMIZED for fast performance
    """
    # Get search query and category filter from request
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('category', '')

    # OPTIMIZATION: select_related() to prefetch related objects
    if product_type == 'book':
        products = Book.objects.filter(is_active=True).select_related('category', 'seller')
        title = 'All Books'
    elif product_type == 'course':
        products = Course.objects.filter(is_active=True).select_related('category', 'seller')
        title = 'All Courses'
    elif product_type == 'webinar':
        products = Webinar.objects.filter(is_active=True).select_related('category', 'seller')
        title = 'All Webinars'
    elif product_type == 'service':
        products = Service.objects.filter(is_active=True).select_related('category', 'seller')
        title = 'All Services'
    else:
        return redirect('home')

    # Apply search filter (title only)
    if search_query:
        products = products.filter(title__icontains=search_query)

    # Apply category filter
    if category_id:
        products = products.filter(category_id=category_id)

    # Order by creation date
    products = products.order_by('-created_at')

    # Get all categories for filter dropdown
    categories = Category.objects.all()

    # Get purchased service IDs for logged-in users (only for services)
    purchased_service_ids = []
    if request.user.is_authenticated and product_type == 'service':
        service_content_type = ContentType.objects.get_for_model(Service)
        purchased_service_ids = OrderItem.objects.filter(
            order__user=request.user,
            content_type=service_content_type
        ).values_list('object_id', flat=True).distinct()

    context = {
        'products': products,
        'product_type': product_type,
        'title': title,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_id,
        'purchased_service_ids': list(purchased_service_ids),
    }

    return render(request, 'src/all_products.html', context)


# ==============================================================================
# BUYER-SELLER CHAT VIEWS
# ==============================================================================

@login_required
def get_seller_chat_stats(request):
    """
    API endpoint to get seller's chat statistics (total chats and unread count).
    Returns JSON response.
    """
    if request.user.user_type != 'seller':
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    try:
        # Get total chats count
        total_chats = ServiceChat.objects.filter(seller=request.user).count()

        # Get unread messages count
        unread_count = ServiceChatMessage.objects.filter(
            chat__seller=request.user,
            sender__user_type='buyer',  # Messages from buyers
            is_read=False
        ).count()

        return JsonResponse({
            'success': True,
            'total_chats': total_chats,
            'unread_count': unread_count
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def seller_messages_redirect(request):
    """
    Redirect to the most recent chat for sellers.
    If no chats exist, show a message.
    """
    if request.user.user_type != 'seller':
        messages.error(request, 'This page is only accessible to sellers.')
        return redirect('buyer_dashboard')

    # Get the most recent chat
    recent_chat = ServiceChat.objects.filter(
        seller=request.user
    ).select_related('buyer', 'service').order_by('-updated_at').first()

    if recent_chat:
        # Redirect to the most recent chat with buyer_id parameter
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        url = reverse('service_chat', kwargs={'service_id': recent_chat.service.id})
        return HttpResponseRedirect(f'{url}?buyer_id={recent_chat.buyer.id}')
    else:
        # No chats yet
        messages.info(request, 'No customer messages yet. Chats will appear here when customers contact you.')
        return redirect('seller_dashboard')


@login_required
def service_chat_window(request, service_id):
    """
    Chat window for buyer-seller communication about a purchased service.
    Accessible only if the user has purchased the service (buyer) or sold it (seller).
    """
    service = get_object_or_404(Service, id=service_id, is_active=True)
    user = request.user

    # Determine user role and validate access
    if user.user_type == 'buyer':
        # Check if buyer purchased this service
        has_purchased = OrderItem.objects.filter(
            order__user=user,
            content_type=ContentType.objects.get_for_model(Service),
            object_id=service_id
        ).exists()

        if not has_purchased:
            messages.error(request, 'You must purchase this service to chat with the seller.')
            return redirect('buyer_dashboard')

        buyer = user
        seller = service.seller
        other_user = seller

    elif user.user_type == 'seller':
        # Check if seller owns this service
        if service.seller != user:
            messages.error(request, 'You can only chat about services you sell.')
            return redirect('seller_dashboard')

        seller = user
        # Find the buyer from the request parameter or the chat
        buyer_id = request.GET.get('buyer_id')
        if not buyer_id:
            messages.error(request, 'Buyer information is required.')
            return redirect('seller_dashboard')

        buyer = get_object_or_404(User, id=buyer_id, user_type='buyer')
        other_user = buyer

        # Verify buyer purchased this service
        has_purchased = OrderItem.objects.filter(
            order__user=buyer,
            content_type=ContentType.objects.get_for_model(Service),
            object_id=service_id
        ).exists()

        if not has_purchased:
            messages.error(request, 'This buyer has not purchased this service.')
            return redirect('seller_dashboard')

    else:
        messages.error(request, 'Invalid user type.')
        return redirect('home')

    # Get or create chat conversation
    chat, created = ServiceChat.objects.get_or_create(
        buyer=buyer,
        seller=seller,
        service=service
    )

    # Mark all messages from other user as read
    ServiceChatMessage.objects.filter(
        chat=chat,
        sender=other_user,
        is_read=False
    ).update(is_read=True)

    # Get all messages
    messages_list = chat.messages.select_related('sender').all()

    # For sellers, get all their chats for the sidebar
    seller_chats = []
    if user.user_type == 'seller':
        all_chats = ServiceChat.objects.filter(
            seller=user
        ).select_related('buyer', 'service').prefetch_related('messages').order_by('-updated_at')

        for c in all_chats:
            unread_count = ServiceChatMessage.objects.filter(
                chat=c,
                sender=c.buyer,
                is_read=False
            ).count()

            last_message = c.messages.order_by('-created_at').first()

            seller_chats.append({
                'chat': c,
                'unread_count': unread_count,
                'last_message': last_message,
                'is_active': c.id == chat.id,
            })

    context = {
        'chat': chat,
        'service': service,
        'messages': messages_list,
        'other_user': other_user,
        'user_type': user.user_type,
        'seller_chats': seller_chats,  # For sidebar navigation
    }

    return render(request, 'src/chat_window.html', context)


@login_required
def send_service_message(request, chat_id):
    """
    API endpoint to send a message in a service chat.
    POST only. Returns JSON response.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    chat = get_object_or_404(ServiceChat, id=chat_id)
    user = request.user

    # Verify user is part of this chat
    if user != chat.buyer and user != chat.seller:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

    # Get message content
    message_text = request.POST.get('message', '').strip()
    if not message_text:
        return JsonResponse({'success': False, 'error': 'Message cannot be empty'}, status=400)

    # Create message
    message = ServiceChatMessage.objects.create(
        chat=chat,
        sender=user,
        message=message_text,
        is_read=False
    )

    return JsonResponse({
        'success': True,
        'message': {
            'id': message.id,
            'sender_name': message.sender.full_name,
            'sender_id': message.sender.id,
            'message': message.message,
            'created_at': message.created_at.strftime('%I:%M %p'),
            'is_current_user': message.sender == user
        }
    })


@login_required
def get_service_messages(request, chat_id):
    """
    API endpoint to fetch all messages in a service chat.
    GET only. Returns JSON response.
    """
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    chat = get_object_or_404(ServiceChat, id=chat_id)
    user = request.user

    # Verify user is part of this chat
    if user != chat.buyer and user != chat.seller:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

    # Mark messages from other user as read
    other_user = chat.seller if user == chat.buyer else chat.buyer
    ServiceChatMessage.objects.filter(
        chat=chat,
        sender=other_user,
        is_read=False
    ).update(is_read=True)

    # Get all messages
    messages_list = chat.messages.select_related('sender').all()

    messages_data = [{
        'id': msg.id,
        'sender_name': msg.sender.full_name,
        'sender_id': msg.sender.id,
        'message': msg.message,
        'created_at': msg.created_at.strftime('%I:%M %p'),
        'is_current_user': msg.sender == user
    } for msg in messages_list]

    return JsonResponse({
        'success': True,
        'messages': messages_data,
        'unread_count': 0  # All marked as read
    })


# ==============================================================================
# STRIPE PAYMENT VIEWS
# ==============================================================================

import stripe
from django.conf import settings as django_settings
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

# Initialize Stripe
stripe.api_key = django_settings.STRIPE_SECRET_KEY


@login_required
def registration_payment(request):
    """
    Payment page for registration fees (initial role payment).
    Creates Stripe Checkout Session and redirects to Stripe.
    Only for paying for the role selected during registration.
    """
    # Check if already paid for current role
    if request.user.user_type == 'buyer' and request.user.buyer_access_paid:
        messages.success(request, 'Your buyer account is already active!')
        return redirect('buyer_dashboard')
    elif request.user.user_type == 'seller' and request.user.seller_access_paid:
        messages.success(request, 'Your seller account is already active!')
        return redirect('seller_dashboard')

    # Determine amount based on user type
    if request.user.user_type == 'buyer':
        amount = django_settings.BUYER_REGISTRATION_FEE
        description = 'Buyer Dashboard Access Fee'
        payment_type = 'buyer'
    else:
        amount = django_settings.SELLER_REGISTRATION_FEE
        description = 'Seller Dashboard Access Fee'
        payment_type = 'seller'

    if request.method == 'POST':
        try:
            # Create Stripe Checkout Session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': int(amount * 100),  # Convert to cents
                        'product_data': {
                            'name': description,
                            'description': f'One-time access fee for {request.user.user_type} dashboard',
                        },
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri(
                    reverse('payment_success')
                ) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.build_absolute_uri(reverse('payment_cancelled')),
                customer_email=request.user.email,
                client_reference_id=str(request.user.id),
                metadata={
                    'user_id': request.user.id,
                    'payment_type': payment_type,  # NEW: track which role is being paid for
                    'username': request.user.username,
                    'is_registration': 'true',  # Flag for registration payment
                }
            )

            return redirect(checkout_session.url, code=303)

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error for user {request.user.id}: {str(e)}")
            messages.error(request, f'Payment error: {str(e)}')
        except Exception as e:
            logger.error(f"Payment error for user {request.user.id}: {str(e)}")
            messages.error(request, 'An error occurred. Please try again.')

    context = {
        'amount': amount,
        'user_type': request.user.user_type,
        'payment_type': payment_type,
        'is_upgrade': False,
        'stripe_publishable_key': django_settings.STRIPE_PUBLISHABLE_KEY,
    }
    return render(request, 'registration_payment.html', context)


def payment_success(request):
    """
    Handle successful payment from Stripe Checkout.
    Verifies payment and activates account.

    NOTE: This view does NOT use @login_required because Stripe redirects
    here from their checkout page, and the session may not persist.
    We verify the user through the Stripe session data instead.
    """
    logger.info(f"=== Payment success callback received ===")
    logger.info(f"GET parameters: {request.GET}")
    logger.info(f"Request path: {request.path}")
    logger.info(f"Request method: {request.method}")
    logger.info(f"User authenticated: {request.user.is_authenticated}")

    session_id = request.GET.get('session_id')

    if not session_id:
        logger.error("No session_id in GET parameters")
        messages.error(request, 'Invalid payment session. Please contact support if payment was deducted.')
        return redirect('login')

    logger.info(f"Retrieving Stripe session: {session_id}")

    try:
        # Retrieve the session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        logger.info(f"Stripe session retrieved successfully")
        logger.info(f"Payment status: {session.payment_status}")
        logger.info(f"Client reference ID: {session.client_reference_id}")

        # Get user_id from the session metadata
        user_id = session.client_reference_id

        if not user_id:
            logger.error("No client_reference_id in Stripe session")
            messages.error(request, 'Invalid payment session.')
            return redirect('login')

        # Get the user from database
        try:
            user = User.objects.get(id=user_id)
            logger.info(f"User found: {user.username} (ID: {user.id})")
        except User.DoesNotExist:
            logger.error(f"User with ID {user_id} not found")
            messages.error(request, 'User not found.')
            return redirect('login')

        # Verify payment status
        if session.payment_status == 'paid':
            logger.info("Payment status is 'paid', proceeding with account activation")

            # Get payment metadata to determine which role was paid for
            payment_type = session.metadata.get('payment_type', user.user_type)
            logger.info(f"Payment type from metadata: {payment_type}")

            payment_amount = session.amount_total / 100
            payment_intent_id = session.payment_intent

            # Activate the specific role based on payment_type
            if payment_type == 'buyer' and not user.buyer_access_paid:
                logger.info("Activating buyer access")
                user.buyer_access_paid = True
                user.buyer_payment_date = timezone.now()
                user.buyer_payment_amount = payment_amount
                user.buyer_stripe_payment_intent_id = payment_intent_id
                user.stripe_customer_id = session.customer
                user.account_status = 'active'

                # Backward compatibility
                if not user.registration_paid:
                    user.registration_paid = True
                    user.registration_paid_at = timezone.now()
                    user.registration_amount = payment_amount
                    user.stripe_payment_intent_id = payment_intent_id

                user.save()
                logger.info(f"Buyer access activated for user {user.id} after payment of ${payment_amount}")
                messages.success(request, 'Payment successful! Your Buyer dashboard is now active.')

            elif payment_type == 'seller' and not user.seller_access_paid:
                logger.info("Activating seller access")
                user.seller_access_paid = True
                user.seller_payment_date = timezone.now()
                user.seller_payment_amount = payment_amount
                user.seller_stripe_payment_intent_id = payment_intent_id
                user.stripe_customer_id = session.customer
                user.account_status = 'active'

                # Backward compatibility
                if not user.registration_paid:
                    user.registration_paid = True
                    user.registration_paid_at = timezone.now()
                    user.registration_amount = payment_amount
                    user.stripe_payment_intent_id = payment_intent_id

                user.save()
                logger.info(f"Seller access activated for user {user.id} after payment of ${payment_amount}")
                messages.success(request, 'Payment successful! Your Seller dashboard is now active.')

            else:
                logger.info(f"User already has {payment_type} access, skipping activation")
                messages.info(request, f'Your {payment_type} account is already active.')

            # Log the user in with explicit backend
            if not request.user.is_authenticated:
                from django.contrib.auth import get_backends
                backend = get_backends()[0]
                user.backend = f'{backend.__module__}.{backend.__class__.__name__}'
                login(request, user, backend=user.backend)
                logger.info(f"User {user.id} logged in after successful payment")

            # Redirect to the dashboard for which payment was made
            if payment_type == 'buyer':
                logger.info("Redirecting to buyer dashboard")
                # Update user_type if needed
                if user.user_type != 'buyer':
                    user.user_type = 'buyer'
                    user.save()
                return redirect('buyer_dashboard')
            else:
                logger.info("Redirecting to seller dashboard")
                # Update user_type if needed
                if user.user_type != 'seller':
                    user.user_type = 'seller'
                    user.save()

                # If seller doesn't have Stripe Account ID, show modal
                if not user.stripe_account_id:
                    logger.info("Seller needs to set up Stripe account, showing modal")
                    return render(request, 'stripe_account_setup.html', {
                        'user': user,
                        'show_stripe_modal': True
                    })

                return redirect('seller_dashboard')
        else:
            logger.warning(f"Payment status is not 'paid': {session.payment_status}")
            messages.warning(request, 'Payment not completed. Please try again.')
            return redirect('registration_payment')

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error verifying payment: {str(e)}", exc_info=True)
        messages.error(request, 'Error verifying payment. Please contact support.')
        return redirect('login')
    except Exception as e:
        logger.error(f"Error processing payment success: {str(e)}", exc_info=True)
        messages.error(request, 'An error occurred. Please contact support.')
        return redirect('login')


@login_required
def payment_cancelled(request):
    """Handle cancelled payment."""
    messages.warning(
        request,
        'Payment cancelled. You need to complete payment to activate your account.'
    )
    return redirect('registration_payment')


@login_required
def role_upgrade_payment(request, role):
    """
    Payment page for upgrading to an additional role (buyer or seller).
    Allows users to pay for access to the other dashboard.
    """
    # Validate role parameter
    if role not in ['buyer', 'seller']:
        messages.error(request, 'Invalid role specified.')
        return redirect('buyer_dashboard' if request.user.buyer_access_paid else 'seller_dashboard')

    # Check if already paid for this role
    if role == 'buyer' and request.user.buyer_access_paid:
        messages.success(request, 'You already have buyer access!')
        return redirect('buyer_dashboard')
    elif role == 'seller' and request.user.seller_access_paid:
        messages.success(request, 'You already have seller access!')
        return redirect('seller_dashboard')

    # Determine amount based on role
    if role == 'buyer':
        amount = django_settings.BUYER_REGISTRATION_FEE
        description = 'Buyer Dashboard Access Upgrade'
        current_role = 'seller'
    else:
        amount = django_settings.SELLER_REGISTRATION_FEE
        description = 'Seller Dashboard Access Upgrade'
        current_role = 'buyer'

    if request.method == 'POST':
        try:
            # Create Stripe Checkout Session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': int(amount * 100),  # Convert to cents
                        'product_data': {
                            'name': description,
                            'description': f'Upgrade to {role} dashboard access',
                        },
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri(
                    reverse('payment_success')
                ) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.build_absolute_uri(
                    reverse('role_upgrade_payment', kwargs={'role': role})
                ),
                customer_email=request.user.email,
                client_reference_id=str(request.user.id),
                metadata={
                    'user_id': request.user.id,
                    'payment_type': role,  # Which role is being paid for
                    'username': request.user.username,
                    'is_upgrade': 'true',  # Flag for upgrade payment
                }
            )

            return redirect(checkout_session.url, code=303)

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error for user {request.user.id}: {str(e)}")
            messages.error(request, f'Payment error: {str(e)}')
        except Exception as e:
            logger.error(f"Payment error for user {request.user.id}: {str(e)}")
            messages.error(request, 'An error occurred. Please try again.')

    context = {
        'amount': amount,
        'upgrade_role': role,
        'current_role': current_role,
        'is_upgrade': True,
        'stripe_publishable_key': django_settings.STRIPE_PUBLISHABLE_KEY,
    }
    return render(request, 'registration_payment.html', context)


@login_required
def update_stripe_account(request):
    """
    Update seller's Stripe Account ID with validation.
    Verifies the account exists and is properly connected.
    """
    if request.method == 'POST':
        stripe_account_id = request.POST.get('stripe_account_id', '').strip()

        if not stripe_account_id:
            messages.error(request, 'Please enter your Stripe Account ID.')
            return redirect('settings')

        # Validate format (should start with acct_)
        if not stripe_account_id.startswith('acct_'):
            messages.error(request, 'Invalid Stripe Account ID format. It should start with "acct_".')
            return redirect('settings')

        try:
            # Verify the account exists and get its details
            account = stripe.Account.retrieve(stripe_account_id)

            # Check account type and status
            account_type = account.get('type', 'unknown')
            charges_enabled = account.get('charges_enabled', False)
            payouts_enabled = account.get('payouts_enabled', False)
            details_submitted = account.get('details_submitted', False)

            # Determine connection status
            if account_type in ['express', 'standard', 'custom']:
                # It's a Connect account
                if details_submitted and charges_enabled:
                    # Fully onboarded and active
                    request.user.stripe_account_id = stripe_account_id
                    request.user.stripe_connect_status = 'active'
                    request.user.stripe_account_verified = True
                    request.user.save()

                    logger.info(
                        f"Stripe Connect account verified for user {request.user.username}: "
                        f"{stripe_account_id} | Type: {account_type} | Charges: {charges_enabled} | Payouts: {payouts_enabled}"
                    )

                    messages.success(
                        request,
                        f'✅ Stripe Connect account verified! '
                        f'Type: {account_type.title()} | Status: Active | '
                        f'You can now receive automatic payouts!'
                    )

                elif details_submitted and not charges_enabled:
                    # Onboarded but restricted
                    request.user.stripe_account_id = stripe_account_id
                    request.user.stripe_connect_status = 'restricted'
                    request.user.stripe_account_verified = False
                    request.user.save()

                    logger.warning(
                        f"Stripe Connect account RESTRICTED for user {request.user.username}: "
                        f"{stripe_account_id} | Charges disabled"
                    )

                    messages.warning(
                        request,
                        f'⚠️ Stripe account connected but RESTRICTED. '
                        f'Charges are disabled. Please check your Stripe dashboard to resolve issues.'
                    )

                else:
                    # Onboarding incomplete
                    request.user.stripe_account_id = stripe_account_id
                    request.user.stripe_connect_status = 'pending'
                    request.user.stripe_account_verified = False
                    request.user.save()

                    logger.warning(
                        f"Stripe Connect account INCOMPLETE for user {request.user.username}: "
                        f"{stripe_account_id} | Details submitted: {details_submitted}"
                    )

                    messages.warning(
                        request,
                        f'⚠️ Stripe account found but onboarding is INCOMPLETE. '
                        f'Please complete your Stripe Connect setup to receive payouts.'
                    )

            else:
                # Unknown or regular account type (not Connect)
                logger.error(
                    f"Invalid Stripe account type for user {request.user.username}: "
                    f"{stripe_account_id} | Type: {account_type}"
                )

                messages.error(
                    request,
                    f'❌ This is not a valid Stripe Connect account! '
                    f'Account type: {account_type}. '
                    f'Please use the "Connect Stripe Account" button to create a proper Connect account.'
                )
                return redirect('settings')

        except stripe.error.PermissionError as e:
            # Account exists but is not connected to this platform
            logger.error(
                f"Stripe permission error for user {request.user.username}: "
                f"Account {stripe_account_id} is NOT connected to platform | Error: {str(e)}"
            )

            messages.error(
                request,
                f'❌ This Stripe account is NOT connected to our platform! '
                f'This is likely your regular Stripe account ID. '
                f'Please use the "Connect Stripe Account" button below to create a proper connected account.'
            )
            return redirect('settings')

        except stripe.error.InvalidRequestError as e:
            # Account doesn't exist
            logger.error(
                f"Stripe account NOT FOUND for user {request.user.username}: "
                f"{stripe_account_id} | Error: {str(e)}"
            )

            messages.error(
                request,
                f'❌ Stripe account not found! '
                f'The account ID "{stripe_account_id}" does not exist. '
                f'Please double-check the ID or use "Connect Stripe Account" to create one.'
            )
            return redirect('settings')

        except stripe.error.StripeError as e:
            # Other Stripe errors
            logger.error(
                f"Stripe error verifying account for user {request.user.username}: "
                f"{stripe_account_id} | Error: {str(e)}"
            )

            messages.error(
                request,
                f'❌ Stripe error: {str(e)}. '
                f'Please try again or contact support.'
            )
            return redirect('settings')

        except Exception as e:
            # Unexpected errors
            logger.error(
                f"Unexpected error verifying Stripe account for user {request.user.username}: "
                f"{stripe_account_id} | Error: {str(e)}"
            )

            messages.error(request, f'An unexpected error occurred. Please try again.')
            return redirect('settings')

        # Redirect based on user type
        if request.user.user_type == 'seller':
            return redirect('seller_dashboard')
        else:
            return redirect('settings')

    return redirect('settings')


@csrf_exempt
def stripe_webhook(request):
    """
    Handle Stripe webhooks for payment verification.
    This is the secure way to verify payments.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    if not sig_header:
        logger.warning("Webhook received without signature")
        return HttpResponse(status=400)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, django_settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        logger.error("Invalid webhook payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        logger.error("Invalid webhook signature")
        return HttpResponse(status=400)

    # Handle checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        # Get user from metadata
        user_id = session['metadata'].get('user_id')

        if not user_id:
            logger.error("Webhook session missing user_id in metadata")
            return HttpResponse(status=400)

        try:
            user = User.objects.get(id=user_id)

            # Activate account if not already activated
            if not user.registration_paid:
                user.account_status = 'active'
                user.registration_paid = True
                user.stripe_payment_intent_id = session.payment_intent
                user.stripe_customer_id = session.customer
                user.registration_paid_at = timezone.now()
                user.registration_amount = session.amount_total / 100
                user.save()

                logger.info(f"Account activated via webhook for user {user.id}")

                # Create notification
                Notification.objects.create(
                    user=user,
                    notification_type='account_update',
                    title='Account Activated',
                    message=f'Your {user.user_type} account has been successfully activated!',
                    link='/'
                )

        except User.DoesNotExist:
            logger.error(f"Webhook: User {user_id} not found")
            return HttpResponse(status=404)
        except Exception as e:
            logger.error(f"Webhook error processing user {user_id}: {str(e)}")
            return HttpResponse(status=500)

    return HttpResponse(status=200)


def contact_us(request):
    """Handle contact us page and form submission"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        # Check if AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        # Validate form data
        if not all([name, email, subject, message]):
            if is_ajax:
                return JsonResponse({'success': False, 'message': 'All fields are required.'})
            messages.error(request, 'All fields are required.')
            context = get_contact_context(request)
            return render(request, 'src/contact_us.html', context)

        if len(message) < 10:
            if is_ajax:
                return JsonResponse({'success': False, 'message': 'Message must be at least 10 characters long.'})
            messages.error(request, 'Message must be at least 10 characters long.')
            context = get_contact_context(request)
            return render(request, 'src/contact_us.html', context)

        # Validate email format
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try:
            validate_email(email)
        except ValidationError:
            if is_ajax:
                return JsonResponse({'success': False, 'message': 'Please enter a valid email address.'})
            messages.error(request, 'Please enter a valid email address.')
            context = get_contact_context(request)
            return render(request, 'src/contact_us.html', context)

        # Send email
        try:
            from django.core.mail import send_mail
            from django.conf import settings

            # Email to admin
            admin_subject = f'Contact Form: {subject}'
            admin_message = f"""
New contact form submission:

From: {name}
Email: {email}
Subject: {subject}

Message:
{message}

---
This message was sent from the Vortex AI contact form.
            """

            send_mail(
                admin_subject,
                admin_message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.CONTACT_EMAIL],  # Admin email
                fail_silently=False,
            )

            # Confirmation email to user
            user_subject = f'We received your message: {subject}'
            user_message = f"""
Hello {name},

Thank you for contacting Vortex AI! We have received your message and will respond within 24-48 hours.

Your message:
{message}

If you have any urgent concerns, please don't hesitate to reach out to us directly at support@vortexai.com.

Best regards,
Vortex AI Support Team

---
This is an automated confirmation email. Please do not reply to this message.
            """

            send_mail(
                user_subject,
                user_message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=True,  # Don't fail if confirmation email doesn't send
            )

            logger.info(f"Contact form submission from {name} ({email}): {subject}")

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': 'Thank you for contacting us! We will respond to your inquiry within 24-48 hours.'
                })

            messages.success(request, 'Thank you for contacting us! We will respond to your inquiry within 24-48 hours.')
            return redirect('contact_us')

        except Exception as e:
            logger.error(f"Error sending contact form email: {str(e)}")

            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': 'There was an error sending your message. Please try again or email us directly at support@vortexai.com.'
                })

            messages.error(request, 'There was an error sending your message. Please try again or email us directly at support@vortexai.com.')
            context = get_contact_context(request)
            return render(request, 'src/contact_us.html', context)

    context = get_contact_context(request)
    return render(request, 'src/contact_us.html', context)


def get_contact_context(request):
    """Helper function to get context for contact page"""
    context = {}

    # Add sidebar context if user is authenticated
    if request.user.is_authenticated:
        if request.user.user_type == 'buyer':
            context['dashboard_url'] = 'buyer_dashboard'
            context['orders_label'] = 'My Orders'
            context['switch_gradient'] = 'from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600'
            context['switch_icon'] = '🏪'
            context['switch_text'] = 'Switch to Seller'
        else:  # seller
            context['dashboard_url'] = 'seller_dashboard'
            context['orders_label'] = 'Sales'
            context['switch_gradient'] = 'from-green-500 to-teal-500 hover:from-green-600 hover:to-teal-600'
            context['switch_icon'] = '🛍️'
            context['switch_text'] = 'Switch to Buyer'

    return context


def privacy_policy(request):
    """Display privacy policy page"""
    context = {}

    # Add sidebar context if user is authenticated
    if request.user.is_authenticated:
        if request.user.user_type == 'buyer':
            context['dashboard_url'] = 'buyer_dashboard'
            context['orders_label'] = 'My Orders'
            context['switch_gradient'] = 'from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600'
            context['switch_icon'] = '🏪'
            context['switch_text'] = 'Switch to Seller'
        else:  # seller
            context['dashboard_url'] = 'seller_dashboard'
            context['orders_label'] = 'Sales'
            context['switch_gradient'] = 'from-green-500 to-teal-500 hover:from-green-600 hover:to-teal-600'
            context['switch_icon'] = '🛍️'
            context['switch_text'] = 'Switch to Buyer'

    return render(request, 'src/privacy_policy.html', context)
