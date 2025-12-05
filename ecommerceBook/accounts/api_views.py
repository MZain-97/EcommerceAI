"""
Django REST Framework ViewSets for API endpoints.
Provides CRUD operations with permissions and filtering.
"""
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.core.cache import cache
import logging

from .models import (
    User, Category, Book, Course, Webinar, Cart, CartItem,
    Order, OrderItem, Rating, Notification, ChatSession,
    ChatMessage, UserPreference
)
from .serializers import (
    UserSerializer, UserRegistrationSerializer, UserLoginSerializer,
    ChangePasswordSerializer, CategorySerializer, BookSerializer,
    BookListSerializer, CourseSerializer, CourseListSerializer,
    WebinarSerializer, WebinarListSerializer, CartSerializer,
    CartItemSerializer, OrderSerializer, OrderListSerializer,
    RatingSerializer, NotificationSerializer, ChatSessionSerializer,
    ChatMessageSerializer, UserPreferenceSerializer
)
from .permissions import IsOwnerOrReadOnly, IsSellerOrReadOnly, IsBuyerUser

logger = logging.getLogger(__name__)


# ==============================================================================
# CUSTOM PERMISSIONS
# ==============================================================================

class IsOwner(permissions.BasePermission):
    """Allow access only to owners of the object"""

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsSeller(permissions.BasePermission):
    """Allow access only to sellers"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'seller'


# ==============================================================================
# AUTHENTICATION VIEWSETS
# ==============================================================================

class AuthViewSet(viewsets.GenericViewSet):
    """
    ViewSet for authentication endpoints.
    Provides registration, login, and logout functionality.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['post'], url_path='register')
    def register(self, request):
        """Register a new user"""
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):
        """Login user and return JWT tokens"""
        serializer = UserLoginSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            user = serializer.validated_data['user']

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='change-password',
            permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        """Change user password"""
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user

            # Check old password
            if not user.check_password(serializer.validated_data['old_password']):
                return Response(
                    {'old_password': ['Wrong password.']},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Set new password
            user.set_password(serializer.validated_data['new_password'])
            user.save()

            return Response({'message': 'Password updated successfully'})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User model"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'email', 'full_name']
    ordering_fields = ['date_joined', 'username']

    def get_queryset(self):
        """Users can only see themselves unless admin"""
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


# ==============================================================================
# PRODUCT VIEWSETS
# ==============================================================================

class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for Category model"""
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']

    def get_permissions(self):
        """Only admins can create/update/delete categories"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]


class BookViewSet(viewsets.ModelViewSet):
    """ViewSet for Book model"""
    queryset = Book.objects.filter(is_active=True, is_deleted=False)
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'seller', 'price']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'price', 'title']

    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.action == 'list':
            return BookListSerializer
        return BookSerializer

    def get_queryset(self):
        """Filter by seller for seller's own products"""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated and self.request.user.user_type == 'seller':
            if self.request.query_params.get('my_products'):
                queryset = queryset.filter(seller=self.request.user)
        return queryset

    def perform_create(self, serializer):
        """Set seller as current user"""
        serializer.save(seller=self.request.user)

    def get_permissions(self):
        """Sellers can create, owners can update/delete"""
        if self.action == 'create':
            return [IsSeller()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsOwnerOrReadOnly()]
        return [permissions.AllowAny()]


class CourseViewSet(viewsets.ModelViewSet):
    """ViewSet for Course model"""
    queryset = Course.objects.filter(is_active=True, is_deleted=False)
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'seller', 'price']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'price', 'title']

    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        return CourseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_authenticated and self.request.user.user_type == 'seller':
            if self.request.query_params.get('my_products'):
                queryset = queryset.filter(seller=self.request.user)
        return queryset

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    def get_permissions(self):
        if self.action == 'create':
            return [IsSeller()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsOwnerOrReadOnly()]
        return [permissions.AllowAny()]


class WebinarViewSet(viewsets.ModelViewSet):
    """ViewSet for Webinar model"""
    queryset = Webinar.objects.filter(is_active=True, is_deleted=False)
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'seller', 'price']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'price', 'title', 'scheduled_date']

    def get_serializer_class(self):
        if self.action == 'list':
            return WebinarListSerializer
        return WebinarSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_authenticated and self.request.user.user_type == 'seller':
            if self.request.query_params.get('my_products'):
                queryset = queryset.filter(seller=self.request.user)
        return queryset

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    def get_permissions(self):
        if self.action == 'create':
            return [IsSeller()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsOwnerOrReadOnly()]
        return [permissions.AllowAny()]


# ==============================================================================
# CART & ORDER VIEWSETS
# ==============================================================================

