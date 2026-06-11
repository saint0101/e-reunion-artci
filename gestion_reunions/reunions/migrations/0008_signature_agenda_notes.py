from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reunions', '0007_customuser_direction'),
    ]

    operations = [
        # Signature numérique sur PresenceRequest
        migrations.AddField(
            model_name='presencerequest',
            name='signature',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='signatures/',
                verbose_name='Signature numérique',
            ),
        ),
        # Notes de séance sur AgendaPoint
        migrations.AddField(
            model_name='agendapoint',
            name='notes_seance',
            field=models.TextField(
                blank=True,
                verbose_name='Notes de séance',
                help_text='Notes prises durant la réunion sur ce point',
            ),
        ),
    ]
