from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reunions', '0005_diligence_diligencecomment'),
    ]

    operations = [
        migrations.AddField(
            model_name='diligence',
            name='rappel_j3_envoye',
            field=models.BooleanField(default=False, verbose_name='Rappel J-3 envoyé'),
        ),
        migrations.AddField(
            model_name='diligence',
            name='rappel_j1_envoye',
            field=models.BooleanField(default=False, verbose_name='Rappel J-1 envoyé'),
        ),
    ]
