from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reunions', '0006_diligence_rappels'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='direction',
            field=models.CharField(blank=True, max_length=100, verbose_name='Direction / Service'),
        ),
    ]
