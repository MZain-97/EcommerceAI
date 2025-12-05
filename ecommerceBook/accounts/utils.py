from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_verification_email(user_email, verification_code):
    """
    Send verification email with 6-digit code
    """
    subject = 'Password Reset Verification Code'
    
    # Create HTML email content
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Password Reset Verification</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .code-container {{
                background-color: #0d9488;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 8px;
                margin: 20px 0;
            }}
            .verification-code {{
                font-size: 32px;
                font-weight: bold;
                letter-spacing: 8px;
                margin: 10px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                font-size: 12px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Password Reset Verification</h2>
                <p>You requested to reset your password for your account.</p>
            </div>
            
            <div class="code-container">
                <p>Your verification code is:</p>
                <div class="verification-code">{verification_code}</div>
                <p><strong>This code will expire in 15 minutes</strong></p>
            </div>
            
            <p>Please enter this code on the verification page to continue with your password reset.</p>
            
            <p><strong>Important:</strong></p>
            <ul>
                <li>This code is valid for 15 minutes only</li>
                <li>Do not share this code with anyone</li>
                <li>If you didn't request this reset, please ignore this email</li>
            </ul>
            
            <div class="footer">
                <p>This is an automated email. Please do not reply to this message.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Create plain text version
    plain_message = f"""
    Password Reset Verification Code
    
    You requested to reset your password for your account.
    
    Your verification code is: {verification_code}
    
    This code will expire in 15 minutes.
    
    Please enter this code on the verification page to continue with your password reset.
    
    Important:
    - This code is valid for 15 minutes only
    - Do not share this code with anyone
    - If you didn't request this reset, please ignore this email
    
    This is an automated email. Please do not reply to this message.
    """
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def send_test_email(user_email):
    """
    Send a simple test email to verify email configuration
    """
    subject = 'Test Email from Django'
    message = 'This is a test email to verify your email configuration is working properly.'
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Failed to send test email: {e}")
        return False