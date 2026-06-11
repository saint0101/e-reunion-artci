#!/usr/bin/env python3
"""Génération de la présentation PowerPoint QR Meeting / eReunion"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt
from pptx.enum.dml import MSO_THEME_COLOR
import pptx.oxml.ns as nsmap
from lxml import etree
import copy
import os

# ─── Palette couleurs ────────────────────────────────────────────────────────
ORANGE      = RGBColor(0xFF, 0x6B, 0x35)   # #FF6B35 – couleur ARTCI
DARK_BLUE   = RGBColor(0x1A, 0x2A, 0x4A)   # #1A2A4A – bleu foncé pro
LIGHT_GREY  = RGBColor(0xF4, 0xF6, 0xF9)   # #F4F6F9 – fond clair
MID_GREY    = RGBColor(0x6C, 0x75, 0x7D)   # texte secondaire
WHITE       = RGBColor(0xFF, 0xFF, 0xFF)
BLACK       = RGBColor(0x1A, 0x1A, 0x1A)
GREEN       = RGBColor(0x28, 0xA7, 0x45)
TEAL        = RGBColor(0x17, 0xA2, 0xB8)

LOGO_PATH   = "/Users/luther/Documents/Dev/projet_reunion/gestion_reunions/static/img/artci_logo.png"
QR_PATH     = "/Users/luther/Documents/Dev/projet_reunion/gestion_reunions/gestion_reunions/media/qr_codes/qr_reunion_1.png"
OUT_PATH    = "/Users/luther/Documents/Dev/projet_reunion/gestion_reunions/Presentation_QRMeeting_ARTCI.pptx"

SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)

prs = Presentation()
prs.slide_width  = SLIDE_W
prs.slide_height = SLIDE_H

# ─── Helpers ─────────────────────────────────────────────────────────────────
def blank_slide(prs):
    blank_layout = prs.slide_layouts[6]   # totalement vide
    return prs.slides.add_slide(blank_layout)

def add_rect(slide, l, t, w, h, fill_color, alpha=None):
    shape = slide.shapes.add_shape(
        pptx.enum.shapes.MSO_SHAPE_TYPE.AUTO_SHAPE if False else 1,  # MSO_SHAPE.RECTANGLE = 1
        l, t, w, h
    )
    shape.line.fill.background()
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.color.rgb = fill_color
    return shape

def add_text_box(slide, text, l, t, w, h,
                 font_size=20, bold=False, color=BLACK,
                 align=PP_ALIGN.LEFT, italic=False, wrap=True):
    txb = slide.shapes.add_textbox(l, t, w, h)
    txb.word_wrap = wrap
    tf  = txb.text_frame
    tf.word_wrap = wrap
    p   = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size  = Pt(font_size)
    run.font.bold  = bold
    run.font.italic= italic
    run.font.color.rgb = color
    return txb

def add_paragraph(tf, text, font_size=16, bold=False, color=BLACK,
                  align=PP_ALIGN.LEFT, space_before=Pt(4), italic=False):
    p = tf.add_paragraph()
    p.alignment = align
    p.space_before = space_before
    run = p.add_run()
    run.text = text
    run.font.size  = Pt(font_size)
    run.font.bold  = bold
    run.font.italic= italic
    run.font.color.rgb = color
    return p

def add_bullet_box(slide, items, l, t, w, h,
                   font_size=15, color=BLACK, bullet_color=ORANGE,
                   title=None, title_size=17, title_color=DARK_BLUE):
    txb = slide.shapes.add_textbox(l, t, w, h)
    txb.word_wrap = True
    tf  = txb.text_frame
    tf.word_wrap = True
    if title:
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size  = Pt(title_size)
        run.font.bold  = True
        run.font.color.rgb = title_color
    for i, item in enumerate(items):
        if title or i > 0:
            p = tf.add_paragraph()
        else:
            p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        p.space_before = Pt(3)
        # bullet symbol
        r1 = p.add_run()
        r1.text = "▸  "
        r1.font.size  = Pt(font_size)
        r1.font.color.rgb = bullet_color
        r2 = p.add_run()
        r2.text = item
        r2.font.size  = Pt(font_size)
        r2.font.color.rgb = color
    return txb

def add_card(slide, l, t, w, h, bg_color, title, body_lines,
             title_size=16, body_size=13, icon=None):
    """Carte colorée avec titre + liste"""
    rect = add_rect(slide, l, t, w, h, bg_color)
    # Titre
    add_text_box(slide, title,
                 l + Inches(0.15), t + Inches(0.12),
                 w - Inches(0.3), Inches(0.4),
                 font_size=title_size, bold=True, color=WHITE)
    # Corps
    txb = slide.shapes.add_textbox(
        l + Inches(0.15), t + Inches(0.52),
        w - Inches(0.3), h - Inches(0.65))
    txb.word_wrap = True
    tf = txb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(body_lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(2)
        run = p.add_run()
        run.text = line
        run.font.size = Pt(body_size)
        run.font.color.rgb = WHITE

def footer(slide, text="QR Meeting — Solution de Gestion Intelligente des Réunions"):
    add_rect(slide, 0, SLIDE_H - Inches(0.35), SLIDE_W, Inches(0.35), DARK_BLUE)
    add_text_box(slide, text,
                 Inches(0.3), SLIDE_H - Inches(0.34),
                 Inches(10), Inches(0.33),
                 font_size=9, color=WHITE, align=PP_ALIGN.LEFT)
    add_text_box(slide, "Confidentiel – ARTCI © 2025",
                 SLIDE_W - Inches(3), SLIDE_H - Inches(0.34),
                 Inches(2.9), Inches(0.33),
                 font_size=9, color=MID_GREY, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 1 – COUVERTURE
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)

# Fond dégradé simulé : bande bleue haut
add_rect(sl, 0, 0, SLIDE_W, Inches(5.2), DARK_BLUE)
# Bande orange basse
add_rect(sl, 0, Inches(5.2), SLIDE_W, Inches(2.3), ORANGE)

# Logo ARTCI
if os.path.exists(LOGO_PATH):
    sl.shapes.add_picture(LOGO_PATH, Inches(0.5), Inches(0.35), width=Inches(3.2))

# Ligne décorative blanche
add_rect(sl, Inches(0.5), Inches(1.6), Inches(4), Inches(0.05), WHITE)

# Titre principal
add_text_box(sl, "QR MEETING",
             Inches(0.5), Inches(1.75), Inches(9), Inches(1.3),
             font_size=58, bold=True, color=WHITE)
add_text_box(sl, "Solution de Gestion Intelligente des Réunions",
             Inches(0.5), Inches(2.9), Inches(10), Inches(0.7),
             font_size=24, bold=False, color=RGBColor(0xCC, 0xD6, 0xFF))

add_text_box(sl, "Dématérialisez vos réunions · Tracez les présences · Pilotez vos actions",
             Inches(0.5), Inches(3.65), Inches(11), Inches(0.55),
             font_size=14, italic=True, color=RGBColor(0xAA, 0xBB, 0xDD))

# QR code déco
if os.path.exists(QR_PATH):
    sl.shapes.add_picture(QR_PATH, Inches(10.6), Inches(1.5), width=Inches(2.2))
    add_text_box(sl, "Scannez pour\nune démo live",
                 Inches(10.5), Inches(3.75), Inches(2.5), Inches(0.6),
                 font_size=9, color=RGBColor(0xAA, 0xBB, 0xDD), align=PP_ALIGN.CENTER)

# Bas de page orange
add_text_box(sl, "Autorité de Régulation des Télécommunications/TIC de Côte d'Ivoire",
             Inches(0.5), Inches(5.4), Inches(9), Inches(0.5),
             font_size=15, bold=True, color=WHITE)
add_text_box(sl, "Direction des Systèmes d'Information  ·  2025",
             Inches(0.5), Inches(5.9), Inches(8), Inches(0.5),
             font_size=12, color=WHITE)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 2 – PROBLÉMATIQUE
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, Inches(1.1), DARK_BLUE)
add_rect(sl, 0, Inches(1.1), SLIDE_W, SLIDE_H - Inches(1.1), LIGHT_GREY)
add_rect(sl, 0, Inches(1.05), SLIDE_W, Inches(0.08), ORANGE)
footer(sl)

add_text_box(sl, "Le constat", Inches(0.5), Inches(0.15), Inches(10), Inches(0.8),
             font_size=30, bold=True, color=WHITE)

problemes = [
    ("📋", "Feuilles d'émargement papier",
     "Perte de documents, falsifications possibles, archivage difficile"),
    ("⏱️", "Absence de traçabilité",
     "Aucun historique fiable des présences, impossible de contrôler rétrospectivement"),
    ("📧", "Invitations dispersées",
     "E-mails manuels, relances oubliées, pas de confirmation de lecture"),
    ("🗂️", "Suivi des décisions inexistant",
     "Les actions issues des réunions ne sont pas suivies, les délais dépassés"),
    ("📊", "Zéro visibilité managériale",
     "Pas de tableau de bord, pas de statistiques sur l'activité des réunions"),
]

for i, (ico, titre, desc) in enumerate(problemes):
    col = i % 2
    row = i // 2
    x = Inches(0.4 + col * 6.4)
    y = Inches(1.35 + row * 1.45)
    w = Inches(6.1)
    h = Inches(1.3)
    add_rect(sl, x, y, w, h, WHITE)
    add_rect(sl, x, y, Inches(0.08), h, ORANGE)
    add_text_box(sl, ico + "  " + titre,
                 x + Inches(0.2), y + Inches(0.1), w - Inches(0.3), Inches(0.45),
                 font_size=14, bold=True, color=DARK_BLUE)
    add_text_box(sl, desc,
                 x + Inches(0.2), y + Inches(0.55), w - Inches(0.3), Inches(0.65),
                 font_size=11.5, color=MID_GREY)

# Card résumé
add_rect(sl, Inches(0.4), Inches(5.55), Inches(12.5), Inches(0.8), ORANGE)
add_text_box(sl,
    "💡  Ces problèmes coûtent du temps, de l'argent et fragilisent la gouvernance de votre organisation",
    Inches(0.6), Inches(5.6), Inches(12), Inches(0.65),
    font_size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 3 – LA SOLUTION EN UN COUP D'ŒIL
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, Inches(1.1), DARK_BLUE)
add_rect(sl, 0, Inches(1.05), SLIDE_W, Inches(0.08), ORANGE)
add_rect(sl, 0, Inches(1.1), SLIDE_W, SLIDE_H - Inches(1.1), LIGHT_GREY)
footer(sl)

add_text_box(sl, "QR Meeting – La solution complète", Inches(0.5), Inches(0.15),
             Inches(10), Inches(0.8), font_size=30, bold=True, color=WHITE)

modules = [
    (ORANGE,     "📅",  "Gestion des\nRéunions",       ["Création guidée", "Calendrier intégré", "Statuts en temps réel"]),
    (DARK_BLUE,  "📲",  "Présence\npar QR Code",        ["Scan depuis mobile", "Formulaire intelligent", "Zéro papier"]),
    (GREEN,      "✍️",  "Signature\nNumérique",          ["Canvas tactile", "Intégrée au PDF", "Valeur légale"]),
    (TEAL,       "📝",  "Agenda\nStructuré",             ["Glisser-déposer", "Notes de séance", "Suivi des points"]),
    (RGBColor(0x6F,0x42,0xC1), "📬", "Invitations\nAutomatiques", ["Email + confirmation", "Relances auto", "Accepter/Décliner"]),
    (RGBColor(0xE8,0x30,0x45), "⚡", "Diligences\n& Actions",   ["Assignation nominative", "Suivi d'avancement", "Alertes dépassement"]),
    (RGBColor(0x14,0x85,0x75), "📊", "Tableaux de\nBord Live",  ["Stats temps réel", "Graphiques Chart.js", "Par direction"]),
    (RGBColor(0xC0,0x39,0x2B), "📄", "Exports\nPDF / Word",    ["Feuille d'émargement", "Avec signatures", "En un clic"]),
]

cols, rows = 4, 2
card_w = Inches(2.95)
card_h = Inches(2.3)
margin_x = Inches(0.35)
start_x = Inches(0.35)
start_y = Inches(1.25)

for idx, (color, icon, title, bullets) in enumerate(modules):
    c = idx % cols
    r = idx // cols
    x = start_x + c * (card_w + margin_x * 0.35)
    y = start_y + r * (card_h + Inches(0.15))
    add_rect(sl, x, y, card_w, card_h, color)
    # icon + titre
    add_text_box(sl, icon, x + Inches(0.15), y + Inches(0.1),
                 Inches(0.5), Inches(0.45), font_size=22, color=WHITE)
    add_text_box(sl, title, x + Inches(0.65), y + Inches(0.08),
                 card_w - Inches(0.8), Inches(0.7),
                 font_size=13.5, bold=True, color=WHITE)
    # bullets
    txb = sl.shapes.add_textbox(x + Inches(0.15), y + Inches(0.82),
                                 card_w - Inches(0.3), card_h - Inches(0.95))
    txb.word_wrap = True
    tf = txb.text_frame
    tf.word_wrap = True
    for bi, b in enumerate(bullets):
        p = tf.paragraphs[0] if bi == 0 else tf.add_paragraph()
        p.space_before = Pt(2)
        r1 = p.add_run(); r1.text = "✓ "; r1.font.size = Pt(11); r1.font.color.rgb = WHITE
        r2 = p.add_run(); r2.text = b;    r2.font.size = Pt(11); r2.font.color.rgb = WHITE


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 4 – FLUX DE PRÉSENCE PAR QR CODE
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, Inches(1.1), DARK_BLUE)
add_rect(sl, 0, Inches(1.05), SLIDE_W, Inches(0.08), ORANGE)
add_rect(sl, 0, Inches(1.1), SLIDE_W, SLIDE_H - Inches(1.1), LIGHT_GREY)
footer(sl)

add_text_box(sl, "Comment ça marche ? — Flux de présence", Inches(0.5), Inches(0.15),
             Inches(11), Inches(0.8), font_size=28, bold=True, color=WHITE)

steps = [
    (DARK_BLUE, "1", "Créer la\nRéunion",      "L'organisateur crée la réunion sur la plateforme"),
    (ORANGE,    "2", "QR Code\nGénéré",         "Un QR code unique est automatiquement généré"),
    (TEAL,      "3", "Afficher le\nQR Code",    "Projeté en salle ou imprimé sur convocation"),
    (GREEN,     "4", "Scan\nSmartphone",         "Chaque participant scanne avec son téléphone"),
    (RGBColor(0x6F,0x42,0xC1), "5", "Formulaire\nde Présence", "Saisie nom, prénom, organisation, fonction"),
    (RGBColor(0xE8,0x30,0x45), "6", "Signature\nNumérique",  "Signature tactile sur l'écran du téléphone"),
]

step_w = Inches(1.9)
step_h = Inches(2.8)
arrow_w = Inches(0.35)
total_w = len(steps) * step_w + (len(steps)-1) * arrow_w
start_x = (SLIDE_W - total_w) / 2
y_box = Inches(1.5)

for i, (color, num, title, desc) in enumerate(steps):
    x = start_x + i * (step_w + arrow_w)
    # Boîte
    add_rect(sl, x, y_box, step_w, step_h, color)
    # Numéro cercle
    add_rect(sl, x + Inches(0.65), y_box - Inches(0.28), Inches(0.6), Inches(0.6),
             WHITE)
    add_text_box(sl, num,
                 x + Inches(0.65), y_box - Inches(0.3), Inches(0.6), Inches(0.6),
                 font_size=18, bold=True, color=color, align=PP_ALIGN.CENTER)
    # Titre
    add_text_box(sl, title,
                 x + Inches(0.1), y_box + Inches(0.15),
                 step_w - Inches(0.2), Inches(0.8),
                 font_size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    # Description
    add_text_box(sl, desc,
                 x + Inches(0.1), y_box + Inches(1.0),
                 step_w - Inches(0.2), Inches(1.6),
                 font_size=10.5, color=WHITE, align=PP_ALIGN.CENTER)
    # Flèche
    if i < len(steps) - 1:
        ax = x + step_w + Inches(0.05)
        add_text_box(sl, "▶",
                     ax, y_box + Inches(1.1),
                     arrow_w, Inches(0.5),
                     font_size=18, color=ORANGE, align=PP_ALIGN.CENTER)

# QR code image
if os.path.exists(QR_PATH):
    sl.shapes.add_picture(QR_PATH, Inches(5.6), Inches(4.6), width=Inches(2.2))

add_text_box(sl,
    "Résultat : feuille d'émargement PDF avec signatures générée automatiquement — sans aucun papier",
    Inches(0.5), Inches(6.55), Inches(12.3), Inches(0.55),
    font_size=13, bold=True, color=DARK_BLUE, align=PP_ALIGN.CENTER)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 5 – SIGNATURE NUMÉRIQUE & EXPORT
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, Inches(1.1), DARK_BLUE)
add_rect(sl, 0, Inches(1.05), SLIDE_W, Inches(0.08), ORANGE)
add_rect(sl, 0, Inches(1.1), SLIDE_W, SLIDE_H - Inches(1.1), WHITE)
footer(sl)

add_text_box(sl, "Signature numérique & Export officiel",
             Inches(0.5), Inches(0.15), Inches(11), Inches(0.8),
             font_size=28, bold=True, color=WHITE)

# Gauche : Signature
add_rect(sl, Inches(0.4), Inches(1.2), Inches(5.8), Inches(5.45), LIGHT_GREY)
add_rect(sl, Inches(0.4), Inches(1.2), Inches(5.8), Inches(0.5), DARK_BLUE)
add_text_box(sl, "✍️  Signature Numérique",
             Inches(0.55), Inches(1.22), Inches(5.5), Inches(0.45),
             font_size=14, bold=True, color=WHITE)

sig_points = [
    "Capture de signature via canvas tactile (mobile/tablette)",
    "Compatible tous smartphones, sans application à installer",
    "Signature encodée et stockée de façon sécurisée",
    "Horodatage automatique de chaque signature",
    "Possibilité de passer la signature (optionnel)",
    "Intégrée directement dans la feuille d'émargement PDF",
]
for i, pt in enumerate(sig_points):
    add_text_box(sl, "▸  " + pt,
                 Inches(0.6), Inches(1.85) + i * Inches(0.62),
                 Inches(5.4), Inches(0.55),
                 font_size=12, color=DARK_BLUE)

# Droite : Export
add_rect(sl, Inches(6.55), Inches(1.2), Inches(6.35), Inches(2.5), LIGHT_GREY)
add_rect(sl, Inches(6.55), Inches(1.2), Inches(6.35), Inches(0.5), ORANGE)
add_text_box(sl, "📄  Export PDF — Feuille d'Émargement",
             Inches(6.7), Inches(1.22), Inches(6.1), Inches(0.45),
             font_size=13, bold=True, color=WHITE)

pdf_points = [
    "En-tête officiel avec logo ARTCI",
    "8 colonnes : N° · Nom · Prénom · Structure · Fonction · Contact · Email · Signature",
    "Signatures numériques intégrées dans le tableau",
    "Génération en un clic depuis l'interface",
]
for i, pt in enumerate(pdf_points):
    add_text_box(sl, "▸  " + pt,
                 Inches(6.7), Inches(1.85) + i * Inches(0.55),
                 Inches(6.1), Inches(0.5),
                 font_size=11.5, color=DARK_BLUE)

add_rect(sl, Inches(6.55), Inches(3.85), Inches(6.35), Inches(2.85), LIGHT_GREY)
add_rect(sl, Inches(6.55), Inches(3.85), Inches(6.35), Inches(0.5), TEAL)
add_text_box(sl, "📝  Export Word — Rapport complet",
             Inches(6.7), Inches(3.87), Inches(6.1), Inches(0.45),
             font_size=13, bold=True, color=WHITE)

word_points = [
    "Format .docx éditable pour personnalisation",
    "Mise en page professionnelle avec en-tête",
    "Tableau des participants avec signatures",
    "Compatible Microsoft Word & LibreOffice",
]
for i, pt in enumerate(word_points):
    add_text_box(sl, "▸  " + pt,
                 Inches(6.7), Inches(4.5) + i * Inches(0.55),
                 Inches(6.1), Inches(0.5),
                 font_size=11.5, color=DARK_BLUE)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 6 – AGENDA & DILIGENCES
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, Inches(1.1), DARK_BLUE)
add_rect(sl, 0, Inches(1.05), SLIDE_W, Inches(0.08), ORANGE)
add_rect(sl, 0, Inches(1.1), SLIDE_W, SLIDE_H - Inches(1.1), LIGHT_GREY)
footer(sl)

add_text_box(sl, "Agenda structuré & Suivi des diligences",
             Inches(0.5), Inches(0.15), Inches(11), Inches(0.8),
             font_size=28, bold=True, color=WHITE)

# Agenda
add_rect(sl, Inches(0.4), Inches(1.2), Inches(6.0), Inches(5.3), WHITE)
add_rect(sl, Inches(0.4), Inches(1.2), Inches(6.0), Inches(0.52), TEAL)
add_text_box(sl, "📝  Agenda Structuré",
             Inches(0.55), Inches(1.23), Inches(5.7), Inches(0.45),
             font_size=15, bold=True, color=WHITE)

agenda_items = [
    ("Réorganisation par glisser-déposer",
     "Modifiez l'ordre des points en drag-and-drop sans recharger la page"),
    ("Notes de séance par point",
     "Le secrétaire prend ses notes directement sur chaque point de l'ordre du jour"),
    ("Barre de progression visuelle",
     "Visualisez l'avancement de l'ordre du jour en temps réel"),
    ("Suivi des points traités",
     "Marquez chaque point comme traité/non-traité d'un clic"),
    ("Durée et responsable assignés",
     "Définissez le temps alloué et désignez un responsable pour chaque point"),
]
for i, (titre, desc) in enumerate(agenda_items):
    y = Inches(1.85) + i * Inches(0.9)
    add_rect(sl, Inches(0.45), y, Inches(5.85), Inches(0.82), LIGHT_GREY)
    add_rect(sl, Inches(0.45), y, Inches(0.06), Inches(0.82), TEAL)
    add_text_box(sl, titre,
                 Inches(0.62), y + Inches(0.05),
                 Inches(5.6), Inches(0.35),
                 font_size=12, bold=True, color=DARK_BLUE)
    add_text_box(sl, desc,
                 Inches(0.62), y + Inches(0.38),
                 Inches(5.6), Inches(0.38),
                 font_size=10.5, color=MID_GREY)

# Diligences
add_rect(sl, Inches(6.75), Inches(1.2), Inches(6.15), Inches(5.3), WHITE)
add_rect(sl, Inches(6.75), Inches(1.2), Inches(6.15), Inches(0.52), RGBColor(0xE8,0x30,0x45))
add_text_box(sl, "⚡  Diligences & Suivi des Actions",
             Inches(6.9), Inches(1.23), Inches(5.9), Inches(0.45),
             font_size=15, bold=True, color=WHITE)

diligences = [
    ("Assignation nominative", "Chaque action est assignée à une personne précise avec une échéance"),
    ("3 statuts de suivi", "En cours · Terminé · En retard — visualisation immédiate"),
    ("Commentaires de suivi", "Les responsables commentent l'avancement directement en ligne"),
    ("Tableau de bord personnel", "Chaque agent voit ses propres diligences sur son espace"),
    ("Export des diligences", "Export complet par réunion pour reporting et contrôle"),
    ("Statistiques par direction", "Vue agrégée du taux de réalisation par service"),
]
for i, (titre, desc) in enumerate(diligences):
    y = Inches(1.85) + i * Inches(0.9)
    add_rect(sl, Inches(6.8), y, Inches(6.05), Inches(0.82), LIGHT_GREY)
    add_rect(sl, Inches(6.8), y, Inches(0.06), Inches(0.82), RGBColor(0xE8,0x30,0x45))
    add_text_box(sl, titre,
                 Inches(6.97), y + Inches(0.05),
                 Inches(5.8), Inches(0.35),
                 font_size=12, bold=True, color=DARK_BLUE)
    add_text_box(sl, desc,
                 Inches(6.97), y + Inches(0.38),
                 Inches(5.8), Inches(0.38),
                 font_size=10.5, color=MID_GREY)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 7 – TABLEAU DE BORD & STATISTIQUES
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, Inches(1.1), DARK_BLUE)
add_rect(sl, 0, Inches(1.05), SLIDE_W, Inches(0.08), ORANGE)
add_rect(sl, 0, Inches(1.1), SLIDE_W, SLIDE_H - Inches(1.1), LIGHT_GREY)
footer(sl)

add_text_box(sl, "Tableaux de bord & Statistiques en temps réel",
             Inches(0.5), Inches(0.15), Inches(11), Inches(0.8),
             font_size=28, bold=True, color=WHITE)

# KPI cards row
kpis = [
    (DARK_BLUE, "Réunions\naujourd'hui",   "Suivi instantané des réunions du jour"),
    (ORANGE,    "Participants\nprésents",  "Compteur en temps réel des émargements"),
    (TEAL,      "Réunions\ncette semaine", "Vue hebdomadaire consolidée"),
    (GREEN,     "Taux de\nprésence",       "Indicateur clé de performance"),
]
for i, (color, titre, desc) in enumerate(kpis):
    x = Inches(0.4 + i * 3.2)
    add_rect(sl, x, Inches(1.28), Inches(3.0), Inches(1.5), color)
    add_text_box(sl, titre,
                 x + Inches(0.15), Inches(1.35),
                 Inches(2.7), Inches(0.7),
                 font_size=14, bold=True, color=WHITE)
    add_text_box(sl, desc,
                 x + Inches(0.15), Inches(2.0),
                 Inches(2.7), Inches(0.65),
                 font_size=10, color=WHITE)

# Features section
features = [
    ("📈", "Graphique répartition par statut",
     "Donut Chart.js interactif — Planifiée · En cours · Terminée · Annulée"),
    ("🏢", "Statistiques par direction/service",
     "Nombre de participants, taux de présence, exports CSV par organisation"),
    ("📅", "Prochaines réunions",
     "Tableau des réunions à venir avec nombre d'inscrits"),
    ("👥", "Statistiques des utilisateurs",
     "Répartition par rôle, activité par agent"),
    ("🔄", "Mise à jour automatique",
     "Polling AJAX toutes les 30 secondes — données toujours fraîches"),
    ("📧", "Récapitulatif hebdomadaire",
     "Email automatique chaque lundi aux administrateurs"),
]
for i, (ico, titre, desc) in enumerate(features):
    col = i % 3
    row = i // 3
    x = Inches(0.4 + col * 4.3)
    y = Inches(3.05 + row * 1.55)
    add_rect(sl, x, y, Inches(4.1), Inches(1.4), WHITE)
    add_rect(sl, x, y, Inches(0.07), Inches(1.4), ORANGE)
    add_text_box(sl, ico + "  " + titre,
                 x + Inches(0.2), y + Inches(0.1),
                 Inches(3.8), Inches(0.45),
                 font_size=12.5, bold=True, color=DARK_BLUE)
    add_text_box(sl, desc,
                 x + Inches(0.2), y + Inches(0.55),
                 Inches(3.8), Inches(0.75),
                 font_size=10.5, color=MID_GREY)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 8 – NOTIFICATIONS & AUTOMATISATIONS
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, Inches(1.1), DARK_BLUE)
add_rect(sl, 0, Inches(1.05), SLIDE_W, Inches(0.08), ORANGE)
add_rect(sl, 0, Inches(1.1), SLIDE_W, SLIDE_H - Inches(1.1), WHITE)
footer(sl)

add_text_box(sl, "Notifications automatiques & Communication",
             Inches(0.5), Inches(0.15), Inches(11), Inches(0.8),
             font_size=28, bold=True, color=WHITE)

notifs = [
    (ORANGE,    "📨",  "Invitation à la réunion",
     "Envoi automatique d'e-mails d'invitation avec lien de réponse\n(Accepter / Décliner). Confirmation immédiate à l'organisateur."),
    (TEAL,      "⏰",  "Rappel J-1 automatique",
     "La veille de chaque réunion, un e-mail de rappel est envoyé\nautomatiquement à tous les participants inscrits."),
    (GREEN,     "✅",  "Confirmation de présence",
     "Après enregistrement, le participant reçoit un e-mail de confirmation\navec un lien d'annulation si besoin."),
    (DARK_BLUE, "❌",  "Notification d'annulation",
     "Si la réunion est annulée, tous les participants inscrits reçoivent\nimmédiatement un e-mail d'information."),
    (RGBColor(0x6F,0x42,0xC1), "📋", "Envoi du compte-rendu",
     "En un clic, le secrétaire envoie le compte-rendu par e-mail\nà tous les participants de la réunion."),
    (RGBColor(0xC0,0x39,0x2B), "📊", "Récapitulatif hebdomadaire",
     "Chaque lundi matin, un bilan de la semaine écoulée est\nenvoyé automatiquement aux administrateurs."),
]

for i, (color, ico, titre, desc) in enumerate(notifs):
    col = i % 2
    row = i // 2
    x = Inches(0.4 + col * 6.4)
    y = Inches(1.25 + row * 1.75)
    add_rect(sl, x, y, Inches(6.1), Inches(1.6), LIGHT_GREY)
    add_rect(sl, x, y, Inches(0.6), Inches(1.6), color)
    add_text_box(sl, ico,
                 x + Inches(0.1), y + Inches(0.55),
                 Inches(0.4), Inches(0.5),
                 font_size=20, color=WHITE, align=PP_ALIGN.CENTER)
    add_text_box(sl, titre,
                 x + Inches(0.72), y + Inches(0.1),
                 Inches(5.25), Inches(0.4),
                 font_size=13, bold=True, color=DARK_BLUE)
    add_text_box(sl, desc,
                 x + Inches(0.72), y + Inches(0.5),
                 Inches(5.25), Inches(1.0),
                 font_size=11, color=MID_GREY)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 9 – SÉCURITÉ & ACCÈS
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, Inches(1.1), DARK_BLUE)
add_rect(sl, 0, Inches(1.05), SLIDE_W, Inches(0.08), ORANGE)
add_rect(sl, 0, Inches(1.1), SLIDE_W, SLIDE_H - Inches(1.1), LIGHT_GREY)
footer(sl)

add_text_box(sl, "Sécurité, rôles & intégration",
             Inches(0.5), Inches(0.15), Inches(11), Inches(0.8),
             font_size=28, bold=True, color=WHITE)

# Rôles
add_rect(sl, Inches(0.4), Inches(1.2), Inches(4.0), Inches(5.35), WHITE)
add_rect(sl, Inches(0.4), Inches(1.2), Inches(4.0), Inches(0.52), DARK_BLUE)
add_text_box(sl, "👥  Profils utilisateurs",
             Inches(0.55), Inches(1.23), Inches(3.8), Inches(0.45),
             font_size=14, bold=True, color=WHITE)

roles = [
    ("🔴 Administrateur", ["Accès complet", "Gestion des utilisateurs", "Tous les tableaux de bord", "Configuration système"]),
    ("🟡 Secrétaire",     ["Création de réunions", "Gestion de l'agenda", "Envoi des CR", "Saisie des diligences"]),
    ("🟢 Participant",    ["Enregistrement présence", "Tableau de bord personnel", "Consultation des réunions", "Suivi de ses diligences"]),
]
y_pos = Inches(1.85)
for role, perms in roles:
    add_text_box(sl, role,
                 Inches(0.55), y_pos, Inches(3.7), Inches(0.4),
                 font_size=12.5, bold=True, color=DARK_BLUE)
    for p in perms:
        y_pos += Inches(0.37)
        add_text_box(sl, "  ▸ " + p,
                     Inches(0.6), y_pos, Inches(3.7), Inches(0.35),
                     font_size=11, color=MID_GREY)
    y_pos += Inches(0.45)

# Sécurité
add_rect(sl, Inches(4.7), Inches(1.2), Inches(4.0), Inches(5.35), WHITE)
add_rect(sl, Inches(4.7), Inches(1.2), Inches(4.0), Inches(0.52), ORANGE)
add_text_box(sl, "🔐  Sécurité",
             Inches(4.85), Inches(1.23), Inches(3.8), Inches(0.45),
             font_size=14, bold=True, color=WHITE)

sec_items = [
    ("HTTPS / SSL", "Chiffrement TLS 1.2 et 1.3 en production"),
    ("Tokens UUID", "Chaque lien de présence est unique et non réutilisable"),
    ("Changement mdp obligatoire", "À la première connexion d'un nouvel utilisateur"),
    ("Sessions sécurisées", "Cookies sécurisés (Secure + HttpOnly)"),
    ("Protection CSRF", "Tous les formulaires protégés contre les attaques"),
    ("Logs d'accès", "Journalisation de toutes les actions critiques"),
    ("Déploiement Docker", "Isolation des services, pas de ports exposés"),
]
for i, (titre, desc) in enumerate(sec_items):
    y = Inches(1.82) + i * Inches(0.68)
    add_rect(sl, Inches(4.75), y, Inches(3.9), Inches(0.62), LIGHT_GREY)
    add_rect(sl, Inches(4.75), y, Inches(0.06), Inches(0.62), ORANGE)
    add_text_box(sl, titre,
                 Inches(4.93), y + Inches(0.04),
                 Inches(3.65), Inches(0.28),
                 font_size=11.5, bold=True, color=DARK_BLUE)
    add_text_box(sl, desc,
                 Inches(4.93), y + Inches(0.3),
                 Inches(3.65), Inches(0.28),
                 font_size=10, color=MID_GREY)

# Intégration
add_rect(sl, Inches(9.0), Inches(1.2), Inches(3.9), Inches(5.35), WHITE)
add_rect(sl, Inches(9.0), Inches(1.2), Inches(3.9), Inches(0.52), TEAL)
add_text_box(sl, "🔗  Intégrations",
             Inches(9.15), Inches(1.23), Inches(3.7), Inches(0.45),
             font_size=14, bold=True, color=WHITE)

integ = [
    ("Active Directory (LDAP)", "Authentification via l'annuaire d'entreprise"),
    ("Office 365 / Exchange", "Envoi d'e-mails via SMTP institutionnel"),
    ("PWA — Application Mobile", "Installable sur iOS et Android sans app store"),
    ("API REST", "Endpoints JSON pour intégration avec d'autres SI"),
    ("Docker / Kubernetes", "Déploiement cloud-ready et scalable"),
    ("PostgreSQL", "Base de données robuste et performante"),
    ("Redis + Celery", "Tâches asynchrones pour les notifications"),
]
for i, (titre, desc) in enumerate(integ):
    y = Inches(1.82) + i * Inches(0.68)
    add_rect(sl, Inches(9.05), y, Inches(3.8), Inches(0.62), LIGHT_GREY)
    add_rect(sl, Inches(9.05), y, Inches(0.06), Inches(0.62), TEAL)
    add_text_box(sl, titre,
                 Inches(9.23), y + Inches(0.04),
                 Inches(3.55), Inches(0.28),
                 font_size=11.5, bold=True, color=DARK_BLUE)
    add_text_box(sl, desc,
                 Inches(9.23), y + Inches(0.3),
                 Inches(3.55), Inches(0.28),
                 font_size=10, color=MID_GREY)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 10 – AVANTAGES CONCURRENTIELS
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, Inches(1.1), DARK_BLUE)
add_rect(sl, 0, Inches(1.05), SLIDE_W, Inches(0.08), ORANGE)
add_rect(sl, 0, Inches(1.1), SLIDE_W, SLIDE_H - Inches(1.1), WHITE)
footer(sl)

add_text_box(sl, "Pourquoi choisir QR Meeting ?",
             Inches(0.5), Inches(0.15), Inches(11), Inches(0.8),
             font_size=28, bold=True, color=WHITE)

avantages = [
    ("🇨🇮", "Conçu pour l'Afrique",
     "Interface en français, conforme aux réalités\nlocales, adapté aux connexions limitées (PWA)"),
    ("⚡", "Déploiement rapide",
     "Opérationnel en moins d'une journée\nvia Docker, sans infrastructure complexe"),
    ("📱", "100% Mobile",
     "Aucune application à installer.\nLe participant scanne et c'est tout."),
    ("🔒", "Données souveraines",
     "Hébergement sur vos propres serveurs.\nVos données ne quittent jamais votre SI."),
    ("🎨", "Personnalisable",
     "Logo, nom de l'organisation, domaine\npropre, couleurs adaptables"),
    ("💰", "Coût total maîtrisé",
     "Solution open-source, zéro licence.\nUniquement le coût d'hébergement."),
]

for i, (ico, titre, desc) in enumerate(avantages):
    col = i % 3
    row = i // 2
    x = Inches(0.4 + col * 4.3)
    y = Inches(1.28 + row * 2.6)
    add_rect(sl, x, y, Inches(4.0), Inches(2.35), LIGHT_GREY)
    add_text_box(sl, ico,
                 x + Inches(0.15), y + Inches(0.1),
                 Inches(0.7), Inches(0.6),
                 font_size=28, color=DARK_BLUE)
    add_rect(sl, x + Inches(0.15), y + Inches(0.75), Inches(1.5), Inches(0.05), ORANGE)
    add_text_box(sl, titre,
                 x + Inches(0.15), y + Inches(0.85),
                 Inches(3.7), Inches(0.45),
                 font_size=14, bold=True, color=DARK_BLUE)
    add_text_box(sl, desc,
                 x + Inches(0.15), y + Inches(1.3),
                 Inches(3.7), Inches(0.9),
                 font_size=11.5, color=MID_GREY)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 11 – ARCHITECTURE TECHNIQUE
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, Inches(1.1), DARK_BLUE)
add_rect(sl, 0, Inches(1.05), SLIDE_W, Inches(0.08), ORANGE)
add_rect(sl, 0, Inches(1.1), SLIDE_W, SLIDE_H - Inches(1.1), LIGHT_GREY)
footer(sl)

add_text_box(sl, "Architecture technique",
             Inches(0.5), Inches(0.15), Inches(11), Inches(0.8),
             font_size=28, bold=True, color=WHITE)

# Couches architecture
layers = [
    (RGBColor(0x17,0x53,0x8A), "COUCHE PRÉSENTATION",
     "Navigateur Web + Smartphone", "Bootstrap 5 · Chart.js · SortableJS · Signature Pad · PWA"),
    (ORANGE, "COUCHE APPLICATION",
     "Serveur Django 5.2 / Python 3.12",
     "Gunicorn · Django REST · Celery (tâches async) · python-decouple"),
    (TEAL,   "COUCHE DONNÉES",
     "Base de données & Cache",
     "PostgreSQL 15 · Redis 7 · Sessions sécurisées"),
    (DARK_BLUE, "INFRASTRUCTURE",
     "Conteneurisation & Réseau",
     "Docker Compose · Nginx (SSL/TLS) · Volumes persistants"),
]

for i, (color, layer, subtitle, tech) in enumerate(layers):
    y = Inches(1.3) + i * Inches(1.38)
    add_rect(sl, Inches(0.4), y, Inches(12.5), Inches(1.25), WHITE)
    add_rect(sl, Inches(0.4), y, Inches(2.1), Inches(1.25), color)
    add_text_box(sl, layer,
                 Inches(0.42), y + Inches(0.35),
                 Inches(2.0), Inches(0.6),
                 font_size=9.5, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text_box(sl, subtitle,
                 Inches(2.65), y + Inches(0.08),
                 Inches(4.0), Inches(0.45),
                 font_size=13, bold=True, color=DARK_BLUE)
    add_text_box(sl, tech,
                 Inches(2.65), y + Inches(0.6),
                 Inches(9.7), Inches(0.55),
                 font_size=11, color=MID_GREY)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 12 – DÉPLOIEMENT & MISE EN ŒUVRE
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, Inches(1.1), DARK_BLUE)
add_rect(sl, 0, Inches(1.05), SLIDE_W, Inches(0.08), ORANGE)
add_rect(sl, 0, Inches(1.1), SLIDE_W, SLIDE_H - Inches(1.1), WHITE)
footer(sl)

add_text_box(sl, "Déploiement & Mise en œuvre",
             Inches(0.5), Inches(0.15), Inches(11), Inches(0.8),
             font_size=28, bold=True, color=WHITE)

phases = [
    (DARK_BLUE, "Semaine 1", "Analyse & Installation",
     ["Audit de l'infrastructure existante", "Installation Docker sur le serveur", "Configuration SSL et nom de domaine", "Paramétrage de la base de données"]),
    (ORANGE,    "Semaine 2", "Configuration & Intégration",
     ["Intégration Active Directory / LDAP", "Configuration messagerie SMTP", "Personnalisation (logo, nom organisation)", "Import des utilisateurs et directions"]),
    (TEAL,      "Semaine 3", "Formation & Tests",
     ["Formation administrateurs (4h)", "Formation secrétaires (3h)", "Formation participants (1h)", "Tests end-to-end avec données réelles"]),
    (GREEN,     "Semaine 4", "Go Live & Support",
     ["Mise en production supervisée", "Accompagnement lors des premières réunions", "Ajustements post-démarrage", "Documentation remise à l'équipe DSI"]),
]

for i, (color, periode, titre, items) in enumerate(phases):
    x = Inches(0.35 + i * 3.2)
    y = Inches(1.25)
    w = Inches(3.0)
    add_rect(sl, x, y, w, Inches(0.55), color)
    add_text_box(sl, periode,
                 x + Inches(0.1), y + Inches(0.05),
                 w - Inches(0.2), Inches(0.45),
                 font_size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_rect(sl, x, y + Inches(0.55), w, Inches(4.8), LIGHT_GREY)
    add_rect(sl, x, y + Inches(0.55), w, Inches(0.5), RGBColor(0xEE, 0xEE, 0xEE))
    add_text_box(sl, titre,
                 x + Inches(0.1), y + Inches(0.57),
                 w - Inches(0.2), Inches(0.45),
                 font_size=12, bold=True, color=DARK_BLUE, align=PP_ALIGN.CENTER)
    for j, item in enumerate(items):
        add_text_box(sl, "▸  " + item,
                     x + Inches(0.15), y + Inches(1.2) + j * Inches(0.85),
                     w - Inches(0.2), Inches(0.75),
                     font_size=11, color=MID_GREY)

add_rect(sl, Inches(0.35), Inches(6.35), Inches(12.6), Inches(0.75), DARK_BLUE)
add_text_box(sl,
    "🎯  Prérequis minimal : un serveur Linux (4 Go RAM, 2 vCPU, 50 Go SSD) · Python 3.12 · Docker Compose",
    Inches(0.5), Inches(6.4), Inches(12.3), Inches(0.65),
    font_size=12.5, bold=True, color=WHITE, align=PP_ALIGN.CENTER)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 13 – CAS D'USAGE / RÉFÉRENCES
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, Inches(1.1), DARK_BLUE)
add_rect(sl, 0, Inches(1.05), SLIDE_W, Inches(0.08), ORANGE)
add_rect(sl, 0, Inches(1.1), SLIDE_W, SLIDE_H - Inches(1.1), LIGHT_GREY)
footer(sl)

add_text_box(sl, "Cas d'usage & secteurs cibles",
             Inches(0.5), Inches(0.15), Inches(11), Inches(0.8),
             font_size=28, bold=True, color=WHITE)

secteurs = [
    ("🏛️", "Institutions publiques",
     ["Conseils de Ministres", "Comités de direction", "Assemblées générales", "Commissions inter-ministérielles"]),
    ("🏢", "Entreprises privées",
     ["CODIR / COMEX", "Réunions de projet", "Assemblées d'actionnaires", "Réunions de service"]),
    ("🎓", "Éducation & Recherche",
     ["Conseils pédagogiques", "Soutenances de thèse", "Comités scientifiques", "Réunions de labo"]),
    ("🏥", "Santé",
     ["Staff médical", "Comités d'éthique", "Réunions de direction", "Formations continues"]),
    ("⚖️", "Justice & Régulation",
     ["Audiences et comités", "Organes délibérants", "Instances de régulation", "Commissions d'enquête"]),
    ("🌍", "Organisations internationales",
     ["Conférences régionales", "Sommets africains", "Groupes de travail", "Comités techniques"]),
]

for i, (ico, titre, cas) in enumerate(secteurs):
    col = i % 3
    row = i // 3
    x = Inches(0.4 + col * 4.3)
    y = Inches(1.25 + row * 2.8)
    add_rect(sl, x, y, Inches(4.0), Inches(2.55), WHITE)
    add_rect(sl, x, y, Inches(4.0), Inches(0.52), DARK_BLUE)
    add_text_box(sl, ico + "  " + titre,
                 x + Inches(0.15), y + Inches(0.05),
                 Inches(3.7), Inches(0.45),
                 font_size=13, bold=True, color=WHITE)
    for j, c in enumerate(cas):
        add_text_box(sl, "▸  " + c,
                     x + Inches(0.15), y + Inches(0.62) + j * Inches(0.47),
                     Inches(3.7), Inches(0.43),
                     font_size=11, color=MID_GREY)


# ═══════════════════════════════════════════════════════════════════════════════
#  SLIDE 14 – CONCLUSION / APPEL À L'ACTION
# ═══════════════════════════════════════════════════════════════════════════════
sl = blank_slide(prs)
add_rect(sl, 0, 0, SLIDE_W, SLIDE_H, DARK_BLUE)
add_rect(sl, 0, Inches(4.6), SLIDE_W, Inches(2.9), ORANGE)

if os.path.exists(LOGO_PATH):
    sl.shapes.add_picture(LOGO_PATH, Inches(0.5), Inches(0.3), width=Inches(2.8))

add_rect(sl, Inches(0.5), Inches(1.5), Inches(4), Inches(0.05), WHITE)
add_text_box(sl, "Passez à l'action",
             Inches(0.5), Inches(1.65), Inches(9), Inches(1.1),
             font_size=46, bold=True, color=WHITE)
add_text_box(sl,
    "QR Meeting est prêt à transformer la gestion de vos réunions.",
    Inches(0.5), Inches(2.75), Inches(10.5), Inches(0.65),
    font_size=18, color=RGBColor(0xCC, 0xD6, 0xFF))
add_text_box(sl,
    "Dématérialisé · Sécurisé · Tracé · Automatisé · Made in Côte d'Ivoire",
    Inches(0.5), Inches(3.35), Inches(10.5), Inches(0.55),
    font_size=14, italic=True, color=RGBColor(0xAA, 0xBB, 0xDD))

ctas = [
    ("🌐", "Démo en ligne",    "meeting.artci.ci"),
    ("📧", "Contact",           "dsi@artci.ci"),
    ("📞", "Téléphone",          "+225 27 22 54 27 80"),
]
for i, (ico, label, val) in enumerate(ctas):
    x = Inches(0.5 + i * 4.2)
    add_rect(sl, x, Inches(4.75), Inches(3.8), Inches(1.55), WHITE)
    add_text_box(sl, ico + "  " + label,
                 x + Inches(0.15), Inches(4.82),
                 Inches(3.5), Inches(0.5),
                 font_size=14, bold=True, color=ORANGE)
    add_text_box(sl, val,
                 x + Inches(0.15), Inches(5.32),
                 Inches(3.5), Inches(0.75),
                 font_size=13, color=DARK_BLUE)

if os.path.exists(QR_PATH):
    sl.shapes.add_picture(QR_PATH, Inches(11.3), Inches(4.6), width=Inches(1.9))

add_text_box(sl,
    "Autorité de Régulation des Télécommunications/TIC de Côte d'Ivoire  —  www.artci.ci",
    Inches(0.5), Inches(6.75), Inches(12.3), Inches(0.45),
    font_size=10, color=WHITE, align=PP_ALIGN.CENTER)


# ─── Sauvegarde ──────────────────────────────────────────────────────────────
prs.save(OUT_PATH)
print(f"✅  Présentation générée : {OUT_PATH}")
print(f"    Nombre de diapositives : {len(prs.slides)}")
