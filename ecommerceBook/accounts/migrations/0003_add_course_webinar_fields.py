# Add missing fields to Course and Webinar models

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_add_missing_fields'),
    ]

    operations = [
        # Add duration_hours field to Course
        migrations.AddField(
            model_name='course',
            name='duration_hours',
            field=models.PositiveIntegerField(null=True, blank=True, help_text='Course duration in hours'),
        ),

        # Add scheduled_date field to Webinar
        migrations.AddField(
            model_name='webinar',
            name='scheduled_date',
            field=models.DateTimeField(null=True, blank=True, help_text='Original webinar date'),
        ),
    ]
