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
                
                # Extraction et formatage des données
                user_info = {
                    'compte': str(user_entry.sAMAccountName.value) if user_entry.sAMAccountName else None,
                    'nom_complet': str(user_entry.cn.value) if user_entry.cn else None,
                    'prenom': str(user_entry.givenName.value) if user_entry.givenName else '',
                    'nom': str(user_entry.sn.value) if user_entry.sn else '',
                    'email': str(user_entry.mail.value) if user_entry.mail else email,
                    'upn': str(user_entry.userPrincipalName.value) if user_entry.userPrincipalName else None,
                    'telephone': str(user_entry.telephoneNumber.value) if user_entry.telephoneNumber else '',
                    'departement': str(user_entry.department.value) if user_entry.department else '',
                    'poste': str(user_entry.title.value) if user_entry.title else '',
                    'entreprise': str(user_entry.company.value) if user_entry.company else 'ARTCI',
                    'bureau': str(user_entry.physicalDeliveryOfficeName.value) if user_entry.physicalDeliveryOfficeName else '',
                    'dn': str(user_entry.distinguishedName.value) if user_entry.distinguishedName else None,
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