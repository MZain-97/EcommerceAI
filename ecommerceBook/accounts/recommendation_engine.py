"""
Recommendation Engine for E-commerce Platform
Uses Pinecone, user browsing history, search history, and chatbot interactions
"""

from django.db.models import Count, Q, Avg
from django.contrib.contenttypes.models import ContentType
from .models import (
    User, Book, Course, Webinar, UserBrowsingHistory,
    UserSearchHistory, UserPreference, ChatMessage, Order, Rating
)
from .chatbot_helper import search_products, generate_embedding
from collections import Counter
import re


def track_product_view(user, product, product_type):
    """
    Track when a user views a product

    Args:
        user: User instance
        product: Product instance (Book, Course, or Webinar)
        product_type: String ('book', 'course', 'webinar')
    """
    if not user.is_authenticated:
        return

    try:
        content_type = ContentType.objects.get(model=product_type)

        # Check if already viewed recently (within last hour)
        from datetime import timedelta
        from django.utils import timezone
        recent_time = timezone.now() - timedelta(hours=1)

        recent_view = UserBrowsingHistory.objects.filter(
            user=user,
            content_type=content_type,
            object_id=product.id,
            viewed_at__gte=recent_time
        ).exists()

        if not recent_view:
            UserBrowsingHistory.objects.create(
                user=user,
                content_type=content_type,
                object_id=product.id
            )

            # Update user preferences in background
            update_user_preferences(user)
    except Exception as e:
        print(f"Error tracking product view: {e}")


def track_search_query(user, query, results_count=0):
    """
    Track user search queries

    Args:
        user: User instance (can be None for anonymous)
        query: Search query string
        results_count: Number of results found
    """
    try:
        UserSearchHistory.objects.create(
            user=user if user and user.is_authenticated else None,
            query=query,
            results_count=results_count
        )

        if user and user.is_authenticated:
            update_user_preferences(user)
    except Exception as e:
        print(f"Error tracking search: {e}")


def update_user_preferences(user):
    """
    Update user preferences based on browsing and search history

    Args:
        user: User instance
    """
    try:
        preference, created = UserPreference.objects.get_or_create(user=user)

        # Get favorite categories from browsing history (last 30 days)
        from datetime import timedelta
        from django.utils import timezone
        recent_time = timezone.now() - timedelta(days=30)

        # Get all viewed products
        recent_views = UserBrowsingHistory.objects.filter(
            user=user,
            viewed_at__gte=recent_time
        )

        # Count category views
        category_counts = {}
        for view in recent_views:
            product = view.product
            if product and hasattr(product, 'category') and product.category:
                cat_id = product.category.id
                category_counts[cat_id] = category_counts.get(cat_id, 0) + 1

        # Get top 5 categories
        top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        preference.favorite_categories = [cat_id for cat_id, _ in top_categories]

        # Extract keywords from search history
        recent_searches = UserSearchHistory.objects.filter(
            user=user,
            searched_at__gte=recent_time
        ).values_list('query', flat=True)

        # Get keywords from chatbot
        recent_chats = ChatMessage.objects.filter(
            user=user,
            created_at__gte=recent_time
        ).values_list('question', flat=True)

        # Combine and extract keywords
        all_text = ' '.join(list(recent_searches) + list(recent_chats))
        keywords = extract_keywords(all_text)
        preference.interests_keywords = keywords[:20]  # Top 20 keywords

        preference.save()
    except Exception as e:
        print(f"Error updating user preferences: {e}")


def extract_keywords(text):
    """
    Extract meaningful keywords from text

    Args:
        text: String to extract keywords from

    Returns:
        List of keywords
    """
    # Remove common stop words
    stop_words = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
        'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
        'to', 'was', 'will', 'with', 'i', 'me', 'my', 'do', 'can', 'how',
        'what', 'where', 'when', 'why', 'show', 'find', 'looking', 'want'
    }

    # Extract words
    words = re.findall(r'\b[a-z]+\b', text.lower())

    # Filter stop words and short words
    meaningful_words = [w for w in words if w not in stop_words and len(w) > 3]

    # Count occurrences
    word_counts = Counter(meaningful_words)

    # Return most common
    return [word for word, count in word_counts.most_common(20)]


