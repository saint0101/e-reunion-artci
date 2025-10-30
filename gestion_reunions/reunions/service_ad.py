import logging
import os
from ldap3 import Server, Connection, ALL, SUBTREE
from django.core.cache import cache
from dotenv import load_dotenv

# Charger le .env
load_dotenv()

logger = logging.getLogger(__name__)

# Récupérer les variables AD depuis le .env
AD_SERVER = os.environ.get("AD_SERVER")
AD_USER = os.environ.get("AD_USER")
AD_PASSWORD = os.environ.get("AD_PASSWORD")
AD_BIND_DN = os.environ.get("AD_BIND_DN") or AD_USER
AD_SEARCH_BASE = os.environ.get("AD_SEARCH_BASE")

if not all([AD_SERVER, AD_USER, AD_PASSWORD, AD_SEARCH_BASE]):
    raise ValueError("AD_SERVER, AD_USER, AD_PASSWORD ou AD_SEARCH_BASE manquant dans le .env")

class ActiveDirectoryService:
    def __init__(self):
        self.server = Server(AD_SERVER, get_info=ALL)

    def safe_get(self, entry, attr_name, default=''):
        """Extraction sûre des attributs LDAP"""
        try:
            attr = getattr(entry, attr_name, None)
            if not attr or not hasattr(attr, 'value'):
                return default
            value = attr.value
            if isinstance(value, (list, tuple)):
                value = value[0] if value else default
            return str(value).strip() if value is not None else default
        except Exception as e:
            logger.warning(f"Erreur extraction {attr_name}: {e}")
            return default

    def get_user_info(self, email=None):
        """Récupère les infos d'un utilisateur par email depuis l'AD"""
        if not email:
            logger.warning("⚠️ Aucun email fourni à get_user_info()")
            return None

        cache_key = f'ad_user_{email}'
        cached_info = cache.get(cache_key)
        if cached_info:
            logger.info(f"Infos récupérées depuis le cache pour {email}")
            return cached_info

        try:
            conn = Connection(
                self.server,
                user=AD_BIND_DN,
                password=AD_PASSWORD,
                auto_bind=True
            )

            search_filter = f'(&(objectClass=user)(mail={email}))'
            conn.search(
                search_base=AD_SEARCH_BASE,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=[
                    'sAMAccountName', 'cn', 'givenName', 'sn', 'mail',
                    'userPrincipalName', 'telephoneNumber', 'mobile',
                    'department', 'title', 'company', 'physicalDeliveryOfficeName',
                    'manager', 'employeeID', 'distinguishedName'
                ]
            )

            if not conn.entries:
                conn.unbind()
                logger.warning(f"Aucun utilisateur trouvé dans AD pour: {email}")
                return None

            user_entry = conn.entries[0]

            user_info = {
                'email': self.safe_get(user_entry, 'mail', email),
                'prenom': self.safe_get(user_entry, 'givenName'),
                'nom': self.safe_get(user_entry, 'sn'),
                'organisation': self.safe_get(user_entry, 'company', 'ARTCI'),
                'fonction': self.safe_get(user_entry, 'title'),
                'contact': self.safe_get(user_entry, 'telephoneNumber') or self.safe_get(user_entry, 'mobile'),
                'poste': self.safe_get(user_entry, 'title'),
                'departement': self.safe_get(user_entry, 'department'),
                'matricule': self.safe_get(user_entry, 'employeeID'),
                'bureau': self.safe_get(user_entry, 'physicalDeliveryOfficeName'),
                'nom_complet': self.safe_get(user_entry, 'cn'),
                'dn': self.safe_get(user_entry, 'distinguishedName'),
                'compte': self.safe_get(user_entry, 'sAMAccountName')
            }

            conn.unbind()
            cache.set(cache_key, user_info, 3600)
            logger.info(f"Utilisateur trouvé dans AD: {user_info['nom_complet']} ({email})")
            return user_info

        except Exception as e:
            logger.error(f"Erreur connexion AD pour {email}: {e}")
            return None

    def search_by_account_name(self, account_name):
        """Recherche un utilisateur par son compte AD (sAMAccountName)"""
        try:
            conn = Connection(
                self.server,
                user=AD_BIND_DN,
                password=AD_PASSWORD,
                auto_bind=True
            )

            search_filter = f'(&(objectClass=user)(sAMAccountName={account_name}))'
            conn.search(
                search_base=AD_SEARCH_BASE,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=['mail']
            )

            if conn.entries:
                email = self.safe_get(conn.entries[0], 'mail')
                conn.unbind()
                if email:
                    return self.get_user_info(email)
            conn.unbind()
            return None

        except Exception as e:
            logger.error(f"Erreur recherche par compte: {e}")
            return None

    def test_connection(self):
        """Test de connexion LDAP"""
        try:
            conn = Connection(
                self.server,
                user=AD_BIND_DN,
                password=AD_PASSWORD,
                auto_bind=True
            )
            result = conn.bind()
            conn.unbind()
            if result:
                logger.info("Connexion AD réussie")
                return True, "Connexion réussie"
            else:
                logger.error("Échec de connexion AD")
                return False, "Échec de connexion"
        except Exception as e:
            logger.error(f"Erreur test connexion AD: {e}")
            return False, str(e)