from ldap3 import Server, Connection, ALL, SUBTREE
from django.conf import settings
from django.core.cache import cache
import logging
from dotenv import load_dotenv


logger = logging.getLogger(__name__)
load_dotenv()

class ActiveDirectoryService:
    def __init__(self):
        self.server = Server(
            # settings.AD_SERVER,
            'ldap://172.16.0.4'
            # port=settings.AD_PORT,
            port=389,
            get_info=ALL
        )
    
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
                user=settings.AD_BIND_DN,
                password=settings.AD_BIND_PASSWORD,
                auto_bind=True
            )
            
            search_filter = f'(&(objectClass=user)(mail={email}))'
            
            conn.search(
                search_base=settings.AD_SEARCH_BASE,
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
                        
            def safe_get(entry, attr_name, default=''):
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
            
            user_info = {
                'email': safe_get(user_entry, 'mail', email),
                'prenom': safe_get(user_entry, 'givenName', ''),
                'nom': safe_get(user_entry, 'sn', ''),
                'organisation': safe_get(user_entry, 'company', 'ARTCI'),
                'fonction': safe_get(user_entry, 'title', ''),
                'contact': safe_get(user_entry, 'telephoneNumber', '') or safe_get(user_entry, 'mobile', ''),
                'poste': safe_get(user_entry, 'title', ''),
                'departement': safe_get(user_entry, 'department', ''),
                'matricule': safe_get(user_entry, 'employeeID', ''),
                'bureau': safe_get(user_entry, 'physicalDeliveryOfficeName', ''),
                'nom_complet': safe_get(user_entry, 'cn', ''),
                'dn': safe_get(user_entry, 'distinguishedName', ''),
                'compte': safe_get(user_entry, 'sAMAccountName', '')
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
                email = safe_get(conn.entries[0], 'mail', None)
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