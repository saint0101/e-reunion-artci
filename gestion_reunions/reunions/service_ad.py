import logging
import os
from ldap3 import Server, Connection, ALL, SUBTREE
from django.core.cache import cache
from django.conf import settings
from dotenv import load_dotenv
from gestion_reunions.settings import AD_BIND_PASSWORD, AD_BIND_DN, AD_SEARCH_BASE, AD_SERVER, AD_USER

logger = logging.getLogger(__name__)

class ActiveDirectoryService:
    def __init__(self):
        load_dotenv()  # charger .env
        
        # self.server_address = os.environ.get('AD_SERVER')
        self.server_address = AD_SERVER
        self.user = AD_USER
        self.password = AD_BIND_PASSWORD

        #self.user = os.environ.get('AD_USER')
        #self.password = os.environ.get('AD_BIND_PASSWORD')
        
        if not all([self.server_address, self.user, self.password]):
            raise ValueError("AD_SERVER, AD_USER ou AD_BIND_PASSWORD manquant dans le .env")
        
        self.server = Server(self.server_address, get_info=ALL)
    
    def safe_get(self, entry, attr_name, default=''):
        try:
            attr = getattr(entry, attr_name, None)
            if not attr or not hasattr(attr, 'value'):
                return default
            
            value = attr.value
            if isinstance(value, (list, tuple)):
                value = value[0] if value else default

            if value is None:
                return default

            return str(value).strip()
        except Exception as e:
            logger.warning(f"Erreur extraction {attr_name}: {e}")
            return default

    def get_user_info(self, email=None):
        """
        Récupère les informations d'un utilisateur depuis l'AD ARTCI
        """
        if not email:
            logger.warning("⚠️ Aucun email fourni à get_user_info()")
            return None

        cache_key = f'ad_user_{email}'
        cached_info = cache.get(cache_key)
        if cached_info:
            logger.info(f"Informations récupérées depuis le cache pour {email}")
            return cached_info
        
        try:
            conn = Connection(
                self.server,
                user= AD_BIND_DN,
                password= AD_BIND_PASSWORD,
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
                'prenom': self.safe_get(user_entry, 'givenName', ''),
                'nom': self.safe_get(user_entry, 'sn', ''),
                'organisation': self.safe_get(user_entry, 'company', 'ARTCI'),
                'fonction': self.safe_get(user_entry, 'title', ''),
                'contact': self.safe_get(user_entry, 'telephoneNumber', '') or self.safe_get(user_entry, 'mobile', ''),
                'poste': self.safe_get(user_entry, 'title', ''),
                'departement': self.safe_get(user_entry, 'department', ''),
                'matricule': self.safe_get(user_entry, 'employeeID', ''),
                'bureau': self.safe_get(user_entry, 'physicalDeliveryOfficeName', ''),
                'nom_complet': self.safe_get(user_entry, 'cn', ''),
                'dn': self.safe_get(user_entry, 'distinguishedName', ''),
                'compte': self.safe_get(user_entry, 'sAMAccountName', '')
            }
            
            conn.unbind()
            cache.set(cache_key, user_info, 3600)
            logger.info(f"Utilisateur trouvé dans AD: {user_info['nom_complet']} ({email})")
            print(user_info)
            return user_info
        
        except Exception as e:
            logger.error(f"Erreur lors de la connexion à l'AD ARTCI pour {email}: {str(e)}")
            return None

    def search_by_account_name(self, account_name):
        try:
            conn = Connection(
                self.server,
                user=settings.AD_BIND_DN,
                password=settings.AD_BIND_PASSWORD,
                auto_bind=True
            )
            search_filter = f'(&(objectClass=user)(sAMAccountName={account_name}))'
            conn.search(
                search_base=settings.AD_SEARCH_BASE,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=['mail']
            )
            if conn.entries and len(conn.entries) > 0:
                email = self.safe_get(conn.entries[0], 'mail', None)
                conn.unbind()
                if email:
                    return self.get_user_info(email)
            conn.unbind()
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par compte: {str(e)}")
            return None
    
    def test_connection(self):
        try:
            conn = Connection(
                self.server,
                user=settings.AD_BIND_DN,
                password=settings.AD_BIND_PASSWORD,
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
            logger.error(f"Erreur de test de connexion AD: {str(e)}")
            return False, str(e)