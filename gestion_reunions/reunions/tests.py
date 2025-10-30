from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from .models import Reunion, PresenceRequest

class PresenceFormTest(TestCase):
    def setUp(self):
        # Crée une réunion fictive pour le test
        self.reunion = Reunion.objects.create(
            title="Réunion Test",
            date=timezone.now(),
            qr_code_uuid="test-uuid-1234"
        )
        self.client = Client()

    @patch('reunions.views.ActiveDirectoryService')
    def test_presence_form_artci_email(self, mock_ad_service):
        # Simulation de la réponse AD
        mock_ad_service.return_value.get_user_info.return_value = {
            'email': 'dja.rodrigue@artci.ci',
            'prenom': 'Rodrigue',
            'nom': 'Dja',
            'organisation': 'ARTCI',
            'fonction': 'Analyste',
            'contact': '12345678',
            'poste': 'Analyste',
            'departement': 'IT',
            'matricule': 'ARTCI001'
        }

        url = reverse('presence_form', args=[self.reunion.qr_code_uuid])
        response = self.client.post(url, data={'email': 'dja.rodrigue@artci.ci'})

        # Vérifie la réponse HTTP
        self.assertEqual(response.status_code, 200)

        # Vérifie que la présence a été créée
        presence = PresenceRequest.objects.filter(email='dja.rodrigue@artci.ci', reunion=self.reunion)
        self.assertTrue(presence.exists())

    def test_presence_form_no_email(self):
        url = reverse('presence_form', args=[self.reunion.qr_code_uuid])
        response = self.client.post(url, data={'email': ''})

        # Doit rediriger car email manquant
        self.assertEqual(response.status_code, 302)