from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reunions', '0004_agenda_invitation_rappels'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Diligence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titre', models.CharField(max_length=255, verbose_name='Titre')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('responsable_externe', models.CharField(blank=True, max_length=200, verbose_name='Responsable externe')),
                ('echeance', models.DateField(blank=True, null=True, verbose_name='Échéance')),
                ('status', models.CharField(
                    choices=[
                        ('open', 'À faire'),
                        ('in_progress', 'En cours'),
                        ('completed', 'Terminée'),
                        ('cancelled', 'Annulée'),
                    ],
                    default='open',
                    max_length=20,
                    verbose_name='Statut',
                )),
                ('priorite', models.CharField(
                    choices=[
                        ('low', 'Faible'),
                        ('medium', 'Normale'),
                        ('high', 'Urgente'),
                    ],
                    default='medium',
                    max_length=10,
                    verbose_name='Priorité',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='diligences_creees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Créée par',
                )),
                ('responsable_interne', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='diligences_assignees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Responsable interne',
                )),
                ('reunion', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='diligences',
                    to='reunions.reunion',
                )),
            ],
            options={
                'verbose_name': 'Diligence',
                'verbose_name_plural': 'Diligences',
                'ordering': ['-priorite', 'echeance', 'created_at'],
            },
        ),
        migrations.CreateModel(
            name='DiligenceComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contenu', models.TextField(verbose_name='Commentaire')),
                ('ancien_status', models.CharField(blank=True, max_length=20)),
                ('nouveau_status', models.CharField(blank=True, max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('auteur', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='commentaires_diligences',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('diligence', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commentaires',
                    to='reunions.diligence',
                )),
            ],
            options={
                'verbose_name': 'Commentaire de diligence',
                'verbose_name_plural': 'Commentaires de diligences',
                'ordering': ['created_at'],
            },
        ),
    ]
