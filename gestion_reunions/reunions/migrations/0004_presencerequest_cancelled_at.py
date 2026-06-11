from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reunions', '0003_customuser_must_change_password'),
    ]

    operations = [
        migrations.AddField(
            model_name='presencerequest',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
