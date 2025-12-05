from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import PasswordResetToken

User = get_user_model()


class AccountsTestCase(TestCase):
    """
    Test cases for accounts app functionality
    """
    
    def setUp(self):
        self.client = Client()
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'full_name': 'Test User',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'user_type': 'buyer'
        }
    
    def test_user_registration(self):
        """Test user registration functionality"""
        response = self.client.post(reverse('register'), self.user_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful registration
        self.assertTrue(User.objects.filter(email='test@example.com').exists())
    
    def test_user_login(self):
        """Test user login functionality"""
        # Create user first
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            full_name='Test User'
        )
        
        # Test login
        response = self.client.post(reverse('login'), {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after successful login
    
    def test_password_reset_flow(self):
        """Test password reset functionality"""
        # Create user first
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='oldpass123',
            full_name='Test User'
        )
        
        # Test forgot password
        response = self.client.post(reverse('forgot_password'), {
            'email': 'test@example.com'
        })
        self.assertEqual(response.status_code, 302)
        
        # Check token was created
        self.assertTrue(PasswordResetToken.objects.filter(user=user).exists())
    
    def test_invalid_login(self):
        """Test invalid login attempts"""
        response = self.client.post(reverse('login'), {
            'email': 'nonexistent@example.com',
            'password': 'wrongpass'
        })
        self.assertEqual(response.status_code, 200)  # Stay on page with error
