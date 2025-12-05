# Generated manually to add missing fields to existing tables

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        # Add is_deleted field to Book
        migrations.AddField(
            model_name='book',
            name='is_deleted',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='book',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),

        # Add is_deleted field to Course
        migrations.AddField(
            model_name='course',
            name='is_deleted',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='course',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),

        # Add is_deleted field to Webinar
        migrations.AddField(
            model_name='webinar',
            name='is_deleted',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='webinar',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),

        # Add description field to Category if it doesn't exist
        migrations.AddField(
            model_name='category',
            name='description',
            field=models.TextField(blank=True, help_text='Category description'),
        ),
        migrations.AddField(
            model_name='category',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Active categories shown to users'),
        ),
        migrations.AddField(
            model_name='category',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
