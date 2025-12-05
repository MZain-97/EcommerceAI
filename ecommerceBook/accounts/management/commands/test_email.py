from django.core.management.base import BaseCommand
from accounts.utils import send_test_email, send_verification_email


class Command(BaseCommand):
    help = 'Test email functionality'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email address to send test email to')
        parser.add_argument(
            '--verification',
            action='store_true',
            help='Send verification email instead of test email',
        )
        parser.add_argument(
            '--code',
            type=str,
            default='123456',
            help='Verification code to send (default: 123456)',
        )

    def handle(self, *args, **options):
        email = options['email']
        
        self.stdout.write(f'Testing email functionality for: {email}')
        self.stdout.write('-' * 50)
        
        if options['verification']:
            code = options['code']
            self.stdout.write(f'Sending verification email with code: {code}')
            success = send_verification_email(email, code)
        else:
            self.stdout.write('Sending test email...')
            success = send_test_email(email)
        
        if success:
            self.stdout.write(
                self.style.SUCCESS(f'Email sent successfully to {email}')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'Failed to send email to {email}')
            )