def get_personalized_recommendations(user, limit=10):
    """
    Get personalized product recommendations for a user

    Args:
        user: User instance
        limit: Number of recommendations to return

    Returns:
        List of product dictionaries with type and object
    """
    if not user.is_authenticated:
        return get_trending_products(limit)

    recommendations = []

    try:
        # Strategy 1: Based on browsing history (40% weight)
        browsing_recs = get_recommendations_from_browsing(user, limit=5)
        recommendations.extend(browsing_recs)

        # Strategy 2: Based on search history and chatbot (30% weight)
        search_recs = get_recommendations_from_searches(user, limit=4)
        recommendations.extend(search_recs)

        # Strategy 3: Based on purchases and ratings (20% weight)
        purchase_recs = get_recommendations_from_purchases(user, limit=3)
        recommendations.extend(purchase_recs)

        # Strategy 4: Trending products (10% weight)
        if len(recommendations) < limit:
            trending = get_trending_products(limit - len(recommendations))
            recommendations.extend(trending)

        # Remove duplicates while preserving order
        seen = set()
        unique_recs = []
        for rec in recommendations:
            key = (rec['type'], rec['id'])
            if key not in seen:
                seen.add(key)
                unique_recs.append(rec)

        return unique_recs[:limit]

    except Exception as e:
        print(f"Error generating personalized recommendations: {e}")
        return get_trending_products(limit)


def get_recommendations_from_browsing(user, limit=5):
    """Get recommendations based on user's browsing history"""
    try:
        # Get recently viewed products
        from datetime import timedelta
        from django.utils import timezone
        recent_time = timezone.now() - timedelta(days=30)

        recent_views = UserBrowsingHistory.objects.filter(
            user=user,
            viewed_at__gte=recent_time
        ).order_by('-viewed_at')[:10]

        if not recent_views:
            return []

        # Get categories of viewed products
        categories = []
        for view in recent_views:
            product = view.product
            if product and hasattr(product, 'category') and product.category:
                categories.append(product.category.id)

        if not categories:
            return []

        # Find similar products in same categories
        books = Book.objects.filter(
            category_id__in=categories,
            is_active=True
        ).order_by('-created_at')[:limit]

        courses = Course.objects.filter(
            category_id__in=categories,
            is_active=True
        ).order_by('-created_at')[:limit]

        webinars = Webinar.objects.filter(
            category_id__in=categories,
            is_active=True
        ).order_by('-created_at')[:limit]

        recommendations = []
        for book in books:
            recommendations.append({'type': 'book', 'id': book.id, 'object': book})
        for course in courses:
            recommendations.append({'type': 'course', 'id': course.id, 'object': course})
        for webinar in webinars:
            recommendations.append({'type': 'webinar', 'id': webinar.id, 'object': webinar})

        return recommendations[:limit]

    except Exception as e:
        print(f"Error in browsing recommendations: {e}")
        return []


def get_recommendations_from_searches(user, limit=4):
    """Get recommendations based on search history and chatbot interactions"""
    try:
        from datetime import timedelta
        from django.utils import timezone
        recent_time = timezone.now() - timedelta(days=30)

        # Get recent searches
        searches = UserSearchHistory.objects.filter(
            user=user,
            searched_at__gte=recent_time
        ).values_list('query', flat=True)[:10]

        # Get chatbot questions
        chats = ChatMessage.objects.filter(
            user=user,
            created_at__gte=recent_time
        ).values_list('question', flat=True)[:10]

        # Combine queries
        all_queries = list(searches) + list(chats)

        if not all_queries:
            return []

        # Use Pinecone to find relevant products
        combined_query = ' '.join(all_queries[:5])
        products = search_products(combined_query, n_results=limit)

        recommendations = []
        for product in products:
            recommendations.append({
                'type': product['type'],
                'id': int(product['id']),
                'object': get_product_by_type_and_id(product['type'], int(product['id']))
            })

        return recommendations

    except Exception as e:
        print(f"Error in search recommendations: {e}")
        return []


