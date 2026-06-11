"""
Script de test du classement protocolaire des participants.
Aucune base de données, aucun email, aucune connexion AD.

Usage :
    python test_classement.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# ── Importer uniquement les fonctions utilitaires (pas Django entier) ─────────
import unicodedata

def _normalize(text):
    text = (text or '').lower()
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

def get_presence_rank(presence):
    f = _normalize(presence['fonction'])
    o = _normalize(presence['organisation'])
    combined = f + ' ' + o

    if 'president' in combined and 'conseil' in combined:
        return (0, _normalize(presence['nom']))
    if 'conseil de regulation' in combined or ('membre' in combined and 'conseil' in combined):
        return (1, _normalize(presence['nom']))
    if 'directeur general' in combined or 'direction generale' in combined:
        return (2, _normalize(presence['nom']))
    return (3, _normalize(presence['nom']))

def sort_presences(presences):
    return sorted(presences, key=get_presence_rank)


# ── Participants simulés ───────────────────────────────────────────────────────

PARTICIPANTS = [
    # Participants ordinaires (arrivés en premier dans la liste brute)
    {
        'nom': 'KONÉ', 'prenom': 'Mamadou',
        'fonction': 'Chef de Service Juridique',
        'organisation': 'ARTCI',
        'email': 'kone.mamadou@artci.ci',
    },
    {
        'nom': 'TRAORÉ', 'prenom': 'Fatou',
        'fonction': 'Directrice des Ressources Humaines',
        'organisation': 'ARTCI',
        'email': 'traore.fatou@artci.ci',
    },
    # Membres du Conseil (entrés après)
    {
        'nom': 'GNAMBA-YAO', 'prenom': 'Isaac',
        'fonction': 'Membre du Conseil de Régulation',
        'organisation': 'ARTCI',
        'email': 'gnambayao.isaac@artci.ci',
    },
    {
        'nom': 'BESSE', 'prenom': 'Laure',
        'fonction': 'Membre du Conseil de Régulation',
        'organisation': 'ARTCI',
        'email': 'besse.laure@artci.ci',
    },
    {
        'nom': 'COULIBALY', 'prenom': 'Issa',
        'fonction': 'Membre du Conseil de Régulation',
        'organisation': 'ARTCI',
        'email': 'coulibaly.issa@artci.ci',
    },
    {
        'nom': 'AMAND', 'prenom': 'Patricia',
        'fonction': 'Membre du Conseil de Régulation',
        'organisation': 'ARTCI',
        'email': 'amand.patricia@artci.ci',
    },
    {
        'nom': 'SAKO', 'prenom': 'Ahmed',
        'fonction': 'Membre du Conseil de Régulation',
        'organisation': 'ARTCI',
        'email': 'sako.ahmed@artci.ci',
    },
    {
        'nom': 'COULIBALY', 'prenom': 'Mamadou',
        'fonction': 'Membre du Conseil de Régulation',
        'organisation': 'ARTCI',
        'email': 'coulibaly.mamadou@artci.ci',
    },
    # Directeur Général
    {
        'nom': 'OUATTARA', 'prenom': 'Lakoun',
        'fonction': 'Directeur Général',
        'organisation': 'Direction Générale',
        'email': 'ouattara.lakoun@artci.ci',
    },
    # Président du Conseil (entré en dernier dans la liste brute)
    {
        'nom': 'ADOM', 'prenom': 'Roger',
        'fonction': 'Président du Conseil de Régulation',
        'organisation': 'ARTCI',
        'email': 'adom.roger@artci.ci',
    },
    # Participant externe
    {
        'nom': 'DUPONT', 'prenom': 'Jean',
        'fonction': 'Directeur Commercial',
        'organisation': 'Orange CI',
        'email': 'dupont.jean@orange.ci',
    },
]


PRIORITY_LABELS = {
    0: '🥇 Président du Conseil',
    1: '🏛️  Membre du Conseil',
    2: '🎯 Directeur Général',
    3: '👤 Autre participant',
}

# ── Affichage ─────────────────────────────────────────────────────────────────

def run_test(participants, titre):
    print(f"\n{'═'*70}")
    print(f"  {titre}")
    print(f"{'═'*70}")
    sorted_list = sort_presences(participants)
    for i, p in enumerate(sorted_list, 1):
        rank, _ = get_presence_rank(p)
        label = PRIORITY_LABELS[rank]
        print(f"  {i:>2}. {label:<30} {p['prenom']} {p['nom']}")
        print(f"       Fonction     : {p['fonction']}")
        print(f"       Organisation : {p['organisation']}")
        print()


# ── Cas 1 : Tous présents ──────────────────────────────────────────────────────
print("\n" + "━"*70)
print("  TEST DU CLASSEMENT PROTOCOLAIRE — QR Meeting ARTCI")
print("━"*70)
print("  Liste brute (ordre d'arrivée) :")
for i, p in enumerate(PARTICIPANTS, 1):
    print(f"    {i:>2}. {p['prenom']} {p['nom']} — {p['fonction']}")

run_test(PARTICIPANTS, "CAS 1 : Président + Conseil + DG + Autres présents")

# ── Cas 2 : Sans membres du Conseil ──────────────────────────────────────────
sans_conseil = [p for p in PARTICIPANTS
                if 'conseil' not in p['fonction'].lower() or 'directeur' in p['fonction'].lower()]
run_test(sans_conseil, "CAS 2 : Aucun membre du Conseil — DG en tête")

# ── Cas 3 : Président seul (sans autres conseillers) ─────────────────────────
sans_conseillers = [p for p in PARTICIPANTS
                    if 'Membre du Conseil' not in p['fonction']]
run_test(sans_conseillers, "CAS 3 : Président seul + DG + Autres")

# ── Cas 4 : Sans président ni conseil ─────────────────────────────────────────
sans_president_conseil = [p for p in PARTICIPANTS
                          if 'conseil' not in p['fonction'].lower()]
run_test(sans_president_conseil, "CAS 4 : Ni Président ni Conseil — DG en tête")

# ── Cas 5 : Que des externes ──────────────────────────────────────────────────
externes = [p for p in PARTICIPANTS if not p['email'].endswith('@artci.ci')]
externes += [
    {'nom': 'MARTIN', 'prenom': 'Sophie', 'fonction': 'PDG', 'organisation': 'MTN CI', 'email': 's.martin@mtn.ci'},
    {'nom': 'BAMBA', 'prenom': 'Idriss', 'fonction': 'DG Adjoint', 'organisation': 'Moov Africa', 'email': 'i.bamba@moov.ci'},
]
run_test(externes, "CAS 5 : Que des participants externes (tri alphabétique)")

print("━"*70)
print("  ✅ Tests terminés — aucune BDD, aucun email, aucune connexion AD")
print("━"*70 + "\n")
