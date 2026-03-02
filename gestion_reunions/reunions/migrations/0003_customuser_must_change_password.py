from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reunions", "0002_alter_compterendu_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="must_change_password",
            field=models.BooleanField(
                default=False,
                help_text="Force le changement de mot de passe à la prochaine connexion",
            ),
        ),
    ]