def get_recommendations_from_purchases(user, limit=3):
    """Get recommendations based on purchase history and ratings"""
    try:
        # Get highly rated products from orders
        high_ratings = Rating.objects.filter(
            user=user,
            rating__gte=4
        ).select_related('order_item')[:5]

        if not high_ratings:
            return []

        # Get categories from highly rated products
        categories = []
        for rating in high_ratings:
            product = rating.order_item.content_object
            if product and hasattr(product, 'category') and product.category:
                categories.append(product.category.id)

        if not categories:
            return []

        # Find products in same categories
        all_products = []

        books = Book.objects.filter(
            category_id__in=categories,
            is_active=True
        )[:limit]
        courses = Course.objects.filter(
            category_id__in=categories,
            is_active=True
        )[:limit]
        webinars = Webinar.objects.filter(
            category_id__in=categories,
            is_active=True
        )[:limit]

        recommendations = []
        for book in books:
            recommendations.append({'type': 'book', 'id': book.id, 'object': book})
        for course in courses:
            recommendations.append({'type': 'course', 'id': course.id, 'object': course})
        for webinar in webinars:
            recommendations.append({'type': 'webinar', 'id': webinar.id, 'object': webinar})

        return recommendations[:limit]

    except Exception as e:
        print(f"Error in purchase recommendations: {e}")
        return []


def get_trending_products(limit=10):
    """Get trending products based on overall popularity"""
    try:
        # Get products with highest ratings
        from django.db.models import Avg, Count

        # Annotate products with rating info
        books = Book.objects.filter(is_active=True).annotate(
            avg_rating=Avg('orderitem__rating__rating'),
            rating_count=Count('orderitem__rating')
        ).order_by('-avg_rating', '-rating_count')[:limit]

        courses = Course.objects.filter(is_active=True).annotate(
            avg_rating=Avg('orderitem__rating__rating'),
            rating_count=Count('orderitem__rating')
        ).order_by('-avg_rating', '-rating_count')[:limit]

        webinars = Webinar.objects.filter(is_active=True).annotate(
            avg_rating=Avg('orderitem__rating__rating'),
            rating_count=Count('orderitem__rating')
        ).order_by('-avg_rating', '-rating_count')[:limit]

        recommendations = []
        for book in books:
            recommendations.append({'type': 'book', 'id': book.id, 'object': book})
        for course in courses:
            recommendations.append({'type': 'course', 'id': course.id, 'object': course})
        for webinar in webinars:
            recommendations.append({'type': 'webinar', 'id': webinar.id, 'object': webinar})

        return recommendations[:limit]

    except Exception as e:
        print(f"Error in trending products: {e}")
        return []


def get_product_by_type_and_id(product_type, product_id):
    """Helper to get product object by type and ID"""
    try:
        if product_type == 'book':
            return Book.objects.get(id=product_id, is_active=True)
        elif product_type == 'course':
            return Course.objects.get(id=product_id, is_active=True)
        elif product_type == 'webinar':
            return Webinar.objects.get(id=product_id, is_active=True)
    except:
        return None


def get_similar_products(product, product_type, limit=5):
    """
    Get products similar to the given product

    Args:
        product: Product instance
        product_type: String ('book', 'course', 'webinar')
        limit: Number of similar products to return

    Returns:
        List of similar products
    """
    try:
        # Use Pinecone to find similar products
        query = f"{product.title} {product.description[:200]}"
        similar = search_products(query, n_results=limit + 1)  # +1 to exclude self

        recommendations = []
        for item in similar:
            # Skip the product itself
            if item['type'] == product_type and int(item['id']) == product.id:
                continue

            product_obj = get_product_by_type_and_id(item['type'], int(item['id']))
            if product_obj:
                recommendations.append({
                    'type': item['type'],
                    'id': int(item['id']),
                    'object': product_obj
                })

        return recommendations[:limit]

    except Exception as e:
        print(f"Error getting similar products: {e}")
        # Fallback to category-based similarity
        if hasattr(product, 'category') and product.category:
            if product_type == 'book':
                similar = Book.objects.filter(
                    category=product.category,
                    is_active=True
                ).exclude(id=product.id)[:limit]
            elif product_type == 'course':
                similar = Course.objects.filter(
                    category=product.category,
                    is_active=True
                ).exclude(id=product.id)[:limit]
            else:
                similar = Webinar.objects.filter(
                    category=product.category,
                    is_active=True
                ).exclude(id=product.id)[:limit]

            return [{'type': product_type, 'id': p.id, 'object': p} for p in similar]

        return []
