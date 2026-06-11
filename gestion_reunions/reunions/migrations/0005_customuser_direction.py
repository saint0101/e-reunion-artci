from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Le champ `direction` existe déjà dans la DB (ajouté manuellement sans migration).
    - database_operations : crée la colonne si absente (ADD COLUMN IF NOT EXISTS),
      puis lève la contrainte NOT NULL et pose un défaut vide.
    - state_operations : enregistre le champ dans l'état Django.
    """

    dependencies = [
        ('reunions', '0004_presencerequest_cancelled_at'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='customuser',
                    name='direction',
                    field=models.CharField(blank=True, default='', max_length=200),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE reunions_customuser
                            ADD COLUMN IF NOT EXISTS direction VARCHAR(200) NOT NULL DEFAULT '';
                        ALTER TABLE reunions_customuser
                            ALTER COLUMN direction SET DEFAULT '',
                            ALTER COLUMN direction DROP NOT NULL;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
