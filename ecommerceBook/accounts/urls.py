from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-password/', views.verify_password, name='verify_password'),
    path('confirm-password/', views.confirm_password, name='confirm_password'),
    path('buyer-dashboard/', views.buyer_dashboard, name='buyer_dashboard'),
    path('seller-dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('add-new-book/', views.add_new_book, name='add_new_book'),
    path('add-new-course/', views.add_new_course, name='add_new_course'),
    path('add-new-webinar/', views.add_new_webinar, name='add_new_webinar'),
    path('add-new-service/', views.add_new_service, name='add_new_service'),
    path('edit-book/<int:book_id>/', views.edit_book, name='edit_book'),
    path('edit-course/<int:course_id>/', views.edit_course, name='edit_course'),
    path('edit-webinar/<int:webinar_id>/', views.edit_webinar, name='edit_webinar'),
    path('edit-service/<int:service_id>/', views.edit_service, name='edit_service'),
    path('delete-book/<int:book_id>/', views.delete_book, name='delete_book'),
    path('delete-course/<int:course_id>/', views.delete_course, name='delete_course'),
    path('delete-webinar/<int:webinar_id>/', views.delete_webinar, name='delete_webinar'),
    path('delete-service/<int:service_id>/', views.delete_service, name='delete_service'),
    path('cart/', views.cart, name='cart'),
    path('add-to-cart/<str:product_type>/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('clear-cart/', views.clear_cart, name='clear_cart'),
    path('settings/', views.settings, name='settings'),
    path('orders/', views.orders, name='orders'),
    path('download-product/<int:order_id>/<int:item_id>/', views.download_product, name='download_product'),
    path('purchase-product/<str:product_type>/<int:product_id>/', views.purchase_product, name='purchase_product'),
    path('purchase-cart/', views.purchase_cart, name='purchase_cart'),
    path('product/<str:product_type>/<int:product_id>/', views.product_detail, name='product_detail'),
    path('seller/product/<str:product_type>/<int:product_id>/', views.seller_product_detail, name='seller_product_detail'),
    path('switch-user-type/', views.switch_user_type, name='switch_user_type'),
    path('ai-support/', views.chatbot, name='chatbot'),
    path('chatbot-message/', views.chatbot_message, name='chatbot_message'),
    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('api/notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('api/notifications/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('rate-product/<int:order_item_id>/', views.rate_product, name='rate_product'),
    path('all-products/<str:product_type>/', views.all_products, name='all_products'),

    # Payment URLs
    path('registration-payment/', views.registration_payment, name='registration_payment'),
    path('role-upgrade-payment/<str:role>/', views.role_upgrade_payment, name='role_upgrade_payment'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('payment-cancelled/', views.payment_cancelled, name='payment_cancelled'),
    path('stripe-webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('update-stripe-account/', views.update_stripe_account, name='update_stripe_account'),
    path('purchase-success/', views.purchase_success_callback, name='purchase_success_callback'),

    # Buyer-Seller Chat URLs
    path('messages/', views.seller_messages_redirect, name='seller_messages'),
    path('api/seller-chat-stats/', views.get_seller_chat_stats, name='get_seller_chat_stats'),
    path('service-chat/<int:service_id>/', views.service_chat_window, name='service_chat'),
    path('api/send-message/<int:chat_id>/', views.send_service_message, name='send_service_message'),
    path('api/get-messages/<int:chat_id>/', views.get_service_messages, name='get_service_messages'),

    # Stripe Connect URLs
    path('stripe-connect/create/', views.create_stripe_connect_account, name='create_stripe_connect_account'),
    path('stripe-connect/return/', views.stripe_connect_return, name='stripe_connect_return'),
    path('stripe-connect/refresh/', views.refresh_stripe_connect_link, name='refresh_stripe_connect_link'),

    # Category AJAX endpoints
    path('api/subcategories/<int:main_category_id>/', views.get_subcategories, name='get_subcategories'),
    path('api/validate-subcategory/', views.validate_subcategory, name='validate_subcategory'),

    # Static Pages
    path('contact-us/', views.contact_us, name='contact_us'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
]