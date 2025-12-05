# Add missing review field to Rating model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_add_course_webinar_fields'),
    ]

    operations = [
        # Add review field to Rating
        migrations.AddField(
            model_name='rating',
            name='review',
            field=models.TextField(blank=True, help_text='Optional review text'),
        ),
    ]
