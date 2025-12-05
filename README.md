# E-Commerce Book Platform

A comprehensive Django-based e-commerce platform for selling digital products including books, courses, and webinars. The platform features an AI-powered chatbot for customer support, recommendation engine, user authentication, cart management, and order processing.

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Database Setup](#database-setup)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Project Structure](#project-structure)
- [Key Features Explained](#key-features-explained)
- [API Endpoints](#api-endpoints)
- [Usage Guide](#usage-guide)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

### Core Features
- **Dual User Roles**: Separate dashboards for buyers and sellers
- **Digital Product Management**: Upload and manage books, courses, and webinars
- **Shopping Cart**: Add multiple items and checkout
- **Order Management**: Complete order history and tracking
- **Product Ratings**: 5-star rating system for purchased products
- **User Authentication**: Registration, login, logout, and password reset with email verification
- **Profile Management**: Update user information and profile images

### Advanced Features
- **AI Chatbot**: Powered by OpenAI and Pinecone for intelligent product recommendations
- **Recommendation Engine**: Personalized product suggestions based on user behavior
- **Browsing History**: Track user interactions for better recommendations
- **Search History**: Save and analyze user search patterns
- **Real-time Notifications**: Alert users about orders, purchases, and account updates
- **Category Management**: Organize products by categories
- **Media Upload**: Support for images and file uploads
- **Email Integration**: Automated email notifications via SMTP

## Tech Stack

### Backend
- **Framework**: Django 4.2.23
- **Database**: PostgreSQL
- **Database Adapter**: psycopg2-binary

### AI & Machine Learning
- **Vector Database**: Pinecone (for product embeddings)
- **AI Model**: OpenAI GPT (for chatbot)
- **Embeddings**: sentence-transformers (2.2.2)
- **Deep Learning**: PyTorch (2.1.2)
- **NLP**: transformers (4.36.2), langchain (0.1.0)
- **Vector Store**: ChromaDB (0.4.22)

### Frontend
- HTML/CSS/JavaScript
- Templates with Django Template Engine

### Media Handling
- Pillow (for image processing)

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.8+** - [Download Python](https://www.python.org/downloads/)
- **PostgreSQL 12+** - [Download PostgreSQL](https://www.postgresql.org/download/)
- **pip** - Python package installer (comes with Python)
- **Git** - [Download Git](https://git-scm.com/downloads)
- **Virtual Environment** (recommended)

### API Keys Required
- **OpenAI API Key** - [Get API Key](https://platform.openai.com/api-keys)
- **Pinecone API Key** - [Get API Key](https://www.pinecone.io/)
- **Gmail App Password** (for email functionality) - [Generate App Password](https://support.google.com/accounts/answer/185833)

## Installation

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd django
```

### 2. Create Virtual Environment

**Windows:**
```bash
python -m venv env
env\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv env
source env/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

The following packages will be installed:
- Django
- psycopg2 & psycopg2-binary (PostgreSQL adapter)
- Pillow (image processing)
- chromadb (vector database)
- sentence-transformers (text embeddings)
- transformers (NLP models)
- torch (deep learning)
- langchain (LLM framework)
- huggingface-hub (model repository)

## Database Setup

### 1. Create PostgreSQL Database

Open PostgreSQL command line or pgAdmin and create a new database:

```sql
CREATE DATABASE EcomerceDB;
CREATE USER postgres WITH PASSWORD '123456';
GRANT ALL PRIVILEGES ON DATABASE EcomerceDB TO postgres;
```

### 2. Update Database Credentials

Open `ecommerceBook/ecommerceBook/settings.py` and verify/update the database configuration:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'EcomerceDB',
        'USER': 'postgres',
        'PASSWORD': '123456',  # Change this to your PostgreSQL password
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 3. Run Migrations

```bash
cd ecommerceBook
python manage.py makemigrations
python manage.py migrate
```

### 4. Create Superuser (Admin)

```bash
python manage.py createsuperuser
```

Follow the prompts to create an admin account.

## Configuration

### 1. Email Configuration

Update email settings in `ecommerceBook/ecommerceBook/settings.py`:

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'  # Replace with your Gmail
EMAIL_HOST_PASSWORD = 'your-app-password'  # Replace with Gmail app password
```

To generate a Gmail app password:
1. Go to your Google Account settings
2. Security → 2-Step Verification
3. App passwords → Generate new password

### 2. OpenAI Configuration

Uncomment and add your OpenAI API key in `settings.py`:

```python
OPENAI_API_KEY = 'your-openai-api-key'
```

### 3. Pinecone Configuration

Uncomment and add your Pinecone API key in `settings.py`:

```python
PINECONE_API_KEY = 'your-pinecone-api-key'
PINECONE_ENVIRONMENT = 'us-east-1'  # Your Pinecone environment
PINECONE_INDEX_NAME = 'ecommerce-products'
```

### 4. Security Settings

For production deployment, update these settings:

```python
DEBUG = False  # Set to False in production
SECRET_KEY = 'your-secret-key'  # Generate a new secret key
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
```

## Running the Application

### 1. Collect Static Files

```bash
python manage.py collectstatic
```

### 2. Start Development Server

```bash
python manage.py runserver
```

The application will be available at: `http://127.0.0.1:8000/`

### 3. Access Admin Panel

Navigate to `http://127.0.0.1:8000/admin/` and login with your superuser credentials.

## Project Structure

```
django/
├── ecommerceBook/              # Main project directory
│   ├── accounts/               # Main application
│   │   ├── migrations/         # Database migrations
│   │   ├── management/         # Custom management commands
│   │   ├── models.py           # Database models
│   │   ├── views.py            # View functions
│   │   ├── forms.py            # Django forms
│   │   ├── urls.py             # URL routing
│   │   ├── admin.py            # Admin configuration
│   │   ├── chatbot_helper.py   # AI chatbot functionality
│   │   ├── recommendation_engine.py  # Product recommendations
│   │   └── utils.py            # Utility functions
│   ├── ecommerceBook/          # Project settings
│   │   ├── settings.py         # Django settings
│   │   ├── urls.py             # Main URL configuration
│   │   ├── wsgi.py             # WSGI configuration
│   │   └── views.py            # Base views
│   ├── templates/              # HTML templates
│   │   ├── home.html           # Homepage
│   │   ├── cart.html           # Shopping cart
│   │   ├── sidebar.html        # Navigation sidebar
│   │   └── src/                # Additional templates
│   ├── static/                 # Static files (CSS, JS, images)
│   ├── media/                  # User uploaded files
│   │   ├── profile_images/     # User profile pictures
│   │   ├── book_images/        # Book cover images
│   │   ├── book_files/         # Book PDF/files
│   │   ├── course_images/      # Course thumbnails
│   │   ├── course_files/       # Course content files
│   │   ├── webinar_images/     # Webinar banners
│   │   └── webinar_files/      # Webinar recordings
│   ├── manage.py               # Django management script
│   └── test_chatbot.py         # Chatbot testing script
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git ignore rules
└── README.md                   # This file
```

## Key Features Explained

### 1. User Management

**Models**: `User`, `PasswordResetToken`

- Custom user model with buyer/seller roles
- Email-based password reset with 6-digit tokens (15-minute expiry)
- Profile image support
- User type switching capability

### 2. Product Management

**Models**: `Book`, `Course`, `Webinar`, `Category`

- Three types of digital products
- Category-based organization
- Image and file upload for each product
- Average rating calculation
- Active/inactive status for visibility control

### 3. Shopping Cart & Orders

**Models**: `Cart`, `CartItem`, `Order`, `OrderItem`

- Generic foreign keys for flexible product types
- Automatic order number generation
- Price stored at time of purchase
- Order status tracking (pending, completed, cancelled)

### 4. AI Chatbot

**Features**:
- Pinecone vector database for product embeddings
- OpenAI GPT for natural language responses
- Product search based on natural language queries
- Session-based chat history

**Files**: `chatbot_helper.py`, `test_chatbot.py`

### 5. Recommendation Engine

**Models**: `UserBrowsingHistory`, `UserSearchHistory`, `UserPreference`

**Features**:
- Tracks user browsing patterns
- Analyzes search history
- Stores user preferences (categories, keywords)
- Generates personalized product recommendations

**File**: `recommendation_engine.py`

### 6. Rating System

**Model**: `Rating`

- 1-5 star ratings
- One rating per user per product
- Average rating calculation for products
- Only available for purchased items

### 7. Notifications

**Model**: `Notification`

**Notification Types**:
- Order created/completed
- New sale for sellers
- Product purchased
- Cart reminders
- Price changes
- Account updates

## API Endpoints

### Authentication
- `GET/POST /register/` - User registration
- `GET/POST /login/` - User login
- `GET /logout/` - User logout
- `POST /forgot-password/` - Request password reset
- `POST /verify-password/` - Verify reset token
- `POST /confirm-password/` - Set new password

### Dashboard
- `GET /buyer-dashboard/` - Buyer main dashboard
- `GET /seller-dashboard/` - Seller main dashboard
- `POST /switch-user-type/` - Switch between buyer/seller

### Product Management (Seller)
- `GET/POST /add-new-book/` - Add new book
- `GET/POST /add-new-course/` - Add new course
- `GET/POST /add-new-webinar/` - Add new webinar
- `GET/POST /edit-book/<book_id>/` - Edit book
- `GET/POST /edit-course/<course_id>/` - Edit course
- `GET/POST /edit-webinar/<webinar_id>/` - Edit webinar
- `POST /delete-book/<book_id>/` - Delete book
- `POST /delete-course/<course_id>/` - Delete course
- `POST /delete-webinar/<webinar_id>/` - Delete webinar

### Shopping (Buyer)
- `GET /cart/` - View shopping cart
- `POST /add-to-cart/<product_type>/<product_id>/` - Add item to cart
- `POST /remove-from-cart/<item_id>/` - Remove item from cart
- `POST /purchase-cart/` - Checkout cart
- `POST /purchase-product/<product_type>/<product_id>/` - Direct purchase

### Products
- `GET /product/<product_type>/<product_id>/` - Product details (buyer view)
- `GET /seller/product/<product_type>/<product_id>/` - Product details (seller view)
- `GET /all-products/<product_type>/` - List all products of type

### Orders
- `GET /orders/` - View order history
- `GET /download-product/<order_id>/<item_id>/` - Download purchased product

### Settings & Profile
- `GET/POST /settings/` - User profile settings

### Ratings
- `POST /rate-product/<order_item_id>/` - Submit product rating

### AI Chatbot
- `GET /ai-support/` - Chatbot interface
- `POST /chatbot-message/` - Send message to chatbot

### Notifications
- `GET /api/notifications/` - Get user notifications
- `POST /api/notifications/mark-read/` - Mark all as read
- `POST /api/notifications/<notification_id>/mark-read/` - Mark single as read

## Usage Guide

### For Buyers

1. **Register/Login**: Create an account or login
2. **Browse Products**: View available books, courses, and webinars
3. **Add to Cart**: Select products and add them to your cart
4. **Checkout**: Purchase cart items or buy products directly
5. **Download**: Access purchased products from Orders page
6. **Rate Products**: Give ratings to purchased items
7. **AI Assistant**: Use chatbot for product recommendations

### For Sellers

1. **Switch to Seller**: Use the switch user type option
2. **Add Products**: Upload books, courses, or webinars
3. **Manage Inventory**: Edit or delete your products
4. **Track Sales**: View sales and order notifications
5. **Monitor Performance**: Check product ratings and feedback

### Admin Panel Features

Access at `/admin/`:
- Manage all users, products, orders
- View and moderate ratings
- Manage categories
- Monitor notifications
- View chat sessions and messages

## Testing

### Test the Chatbot Integration

Run the chatbot test script:

```bash
cd ecommerceBook
python test_chatbot.py
```

This will test:
1. Pinecone index connection
2. Product indexing
3. Product search functionality
4. OpenAI chat response generation

### Run Django Tests

```bash
python manage.py test accounts
```

## Troubleshooting

### Database Connection Error

**Problem**: `connection to server at "localhost" (127.0.0.1), port 5432 failed`

**Solution**:
- Ensure PostgreSQL is running
- Verify database credentials in `settings.py`
- Check if database exists: `psql -U postgres -l`

### Import Error for psycopg2

**Problem**: `Error loading psycopg2 module`

**Solution**:
```bash
pip uninstall psycopg2 psycopg2-binary
pip install psycopg2-binary
```

### Static Files Not Loading

**Problem**: CSS/JS files not appearing

**Solution**:
```bash
python manage.py collectstatic --clear
python manage.py collectstatic
```

### Email Not Sending

**Problem**: Password reset emails not being delivered

**Solution**:
- Verify Gmail app password is correct
- Check EMAIL_USE_TLS is True
- Ensure 2-factor authentication is enabled on Gmail
- Use console backend for development:
  ```python
  EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
  ```

### Chatbot Not Working

**Problem**: AI chatbot returns errors

**Solution**:
- Verify OpenAI API key is valid and has credits
- Check Pinecone API key and index name
- Run `python test_chatbot.py` to diagnose issues
- Ensure required packages are installed:
  ```bash
  pip install sentence-transformers transformers torch langchain chromadb
  ```

### Port Already in Use

**Problem**: `Error: That port is already in use`

**Solution**:
```bash
# Use a different port
python manage.py runserver 8080

# Or find and kill the process using port 8000
# Windows:
netstat -ano | findstr :8000
taskkill /PID <process_id> /F

# macOS/Linux:
lsof -ti:8000 | xargs kill -9
```

### Migration Errors

**Problem**: Migration conflicts or errors

**Solution**:
```bash
# Reset migrations (development only - will lose data)
python manage.py migrate accounts zero
python manage.py showmigrations
python manage.py makemigrations
python manage.py migrate
```

### Media Files Not Accessible

**Problem**: Uploaded images/files not displaying

**Solution**:
- Ensure MEDIA_URL and MEDIA_ROOT are configured in settings.py
- Verify URLs are configured for development in main urls.py
- Check folder permissions for media directory

## Development Tips

### Create Sample Data

Use Django shell to create test data:

```bash
python manage.py shell
```

```python
from accounts.models import User, Category, Book
from decimal import Decimal

# Create a seller
seller = User.objects.create_user(
    username='seller1',
    email='seller@example.com',
    password='password123',
    user_type='seller',
    full_name='John Seller'
)

# Create a category
category = Category.objects.create(name='Programming')

# Create a book
book = Book.objects.create(
    title='Learn Python',
    description='Comprehensive Python guide',
    price=Decimal('29.99'),
    category=category,
    seller=seller
)
```

### Enable Debug Toolbar

For development, install Django Debug Toolbar:

```bash
pip install django-debug-toolbar
```

Add to `INSTALLED_APPS` in settings.py:
```python
INSTALLED_APPS += ['debug_toolbar']
```

### Database Backup

Backup your database:

```bash
# Windows
pg_dump -U postgres -d EcomerceDB > backup.sql

# Restore
psql -U postgres -d EcomerceDB < backup.sql
```

## Security Considerations

Before deploying to production:

1. **Change Secret Key**: Generate a new Django secret key
2. **Disable Debug**: Set `DEBUG = False`
3. **Configure ALLOWED_HOSTS**: Add your domain
4. **Use Environment Variables**: Store sensitive data in .env file
5. **Enable HTTPS**: Use SSL certificates
6. **Secure Database**: Use strong passwords
7. **Hide API Keys**: Never commit API keys to version control
8. **Regular Updates**: Keep dependencies updated

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -m 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## Support

For issues and questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review Django documentation: https://docs.djangoproject.com/
- Check Pinecone docs: https://docs.pinecone.io/
- Review OpenAI docs: https://platform.openai.com/docs/

## Acknowledgments

- Django Framework
- OpenAI for GPT models
- Pinecone for vector database
- PostgreSQL database
- All open-source contributors

---

**Version**: 1.0.0
**Last Updated**: October 2024
