from ldap3 import Server, Connection, ALL, SUBTREE
from django.core.cache import cache
import logging, os
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

# Charger le fichier .env depuis la racine du projet
BASE_DIR = Path(__file__).resolve().parent.parent  # ← dossier gestion_reunions/
dotenv_path = BASE_DIR / ".env"
load_dotenv(dotenv_path)
logger.info(f"✅ Chargement du .env depuis : {dotenv_path}")

class ActiveDirectoryService:
    def __init__(self):
        # Charger les infos depuis le .env
        self.AD_SERVER = os.environ.get("AD_SERVER")
        self.AD_PORT = int(os.environ.get("AD_PORT", 389))
        self.AD_BIND_PASSWORD = os.environ.get("AD_BIND_PASSWORD")
        self.AD_BIND_DN = os.environ.get("AD_BIND_DN") or self.AD_USER
        self.AD_SEARCH_BASE = os.environ.get("AD_SEARCH_BASE")

        # 🐞 Debug temporaire
        print("🐞 DEBUG AD ENV:")
        print("AD_SERVER:", self.AD_SERVER)
        print("AD_BIND_PASSWORD:", "✅ défini" if self.AD_BIND_PASSWORD else "❌ manquant")
        print("AD_SEARCH_BASE:", self.AD_SEARCH_BASE)
        print("Env chargé depuis:", dotenv_path)

        # Vérification de base
        if not all([self.AD_SERVER, self.AD_BIND_PASSWORD, self.AD_SEARCH_BASE]):
            raise ValueError("⚠️ AD_SERVER, AD_BIND_PASSWORD ou AD_SEARCH_BASE manquant dans le .env")

        # Création du serveur LDAP
        self.server = Server(
            self.AD_SERVER,
            port=self.AD_PORT,
            get_info=ALL
        )

    def get_user_info(self, email=None):
        """Récupère les informations d'un utilisateur depuis l'AD ARTCI"""
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
                user=self.AD_BIND_DN,
                password=self.AD_BIND_PASSWORD,
                auto_bind=True
            )

            search_filter = f'(&(objectClass=user)(mail={email}))'
            conn.search(
                search_base=self.AD_SEARCH_BASE,
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
                    return str(value).strip() if value else default
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
            return user_info

        except Exception as e:
            logger.error(f"Erreur lors de la connexion à l'AD ARTCI pour {email}: {str(e)}")
            return None

    def test_connection(self):
        """Teste la connexion au serveur AD"""
        try:
            conn = Connection(
                self.server,
                user=self.AD_BIND_DN,
                password=self.AD_BIND_PASSWORD,
                auto_bind=True
            )
            result = conn.bind()
            conn.unbind()
            if result:
                logger.info("Connexion AD réussie ✅")
                return True, "Connexion réussie"
            else:
                logger.error("Échec de connexion AD ❌")
                return False, "Échec de connexion"
        except Exception as e:
            logger.error(f"Erreur de test de connexion AD: {str(e)}")
            return False, str(e)