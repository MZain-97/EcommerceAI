"""
Django REST Framework serializers for all models.
Provides JSON serialization/deserialization with validation.
"""
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import (
    User, Category, Book, Course, Webinar, Cart, CartItem,
    Order, OrderItem, Rating, Notification, ChatSession,
    ChatMessage, UserPreference, UserBrowsingHistory, UserSearchHistory
)


# ==============================================================================
# USER & AUTHENTICATION SERIALIZERS
# ==============================================================================

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'full_name', 'user_type',
            'phone_number', 'profile_image', 'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
        extra_kwargs = {
            'email': {'required': True},
            'full_name': {'required': True}
        }


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = [
            'username', 'email', 'full_name', 'user_type',
            'password', 'password2', 'phone_number'
        ]

    def validate(self, attrs):
        """Validate passwords match"""
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                "password": "Password fields didn't match."
            })
        return attrs

    def create(self, validated_data):
        """Create user with hashed password"""
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    username = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        """Authenticate user credentials"""
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = authenticate(
                request=self.context.get('request'),
                username=username,
                password=password
            )

            if not user:
                raise serializers.ValidationError(
                    'Unable to log in with provided credentials.',
                    code='authorization'
                )
        else:
            raise serializers.ValidationError(
                'Must include "username" and "password".',
                code='authorization'
            )

        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change"""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )


# ==============================================================================
# PRODUCT SERIALIZERS
# ==============================================================================

class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model"""
    products_count = serializers.IntegerField(
        source='get_products_count',
        read_only=True
    )

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'is_active', 'products_count', 'created_at']
        read_only_fields = ['id', 'created_at']


class BaseProductSerializer(serializers.ModelSerializer):
    """Base serializer for product models"""
    average_rating = serializers.FloatField(
        source='get_average_rating',
        read_only=True
    )
    ratings_count = serializers.IntegerField(
        source='get_ratings_count',
        read_only=True
    )
    seller_name = serializers.CharField(
        source='seller.full_name',
        read_only=True
    )
    category_name = serializers.CharField(
        source='category.name',
        read_only=True
    )

    class Meta:
        abstract = True
        read_only_fields = [
            'id', 'seller', 'created_at', 'updated_at',
            'is_deleted', 'deleted_at'
        ]


class BookSerializer(BaseProductSerializer):
    """Serializer for Book model"""

    class Meta(BaseProductSerializer.Meta):
        model = Book
        fields = [
            'id', 'title', 'description', 'price', 'category', 'category_name',
            'book_image', 'book_file', 'seller', 'seller_name', 'created_at',
            'updated_at', 'is_active', 'average_rating', 'ratings_count'
        ]


class BookListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for book lists (no file fields)"""
    average_rating = serializers.FloatField(source='get_average_rating', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Book
        fields = [
            'id', 'title', 'description', 'price', 'category_name',
            'book_image', 'is_active', 'average_rating'
        ]


class CourseSerializer(BaseProductSerializer):
    """Serializer for Course model"""

    class Meta(BaseProductSerializer.Meta):
        model = Course
        fields = [
            'id', 'title', 'description', 'price', 'category', 'category_name',
            'course_image', 'course_file', 'duration_hours', 'seller',
            'seller_name', 'created_at', 'updated_at', 'is_active',
            'average_rating', 'ratings_count'
        ]


class CourseListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for course lists"""
    average_rating = serializers.FloatField(source='get_average_rating', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'price', 'category_name',
            'course_image', 'duration_hours', 'is_active', 'average_rating'
        ]


class WebinarSerializer(BaseProductSerializer):
    """Serializer for Webinar model"""

    class Meta(BaseProductSerializer.Meta):
        model = Webinar
        fields = [
            'id', 'title', 'description', 'price', 'category', 'category_name',
            'webinar_image', 'webinar_file', 'scheduled_date', 'seller',
            'seller_name', 'created_at', 'updated_at', 'is_active',
            'average_rating', 'ratings_count'
        ]


class WebinarListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for webinar lists"""
    average_rating = serializers.FloatField(source='get_average_rating', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Webinar
        fields = [
            'id', 'title', 'description', 'price', 'category_name',
            'webinar_image', 'scheduled_date', 'is_active', 'average_rating'
        ]


# ==============================================================================
# CART & ORDER SERIALIZERS
# ==============================================================================

class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for CartItem model"""
    product_title = serializers.CharField(
        source='content_object.title',
        read_only=True
    )
    product_price = serializers.DecimalField(
        source='content_object.price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    total_price = serializers.DecimalField(
        source='get_total_price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = CartItem
        fields = [
            'id', 'content_type', 'object_id', 'product_title',
            'product_price', 'quantity', 'total_price', 'added_at'
        ]
        read_only_fields = ['id', 'added_at']


class CartSerializer(serializers.ModelSerializer):
    """Serializer for Cart model"""
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.DecimalField(
        source='get_total_price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    total_items = serializers.IntegerField(
        source='get_total_items',
        read_only=True
    )

    class Meta:
        model = Cart
        fields = [
            'id', 'user', 'items', 'total_price', 'total_items',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for OrderItem model"""
    product_title = serializers.CharField(
        source='content_object.title',
        read_only=True
    )
    total_price = serializers.DecimalField(
        source='get_total_price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = OrderItem
        fields = [
            'id', 'content_type', 'object_id', 'product_title',
            'quantity', 'price', 'total_price', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order model"""
    items = OrderItemSerializer(many=True, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'user_email', 'order_number', 'status',
            'total_amount', 'items', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'order_number', 'created_at', 'updated_at'
        ]


class OrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for order lists"""
    items_count = serializers.IntegerField(
        source='items.count',
        read_only=True
    )

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'total_amount',
            'items_count', 'created_at'
        ]


# ==============================================================================
# RATING & NOTIFICATION SERIALIZERS
# ==============================================================================

class RatingSerializer(serializers.ModelSerializer):
    """Serializer for Rating model"""
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    product_title = serializers.CharField(
        source='order_item.content_object.title',
        read_only=True
    )

    class Meta:
        model = Rating
        fields = [
            'id', 'user', 'user_name', 'order_item', 'product_title',
            'rating', 'review', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate_rating(self, value):
        """Ensure rating is between 1 and 5"""
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message', 'link',
            'is_read', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# ==============================================================================
# CHATBOT SERIALIZERS
# ==============================================================================

class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for ChatMessage model"""

    class Meta:
        model = ChatMessage
        fields = ['id', 'question', 'answer', 'created_at']
        read_only_fields = ['id', 'answer', 'created_at']


class ChatSessionSerializer(serializers.ModelSerializer):
    """Serializer for ChatSession model"""
    messages = ChatMessageSerializer(many=True, read_only=True)
    messages_count = serializers.IntegerField(
        source='get_messages_count',
        read_only=True
    )

    class Meta:
        model = ChatSession
        fields = [
            'id', 'session_id', 'messages', 'messages_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'session_id', 'created_at', 'updated_at']


# ==============================================================================
# ANALYTICS & PREFERENCES SERIALIZERS
# ==============================================================================

class UserPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for UserPreference model"""

    class Meta:
        model = UserPreference
        fields = [
            'id', 'favorite_categories', 'interests_keywords', 'last_updated'
        ]
        read_only_fields = ['id', 'last_updated']


class UserBrowsingHistorySerializer(serializers.ModelSerializer):
    """Serializer for UserBrowsingHistory model"""
    product_title = serializers.CharField(
        source='product.title',
        read_only=True
    )

    class Meta:
        model = UserBrowsingHistory
        fields = ['id', 'content_type', 'object_id', 'product_title', 'viewed_at']
        read_only_fields = ['id', 'viewed_at']


class UserSearchHistorySerializer(serializers.ModelSerializer):
    """Serializer for UserSearchHistory model"""

    class Meta:
        model = UserSearchHistory
        fields = ['id', 'query', 'results_count', 'searched_at']
        read_only_fields = ['id', 'searched_at']
