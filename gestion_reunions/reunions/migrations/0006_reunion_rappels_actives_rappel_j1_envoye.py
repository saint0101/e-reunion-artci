from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Les colonnes rappels_actives et rappel_j1_envoye existent déjà en DB
    (ajoutées sans migration) avec une contrainte NOT NULL mais sans DEFAULT.
    - database_operations : ajoute les colonnes si absentes et pose un défaut false.
    - state_operations : enregistre les champs dans l'état Django.
    """

    dependencies = [
        ('reunions', '0005_customuser_direction'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='reunion',
                    name='rappels_actives',
                    field=models.BooleanField(default=False),
                ),
                migrations.AddField(
                    model_name='reunion',
                    name='rappel_j1_envoye',
                    field=models.BooleanField(default=False),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE reunions_reunion
                            ADD COLUMN IF NOT EXISTS rappels_actives BOOLEAN NOT NULL DEFAULT false;
                        ALTER TABLE reunions_reunion
                            ALTER COLUMN rappels_actives SET DEFAULT false;

                        ALTER TABLE reunions_reunion
                            ADD COLUMN IF NOT EXISTS rappel_j1_envoye BOOLEAN NOT NULL DEFAULT false;
                        ALTER TABLE reunions_reunion
                            ALTER COLUMN rappel_j1_envoye SET DEFAULT false;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
