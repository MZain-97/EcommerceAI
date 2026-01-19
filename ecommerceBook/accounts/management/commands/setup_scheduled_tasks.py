"""
Management command to set up all scheduled Celery Beat tasks.
Run this command once to create all the periodic tasks in the database.

Usage: python manage.py setup_scheduled_tasks
"""
from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
import json


class Command(BaseCommand):
    help = 'Set up all scheduled Celery Beat tasks for the ecommerce platform'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Setting up scheduled tasks...'))

        # Track statistics
        created = 0
        updated = 0
        skipped = 0

        # ==================================================================
        # 1. DAILY SALES REPORT - Every day at 9:00 AM
        # ==================================================================
        crontab_9am, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='9',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        task, created_flag = PeriodicTask.objects.get_or_create(
            name='Daily Sales Report - 9:00 AM',
            defaults={
                'task': 'accounts.tasks.daily_sales_report',
                'crontab': crontab_9am,
                'enabled': True,
                'description': 'Generate and email daily sales report to admin'
            }
        )
        if created_flag:
            created += 1
            self.stdout.write(self.style.SUCCESS('[OK] Created: Daily Sales Report'))
        else:
            task.task = 'accounts.tasks.daily_sales_report'
            task.crontab = crontab_9am
            task.enabled = True
            task.save()
            updated += 1
            self.stdout.write(self.style.SUCCESS('[OK] Updated: Daily Sales Report'))

        # ==================================================================
        # 2. CLEANUP EXPIRED PASSWORD TOKENS - Every day at 2:00 AM
        # ==================================================================
        crontab_2am, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='2',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        task, created_flag = PeriodicTask.objects.get_or_create(
            name='Cleanup Expired Password Tokens - 2:00 AM',
            defaults={
                'task': 'accounts.tasks.clean_expired_password_tokens',
                'crontab': crontab_2am,
                'enabled': True,
                'description': 'Delete expired password reset tokens'
            }
        )
        if created_flag:
            created += 1
            self.stdout.write(self.style.SUCCESS('[OK] Created: Cleanup Expired Tokens'))
        else:
            task.task = 'accounts.tasks.clean_expired_password_tokens'
            task.crontab = crontab_2am
            task.enabled = True
            task.save()
            updated += 1
            self.stdout.write(self.style.SUCCESS('[OK] Updated: Cleanup Expired Tokens'))

        # ==================================================================
        # 3. UPDATE AI RECOMMENDATIONS - Every day at 3:00 AM
        # ==================================================================
        crontab_3am, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='3',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        task, created_flag = PeriodicTask.objects.get_or_create(
            name='Update AI Recommendations - 3:00 AM',
            defaults={
                'task': 'accounts.tasks.update_ai_recommendations',
                'crontab': crontab_3am,
                'enabled': True,
                'description': 'Update user preferences and product recommendations'
            }
        )
        if created_flag:
            created += 1
            self.stdout.write(self.style.SUCCESS('[OK] Created: Update AI Recommendations'))
        else:
            task.task = 'accounts.tasks.update_ai_recommendations'
            task.crontab = crontab_3am
            task.enabled = True
            task.save()
            updated += 1
            self.stdout.write(self.style.SUCCESS('[OK] Updated: Update AI Recommendations'))

        # ==================================================================
        # 4. DATABASE BACKUP - Every day at 1:00 AM
        # ==================================================================
        crontab_1am, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='1',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        task, created_flag = PeriodicTask.objects.get_or_create(
            name='Database Backup - 1:00 AM',
            defaults={
                'task': 'accounts.tasks.database_backup',
                'crontab': crontab_1am,
                'enabled': True,
                'description': 'Create automated PostgreSQL database backup'
            }
        )
        if created_flag:
            created += 1
            self.stdout.write(self.style.SUCCESS('[OK] Created: Database Backup'))
        else:
            task.task = 'accounts.tasks.database_backup'
            task.crontab = crontab_1am
            task.enabled = True
            task.save()
            updated += 1
            self.stdout.write(self.style.SUCCESS('[OK] Updated: Database Backup'))

        # ==================================================================
        # 5. SYNC STRIPE PAYMENTS - Every 30 minutes
        # ==================================================================
        interval_30min, _ = IntervalSchedule.objects.get_or_create(
            every=30,
            period=IntervalSchedule.MINUTES,
        )

        task, created_flag = PeriodicTask.objects.get_or_create(
            name='Sync Stripe Payments - Every 30 Minutes',
            defaults={
                'task': 'accounts.tasks.sync_stripe_payments',
                'interval': interval_30min,
                'enabled': True,
                'description': 'Sync payment statuses with Stripe API'
            }
        )
        if created_flag:
            created += 1
            self.stdout.write(self.style.SUCCESS('[OK] Created: Sync Stripe Payments'))
        else:
            task.task = 'accounts.tasks.sync_stripe_payments'
            task.interval = interval_30min
            task.crontab = None  # Clear crontab if switching from crontab to interval
            task.enabled = True
            task.save()
            updated += 1
            self.stdout.write(self.style.SUCCESS('[OK] Updated: Sync Stripe Payments'))

        # ==================================================================
        # 6. WEEKLY SELLER REPORTS - Every Monday at 9:00 AM
        # ==================================================================
        crontab_monday_9am, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='9',
            day_of_week='1',  # Monday = 1
            day_of_month='*',
            month_of_year='*',
        )

        task, created_flag = PeriodicTask.objects.get_or_create(
            name='Weekly Seller Reports - Monday 9:00 AM',
            defaults={
                'task': 'accounts.tasks.weekly_seller_reports',
                'crontab': crontab_monday_9am,
                'enabled': True,
                'description': 'Send weekly performance reports to sellers'
            }
        )
        if created_flag:
            created += 1
            self.stdout.write(self.style.SUCCESS('[OK] Created: Weekly Seller Reports'))
        else:
            task.task = 'accounts.tasks.weekly_seller_reports'
            task.crontab = crontab_monday_9am
            task.enabled = True
            task.save()
            updated += 1
            self.stdout.write(self.style.SUCCESS('[OK] Updated: Weekly Seller Reports'))

        # ==================================================================
        # 7. CLEAN OLD SESSIONS - Every day at 4:00 AM
        # ==================================================================
        crontab_4am, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='4',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        task, created_flag = PeriodicTask.objects.get_or_create(
            name='Clean Old Sessions - 4:00 AM',
            defaults={
                'task': 'accounts.tasks.clean_old_sessions',
                'crontab': crontab_4am,
                'enabled': True,
                'description': 'Clean up expired Django sessions'
            }
        )
        if created_flag:
            created += 1
            self.stdout.write(self.style.SUCCESS('[OK] Created: Clean Old Sessions'))
        else:
            task.task = 'accounts.tasks.clean_old_sessions'
            task.crontab = crontab_4am
            task.enabled = True
            task.save()
            updated += 1
            self.stdout.write(self.style.SUCCESS('[OK] Updated: Clean Old Sessions'))

        # ==================================================================
        # 8. ABANDONED REGISTRATION REMINDER - Every day at 6:00 PM
        # ==================================================================
        crontab_6pm, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='18',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        task, created_flag = PeriodicTask.objects.get_or_create(
            name='Abandoned Registration Reminder - 6:00 PM',
            defaults={
                'task': 'accounts.tasks.abandoned_registration_reminder',
                'crontab': crontab_6pm,
                'enabled': True,
                'description': 'Remind users to complete registration payment'
            }
        )
        if created_flag:
            created += 1
            self.stdout.write(self.style.SUCCESS('[OK] Created: Abandoned Registration Reminder'))
        else:
            task.task = 'accounts.tasks.abandoned_registration_reminder'
            task.crontab = crontab_6pm
            task.enabled = True
            task.save()
            updated += 1
            self.stdout.write(self.style.SUCCESS('[OK] Updated: Abandoned Registration Reminder'))

        # ==================================================================
        # SUMMARY
        # ==================================================================
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS(f'Setup Complete!'))
        self.stdout.write(self.style.SUCCESS(f'Created: {created} tasks'))
        self.stdout.write(self.style.SUCCESS(f'Updated: {updated} tasks'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Next steps:'))
        self.stdout.write('1. Start Celery worker: celery -A ecommerceBook worker -l info')
        self.stdout.write('2. Start Celery beat: celery -A ecommerceBook beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler')
        self.stdout.write('3. View tasks in admin: /admin/django_celery_beat/periodictask/')
        self.stdout.write('')
