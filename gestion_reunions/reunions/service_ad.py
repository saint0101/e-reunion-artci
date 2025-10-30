from ldap3 import Server, Connection, ALL, SUBTREE
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class ActiveDirectoryService:
    def __init__(self):
        self.server = Server(
            settings.AD_SERVER,
            port=settings.AD_PORT,
            get_info=ALL
        )
    
    def get_user_info(self, email):
        """
        Récupère les informations d'un utilisateur depuis l'AD ARTCI
        """
        # Vérifier le cache d'abord
        cache_key = f'ad_user_{email}'
        cached_info = cache.get(cache_key)
        if cached_info:
            logger.info(f"Informations récupérées depuis le cache pour {email}")
            return cached_info
        
        try:
            # Connexion à l'AD avec le compte de service
            conn = Connection(
                self.server,
                user=settings.AD_BIND_DN,
                password=settings.AD_BIND_PASSWORD,
                auto_bind=True
            )
            
            # Filtre de recherche par email (mail) ou sAMAccountName
            search_filter = f'(&(objectClass=user)(mail={email}))'
            
            # Recherche dans l'AD ARTCI
            conn.search(
                search_base=settings.AD_SEARCH_BASE,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=[
                    'sAMAccountName',        # Identifiant de connexion
                    'cn',                    # Nom complet (Common Name)
                    'givenName',             # Prénom
                    'sn',                    # Nom de famille (Surname)
                    'mail',                  # Email
                    'userPrincipalName',     # UPN (user@domain)
                    'telephoneNumber',       # Téléphone
                    'department',            # Département
                    'title',                 # Titre/Poste
                    'company',               # Entreprise
                    'physicalDeliveryOfficeName',  # Bureau
                    'manager',               # Manager (DN)
                    'distinguishedName'      # DN complet
                ]
            )
            
            if conn.entries and len(conn.entries) > 0:
                user_entry = conn.entries[0]
                
                # Fonction helper pour extraire les valeurs de manière sécurisée
                def safe_get_value(entry, attr_name, default=''):
                    try:
                        attr = getattr(entry, attr_name, None)
                        if attr and hasattr(attr, 'value') and attr.value is not None:
                            value = str(attr.value)
                            return value.strip() if value else default
                        return default
                    except Exception as e:
                        logger.warning(f"Erreur lors de l'extraction de {attr_name}: {str(e)}")
                        return default
                
                # Extraction et formatage des données
                user_info = {
                    'compte': safe_get_value(user_entry, 'sAMAccountName', None),
                    'nom_complet': safe_get_value(user_entry, 'cn', None),
                    'prenom': safe_get_value(user_entry, 'givenName', ''),
                    'nom': safe_get_value(user_entry, 'sn', ''),
                    'email': safe_get_value(user_entry, 'mail', email),
                    'upn': safe_get_value(user_entry, 'userPrincipalName', None),
                    'telephone': safe_get_value(user_entry, 'telephoneNumber', ''),
                    'departement': safe_get_value(user_entry, 'department', ''),
                    'poste': safe_get_value(user_entry, 'title', ''),
                    'entreprise': safe_get_value(user_entry, 'company', 'ARTCI'),
                    'bureau': safe_get_value(user_entry, 'physicalDeliveryOfficeName', ''),
                    'dn': safe_get_value(user_entry, 'distinguishedName', None),
                    'matricule': None  # ARTCI n'utilise pas employeeID apparemment
                }
                
                conn.unbind()
                
                # Mise en cache pour 1 heure
                cache.set(cache_key, user_info, 3600)
                
                logger.info(f"Utilisateur trouvé dans AD: {user_info['nom_complet']} ({email})")
                return user_info
            else:
                conn.unbind()
                logger.warning(f"Aucun utilisateur trouvé dans AD pour: {email}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de la connexion à l'AD ARTCI: {str(e)}")
            return None
    
    def search_by_account_name(self, account_name):
        """
        Recherche par sAMAccountName (identifiant de compte)
        """
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
                attributes=['mail', 'cn', 'givenName', 'sn', 'department', 'title']
            )
            
            if conn.entries and len(conn.entries) > 0:
                user_entry = conn.entries[0]
                email = str(user_entry.mail.value) if user_entry.mail else None
                conn.unbind()
                
                if email:
                    return self.get_user_info(email)
            
            conn.unbind()
            return None
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par compte: {str(e)}")
            return None
    
    def test_connection(self):
        """
        Teste la connexion à l'AD
        """
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