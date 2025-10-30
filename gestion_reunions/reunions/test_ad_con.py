# test_ad_debug.py
import os, sys
import django

# Ajoute le chemin racine du projet au sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_reunions.settings')

django.setup()

from ldap3 import Server, Connection, ALL, SUBTREE
from django.conf import settings

print("=== TEST DE CONNEXION AD ARTCI ===\n")

# Test 1: Vérification des paramètres
print("1. Vérification des paramètres:")
print(f"   AD_SERVER: {getattr(settings, 'AD_SERVER', 'NON DÉFINI')}")
print(f"   AD_PORT: {getattr(settings, 'AD_PORT', 'NON DÉFINI')}")
print(f"   AD_BIND_DN: {getattr(settings, 'AD_BIND_DN', 'NON DÉFINI')}")
print(f"   AD_BIND_PASSWORD: {'***' if getattr(settings, 'AD_BIND_PASSWORD', None) else 'NON DÉFINI'}")
print(f"   AD_SEARCH_BASE: {getattr(settings, 'AD_SEARCH_BASE', 'NON DÉFINI')}\n")

# Test 2: Connexion au serveur
try:
    print("2. Tentative de connexion au serveur...")
    server = Server(settings.AD_SERVER, port=settings.AD_PORT, get_info=ALL)
    conn = Connection(
        server,
        user=settings.AD_BIND_DN,
        password=settings.AD_BIND_PASSWORD,
        auto_bind=True
    )
    print("   ✓ Connexion réussie!\n")
    
    # Test 3: Recherche d'un utilisateur
    test_email = "dja.rodrigue@artci.ci"
    print(f"3. Recherche de l'utilisateur: {test_email}")
    
    search_filter = f'(&(objectClass=user)(mail={test_email}))'
    print(f"   Filtre: {search_filter}")
    
    result = conn.search(
        search_base=settings.AD_SEARCH_BASE,
        search_filter=search_filter,
        search_scope=SUBTREE,
        attributes='*'  # Tous les attributs
    )
    
    print(f"   Résultat de recherche: {result}")
    print(f"   Nombre d'entrées trouvées: {len(conn.entries)}\n")
    
    if conn.entries:
        print("4. Détails de l'utilisateur trouvé:")
        user = conn.entries[0]
        print(f"   DN: {user.entry_dn}")
        print(f"\n   Attributs disponibles:")
        
        # Afficher tous les attributs
        for attr_name in sorted(user.entry_attributes_as_dict.keys()):
            attr_value = user.entry_attributes_as_dict[attr_name]
            print(f"     - {attr_name}: {attr_value}")
    else:
        print("   ✗ Aucun utilisateur trouvé!")
        print("\n   Essai de recherche large:")
        # Recherche sans filtre email
        conn.search(
            search_base=settings.AD_SEARCH_BASE,
            search_filter='(objectClass=user)',
            search_scope=SUBTREE,
            attributes=['cn', 'mail'],
            size_limit=5
        )
        print(f"   Premiers utilisateurs dans AD:")
        for entry in conn.entries[:5]:
            print(f"     - {entry.cn}: {entry.mail if hasattr(entry, 'mail') else 'pas de mail'}")
    
    conn.unbind()
    
except Exception as e:
    print(f"   ✗ Erreur: {str(e)}")
    import traceback
    traceback.print_exc()