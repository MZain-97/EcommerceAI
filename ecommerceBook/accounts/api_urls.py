"""
API URL configuration for REST API endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

from .api_views import (
    AuthViewSet, UserViewSet, CategoryViewSet, BookViewSet,
    CourseViewSet, WebinarViewSet, CartViewSet, OrderViewSet,
    RatingViewSet, NotificationViewSet, ChatSessionViewSet,
    UserPreferenceViewSet
)

# API documentation schema
schema_view = get_schema_view(
    openapi.Info(
        title="E-Commerce Book Platform API",
        default_version='v1',
        description="""
        REST API for E-Commerce Book Platform

        ## Features
        - JWT Authentication
        - User management (Buyers & Sellers)
        - Product management (Books, Courses, Webinars)
        - Shopping cart & orders
        - AI-powered chatbot
        - Ratings & reviews
        - Real-time notifications
        - Personalized recommendations

        ## Authentication
        Use JWT tokens for authentication. Obtain tokens via `/api/v1/auth/login/` endpoint.
        Include token in header: `Authorization: Bearer <token>`
        """,
        terms_of_service="https://www.example.com/terms/",
        contact=openapi.Contact(email="support@ecommercebook.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'books', BookViewSet, basename='book')
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'webinars', WebinarViewSet, basename='webinar')
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'ratings', RatingViewSet, basename='rating')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'chat-sessions', ChatSessionViewSet, basename='chat-session')
router.register(r'preferences', UserPreferenceViewSet, basename='preference')

# URL patterns
urlpatterns = [
    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),

    # JWT Authentication
    path('auth/', include([
        path('register/', AuthViewSet.as_view({'post': 'register'}), name='auth-register'),
        path('login/', AuthViewSet.as_view({'post': 'login'}), name='auth-login'),
        path('change-password/', AuthViewSet.as_view({'post': 'change_password'}), name='auth-change-password'),
        path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    ])),

    # Router URLs
    path('', include(router.urls)),
]
