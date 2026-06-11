from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("reunions", "0003_customuser_must_change_password"),
    ]

    operations = [
        # --- Champs Reunion ---
        migrations.AddField(
            model_name="reunion",
            name="rappels_actives",
            field=models.BooleanField(default=True, verbose_name="Rappels email actifs"),
        ),
        migrations.AddField(
            model_name="reunion",
            name="rappel_j1_envoye",
            field=models.BooleanField(default=False, verbose_name="Rappel J-1 envoyé"),
        ),
        # --- AgendaPoint ---
        migrations.CreateModel(
            name="AgendaPoint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ordre", models.PositiveIntegerField(default=1, verbose_name="Ordre")),
                ("titre", models.CharField(max_length=200, verbose_name="Titre")),
                ("description", models.TextField(blank=True, verbose_name="Description")),
                ("duree_minutes", models.PositiveIntegerField(blank=True, null=True, verbose_name="Durée (min)")),
                ("responsable_externe", models.CharField(blank=True, max_length=200, verbose_name="Responsable externe")),
                ("est_traite", models.BooleanField(default=False, verbose_name="Traité")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "reunion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agenda_points",
                        to="reunions.reunion",
                        verbose_name="Réunion",
                    ),
                ),
                (
                    "responsable_interne",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="points_responsable",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Responsable interne",
                    ),
                ),
            ],
            options={
                "verbose_name": "Point d'agenda",
                "verbose_name_plural": "Points d'agenda",
                "ordering": ["ordre"],
            },
        ),
        # --- Invitation ---
        migrations.CreateModel(
            name="Invitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(verbose_name="Email")),
                ("nom", models.CharField(blank=True, max_length=100, verbose_name="Nom")),
                ("prenom", models.CharField(blank=True, max_length=100, verbose_name="Prénom")),
                ("token", models.UUIDField(default=uuid.uuid4, unique=True, verbose_name="Token")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "En attente"),
                            ("sent", "Envoyée"),
                            ("accepted", "Acceptée"),
                            ("declined", "Déclinée"),
                        ],
                        default="pending",
                        max_length=20,
                        verbose_name="Statut",
                    ),
                ),
                ("sent_at", models.DateTimeField(blank=True, null=True, verbose_name="Envoyée le")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "invited_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invitations_sent",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Invité par",
                    ),
                ),
                (
                    "reunion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invitations",
                        to="reunions.reunion",
                        verbose_name="Réunion",
                    ),
                ),
            ],
            options={
                "verbose_name": "Invitation",
                "verbose_name_plural": "Invitations",
                "unique_together": {("reunion", "email")},
            },
        ),
    ]
