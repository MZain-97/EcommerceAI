"""
Factory classes for creating test data.
Uses factory_boy for efficient test data generation.
"""
import factory
from factory.django import DjangoModelFactory
from faker import Faker
from decimal import Decimal

from .models import (
    User, Category, Book, Course, Webinar, Cart, CartItem,
    Order, OrderItem, Rating, Notification, ChatSession,
    ChatMessage, UserPreference
)

fake = Faker()


class UserFactory(DjangoModelFactory):
    """Factory for User model"""

    class Meta:
        model = User
        django_get_or_create = ('username',)

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    full_name = factory.Faker('name')
    user_type = 'buyer'
    phone_number = factory.Faker('phone_number')
    is_active = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.set_password(extracted)
        else:
            self.set_password('testpass123')


class BuyerFactory(UserFactory):
    """Factory for buyer users"""
    user_type = 'buyer'


class SellerFactory(UserFactory):
    """Factory for seller users"""
    user_type = 'seller'


class CategoryFactory(DjangoModelFactory):
    """Factory for Category model"""

    class Meta:
        model = Category
        django_get_or_create = ('name',)

    name = factory.Sequence(lambda n: f'Category {n}')
    description = factory.Faker('paragraph')
    is_active = True


class BookFactory(DjangoModelFactory):
    """Factory for Book model"""

    class Meta:
        model = Book

    title = factory.Faker('sentence', nb_words=4)
    description = factory.Faker('paragraph')
    price = factory.LazyFunction(lambda: Decimal(str(fake.random.uniform(9.99, 99.99))))
    category = factory.SubFactory(CategoryFactory)
    seller = factory.SubFactory(SellerFactory)
    is_active = True
    is_deleted = False


class CourseFactory(DjangoModelFactory):
    """Factory for Course model"""

    class Meta:
        model = Course

    title = factory.Faker('sentence', nb_words=4)
    description = factory.Faker('paragraph')
    price = factory.LazyFunction(lambda: Decimal(str(fake.random.uniform(49.99, 299.99))))
    category = factory.SubFactory(CategoryFactory)
    seller = factory.SubFactory(SellerFactory)
    duration_hours = factory.Faker('random_int', min=10, max=100)
    is_active = True
    is_deleted = False


class WebinarFactory(DjangoModelFactory):
    """Factory for Webinar model"""

    class Meta:
        model = Webinar

    title = factory.Faker('sentence', nb_words=4)
    description = factory.Faker('paragraph')
    price = factory.LazyFunction(lambda: Decimal(str(fake.random.uniform(19.99, 99.99))))
    category = factory.SubFactory(CategoryFactory)
    seller = factory.SubFactory(SellerFactory)
    scheduled_date = factory.Faker('future_datetime')
    is_active = True
    is_deleted = False


class CartFactory(DjangoModelFactory):
    """Factory for Cart model"""

    class Meta:
        model = Cart

    user = factory.SubFactory(BuyerFactory)


class OrderFactory(DjangoModelFactory):
    """Factory for Order model"""

    class Meta:
        model = Order

    user = factory.SubFactory(BuyerFactory)
    order_number = factory.Sequence(lambda n: f'ORD{100000 + n}')
    status = 'completed'
    total_amount = factory.LazyFunction(lambda: Decimal(str(fake.random.uniform(10.00, 500.00))))


class RatingFactory(DjangoModelFactory):
    """Factory for Rating model"""

    class Meta:
        model = Rating

    user = factory.SubFactory(BuyerFactory)
    rating = factory.Faker('random_int', min=1, max=5)
    review = factory.Faker('paragraph')


class NotificationFactory(DjangoModelFactory):
    """Factory for Notification model"""

    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory)
    notification_type = 'general'
    title = factory.Faker('sentence', nb_words=5)
    message = factory.Faker('paragraph')
    is_read = False


class ChatSessionFactory(DjangoModelFactory):
    """Factory for ChatSession model"""

    class Meta:
        model = ChatSession

    user = factory.SubFactory(BuyerFactory)
    session_id = factory.Sequence(lambda n: f'session_{n}')


class ChatMessageFactory(DjangoModelFactory):
    """Factory for ChatMessage model"""

    class Meta:
        model = ChatMessage

    session = factory.SubFactory(ChatSessionFactory)
    user = factory.SelfAttribute('session.user')
    question = factory.Faker('sentence')
    answer = factory.Faker('paragraph')


class UserPreferenceFactory(DjangoModelFactory):
    """Factory for UserPreference model"""

    class Meta:
        model = UserPreference

    user = factory.SubFactory(BuyerFactory)
    favorite_categories = factory.LazyFunction(lambda: [1, 2, 3])
    interests_keywords = factory.LazyFunction(lambda: ['python', 'django', 'web'])