class CartViewSet(viewsets.ModelViewSet):
    """ViewSet for Cart model"""
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated, IsBuyerUser]

    def get_queryset(self):
        """Users can only see their own cart"""
        return Cart.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'], url_path='my-cart')
    def my_cart(self, request):
        """Get current user's cart"""
        cart, created = Cart.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='add-item')
    def add_item(self, request):
        """Add item to cart"""
        cart, created = Cart.objects.get_or_create(user=request.user)

        product_type = request.data.get('product_type')
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)

        # Get content type
        model_map = {
            'book': Book,
            'course': Course,
            'webinar': Webinar
        }

        if product_type not in model_map:
            return Response(
                {'error': 'Invalid product type'},
                status=status.HTTP_400_BAD_REQUEST
            )

        content_type = ContentType.objects.get_for_model(model_map[product_type])

        # Add or update cart item
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            content_type=content_type,
            object_id=product_id,
            defaults={'quantity': quantity}
        )

        if not created:
            cart_item.quantity += int(quantity)
            cart_item.save()

        serializer = CartSerializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='remove-item')
    def remove_item(self, request):
        """Remove item from cart"""
        item_id = request.data.get('item_id')
        try:
            cart = Cart.objects.get(user=request.user)
            cart_item = CartItem.objects.get(id=item_id, cart=cart)
            cart_item.delete()

            serializer = CartSerializer(cart)
            return Response(serializer.data)
        except (Cart.DoesNotExist, CartItem.DoesNotExist):
            return Response(
                {'error': 'Item not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['post'], url_path='clear')
    def clear_cart(self, request):
        """Clear all items from cart"""
        cart = get_object_or_404(Cart, user=request.user)
        cart.clear()
        serializer = CartSerializer(cart)
        return Response(serializer.data)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Order model (read-only)"""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['created_at', 'total_amount']

    def get_serializer_class(self):
        if self.action == 'list':
            return OrderListSerializer
        return OrderSerializer

    def get_queryset(self):
        """Users can only see their own orders"""
        return Order.objects.filter(user=self.request.user)

    @action(detail=True, methods=['get'], url_path='download/(?P<item_id>[^/.]+)')
    def download_item(self, request, pk=None, item_id=None):
        """Get download link for purchased product"""
        order = self.get_object()
        order_item = get_object_or_404(OrderItem, id=item_id, order=order)

        # Return file URL
        product = order_item.content_object
        file_field = None

        if isinstance(product, Book):
            file_field = product.book_file
        elif isinstance(product, Course):
            file_field = product.course_file
        elif isinstance(product, Webinar):
            file_field = product.webinar_file

        if file_field:
            return Response({'download_url': file_field.url})

        return Response(
            {'error': 'File not available'},
            status=status.HTTP_404_NOT_FOUND
        )


# ==============================================================================
# RATING & NOTIFICATION VIEWSETS
# ==============================================================================

class RatingViewSet(viewsets.ModelViewSet):
    """ViewSet for Rating model"""
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['rating']
    ordering_fields = ['created_at', 'rating']

    def get_queryset(self):
        """Users can see their own ratings or ratings for their products"""
        user = self.request.user
        if user.user_type == 'seller':
            # Sellers see ratings for their products
            return Rating.objects.filter(
                order_item__content_object__seller=user
            )
        else:
            # Buyers see their own ratings
            return Rating.objects.filter(user=user)

    def perform_create(self, serializer):
        """Set user as current user"""
        serializer.save(user=self.request.user)


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for Notification model"""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_read', 'notification_type']
    ordering_fields = ['created_at']

    def get_queryset(self):
        """Users can only see their own notifications"""
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        updated = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)

        return Response({'marked_read': updated})

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """Mark single notification as read"""
        notification = self.get_object()
        notification.mark_as_read()
        serializer = self.get_serializer(notification)
        return Response(serializer.data)


# ==============================================================================
# CHATBOT VIEWSETS
# ==============================================================================

class ChatSessionViewSet(viewsets.ModelViewSet):
    """ViewSet for ChatSession model"""
    serializer_class = ChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Users can only see their own chat sessions"""
        return ChatSession.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='send-message')
    def send_message(self, request, pk=None):
        """Send message to chatbot"""
        from .chatbot_helper import search_products, generate_chat_response, get_fallback_response

        session = self.get_object()
        question = request.data.get('question')

        if not question:
            return Response(
                {'error': 'Question is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Search for relevant products
        products = search_products(question, n_results=5)

        # Generate AI response
        response_stream = generate_chat_response(question, products)

        if response_stream:
            # Collect streaming response
            answer = ""
            try:
                for chunk in response_stream:
                    if chunk.choices[0].delta.content:
                        answer += chunk.choices[0].delta.content
            except Exception as e:
                logger.error(f"Error streaming response: {e}")
                answer = get_fallback_response(question)
        else:
            answer = get_fallback_response(question)

        # Save message
        message = ChatMessage.objects.create(
            session=session,
            user=request.user,
            question=question,
            answer=answer
        )

        serializer = ChatMessageSerializer(message)
        return Response(serializer.data)


# ==============================================================================
# ANALYTICS VIEWSETS
# ==============================================================================

class UserPreferenceViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for UserPreference model (read-only)"""
    serializer_class = UserPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Users can only see their own preferences"""
        return UserPreference.objects.filter(user=self.request.user)
