from django.shortcuts import render
from accounts.models import Book, Course, Webinar, Service, OrderItem
from django.contrib.contenttypes.models import ContentType


def home(request):
    """
    Home page view - displays services, books, courses, and webinars
    Shows 8 products per section based on recommendations for logged-in users
    """
    from django.core.cache import cache

    # Get all active products
    all_services = Service.objects.filter(is_active=True).select_related('category', 'seller')
    all_books = Book.objects.filter(is_active=True).select_related('category', 'seller')
    all_courses = Course.objects.filter(is_active=True).select_related('category', 'seller')
    all_webinars = Webinar.objects.filter(is_active=True).select_related('category', 'seller')

    # Get total counts BEFORE slicing
    services_count = all_services.count()
    books_count = all_books.count()
    courses_count = all_courses.count()
    webinars_count = all_webinars.count()

    # For logged-in users, use recommendation engine
    if request.user.is_authenticated:
        # Get cached recommendations or calculate if not cached
        cache_key = f'user_recommendations_{request.user.id}'
        recommendations = cache.get(cache_key)

        if recommendations is None:
            from accounts.recommendation_engine import get_personalized_recommendations
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

        services_list = list(all_services)
        books_list = list(all_books)
        courses_list = list(all_courses)
        webinars_list = list(all_webinars)

        services_list.sort(key=lambda x: sort_by_recommendation(x, 'service'))
        books_list.sort(key=lambda x: sort_by_recommendation(x, 'book'))
        courses_list.sort(key=lambda x: sort_by_recommendation(x, 'course'))
        webinars_list.sort(key=lambda x: sort_by_recommendation(x, 'webinar'))

        # Limit to 8 products per section
        services = services_list[:8]
        books = books_list[:8]
        courses = courses_list[:8]
        webinars = webinars_list[:8]
    else:
        # For non-logged-in users, just show newest 8 products
        services = all_services.order_by('-created_at')[:8]
        books = all_books.order_by('-created_at')[:8]
        courses = all_courses.order_by('-created_at')[:8]
        webinars = all_webinars.order_by('-created_at')[:8]

    # Get purchased service IDs for logged-in users
    purchased_service_ids = []
    if request.user.is_authenticated:
        service_content_type = ContentType.objects.get_for_model(Service)
        purchased_service_ids = OrderItem.objects.filter(
            order__user=request.user,
            content_type=service_content_type
        ).values_list('object_id', flat=True).distinct()

    context = {
        'services': services,
        'books': books,
        'webinars': webinars,
        'courses': courses,
        'purchased_service_ids': list(purchased_service_ids),
        'books_count': books_count,
        'courses_count': courses_count,
        'webinars_count': webinars_count,
        'services_count': services_count,
    }

    return render(request, 'home.html', context)