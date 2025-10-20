from django.http import HttpResponse
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.shared import RGBColor
import io
from datetime import datetime



def generate_presence_report(reunion, format_type='pdf'):
    """Génère un rapport de présence dans le format spécifié"""
    
    presences = reunion.presence_requests.filter(status='confirmed')
    
    if format_type == 'pdf':
        return generate_pdf_report(reunion, presences)
    elif format_type == 'excel':
        return generate_excel_report(reunion, presences)
    elif format_type == 'word':
        return generate_word_report(reunion, presences)
    
    return None


def generate_pdf_report(reunion, presences):
    """Génère un rapport PDF de présence avec colonnes auto-ajustées"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.8*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        textColor=colors.HexColor('#FF6B35'),
        alignment=1
    )

    story = []
    title = Paragraph(f"Liste de Présence - {reunion.titre}", title_style)
    story.append(title)
    story.append(Spacer(1, 12))

    info_data = [
        ['Date:', reunion.date_debut.strftime('%d/%m/%Y à %H:%M')],
        ['Lieu:', reunion.lieu],
        ['Organisateur:', f"{reunion.organisateur.first_name} {reunion.organisateur.last_name}"],
        ['Nombre de participants:', str(presences.count())],
    ]
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    if presences:
        data = [['N°', 'Nom', 'Prénom', 'Structure/Organisation', 'Fonction', 'Contact', 'Email']]
        for i, presence in enumerate(presences, 1):
            data.append([
                str(i),
                presence.nom or '—',
                presence.prenom or '—',
                presence.organisation or '—',
                presence.fonction or '—',
                presence.contact or '—',
                presence.email or '—',
            ])

        # 🔹 Calcul dynamique de la largeur de chaque colonne
        max_chars = [max(len(str(row[i])) for row in data) for i in range(len(data[0]))]
        total_chars = sum(max_chars)
        page_width = 7.3 * inch  # largeur disponible environ
        colWidths = [(chars / total_chars) * page_width for chars in max_chars]

        table = Table(data, repeatRows=1, colWidths=colWidths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF6B35')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
        ]))
        story.append(table)

    story.append(Spacer(1, 36))
    signature_data = [
        ['Généré le:', datetime.now().strftime('%d/%m/%Y à %H:%M')],
        ['Par:', 'QR Meeting System'],
        ['Signature organisateur:', ''],
    ]
    signature_table = Table(signature_data, colWidths=[2*inch, 4*inch])
    story.append(signature_table)

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="presence_{reunion.titre.replace(" ", "_")}.pdf"'
    return response


def generate_excel_report(reunion, presences):
    """Génère un rapport Excel de présence avec colonnes auto-ajustées"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Liste de Présence"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="FF6B35", end_color="FF6B35", fill_type="solid")
    center = Alignment(horizontal="center", vertical="center")
    wrap = Alignment(wrap_text=True, vertical="center")

    ws["A1"] = f"Liste de Présence - {reunion.titre}"
    ws["A1"].font = Font(bold=True, size=16, color="FF6B35")
    ws.merge_cells("A1:G1")

    info = [
        ("Date:", reunion.date_debut.strftime('%d/%m/%Y à %H:%M')),
        ("Lieu:", reunion.lieu),
        ("Organisateur:", f"{reunion.organisateur.first_name} {reunion.organisateur.last_name}"),
        ("Nombre de participants:", presences.count()),
    ]
    for i, (label, value) in enumerate(info, start=3):
        ws[f"A{i}"] = label
        ws[f"A{i}"].font = Font(bold=True)
        ws[f"B{i}"] = value

    headers = ['N°', 'Nom', 'Prénom', 'Structure/Organisation', 'Fonction', 'Contact', 'Email']
    ws.append([])
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=8, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center

    start_row = 9
    for i, presence in enumerate(presences, 1):
        ws.append([
            i,
            presence.nom or '—',
            presence.prenom or '—',
            presence.organisation or '—',
            presence.fonction or '—',
            presence.contact or '—',
            presence.email or '—',
        ])

    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for row in ws.iter_rows(min_row=8, max_row=ws.max_row, min_col=1, max_col=7):
        for cell in row:
            cell.border = border
            if cell.column == 1:
                cell.alignment = center
            else:
                cell.alignment = wrap

    # 🔹 Ajustement automatique des largeurs selon le texte réel
    for col in ws.columns:
        max_length = 0
        col_letter = col[0].column_letter
        for cell in col:
            if cell.value:
                length = len(str(cell.value))
                if length > max_length:
                    max_length = length
        adjusted_width = (max_length + 2)
        ws.column_dimensions[col_letter].width = adjusted_width

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = f'attachment; filename="presence_{reunion.titre.replace(' ', '_')}.xlsx"'
    return response


def generate_word_report(reunion, presences):
    """Génère un rapport Word de présence avec adaptation automatique des colonnes"""
    # Création d’un nouveau document Word
    doc = Document()
    
    # -------------------------------
    # CONFIGURATION DES MARGES
    # -------------------------------
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)
    
    # -------------------------------
    # TITRE DU DOCUMENT
    # -------------------------------
    title = doc.add_heading(f'Liste de Présence - {reunion.titre}', 0)
    title_format = title.runs[0]
    title_format.font.color.rgb = RGBColor(255, 107, 53)
    
    # -------------------------------
    # INFORMATIONS DE LA RÉUNION
    # -------------------------------
    doc.add_paragraph()
    info_table = doc.add_table(rows=4, cols=2)
    info_table.style = 'Light Grid Accent 1'
    
    info_data = [
        ('Date:', reunion.date_debut.strftime('%d/%m/%Y à %H:%M')),
        ('Lieu:', reunion.lieu),
        ('Organisateur:', f"{reunion.organisateur.first_name} {reunion.organisateur.last_name}"),
        ('Nombre de participants:', str(presences.count())),
    ]
    
    for i, (label, value) in enumerate(info_data):
        cell_label = info_table.cell(i, 0)
        cell_value = info_table.cell(i, 1)
        cell_label.text = label
        cell_value.text = value
        # Mise en gras des intitulés
        cell_label.paragraphs[0].runs[0].font.bold = True
    
    # -------------------------------
    # LISTE DES PARTICIPANTS
    # -------------------------------
    doc.add_paragraph()
    doc.add_heading('Liste des Participants', level=2)
    
    if presences:
        table = doc.add_table(rows=1, cols=7)
        table.style = 'Light Grid Accent 1'
        
        headers = ['N°', 'Nom', 'Prénom', 'Structure/Organisation', 'Fonction', 'Contact', 'Email']
        header_cells = table.rows[0].cells
        
        # En-têtes en gras
        for i, header in enumerate(headers):
            p = header_cells[i].paragraphs[0]
            run = p.add_run(header)
            run.bold = True
        
        # Ajout des participants
        for i, presence in enumerate(presences, start=1):
            row_cells = table.add_row().cells
            row_cells[0].text = str(i)
            row_cells[1].text = presence.nom or '—'
            row_cells[2].text = presence.prenom or '—'
            row_cells[3].text = presence.organisation or '—'
            row_cells[4].text = presence.fonction or '—'
            row_cells[5].text = presence.contact or '—'
            row_cells[6].text = presence.email or '—'
        
        # -------------------------------
        # AJUSTEMENT AUTOMATIQUE DES LARGEURS
        # -------------------------------
        table.autofit = True  # Laisse Word ajuster automatiquement la largeur
        
        # Supprime toute contrainte de largeur fixe
        for column in table.columns:
            for cell in column.cells:
                cell.width = None
        
        # Ajoute un léger espacement dans les cellules
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.space_after = Pt(3)
                    paragraph.paragraph_format.space_before = Pt(3)
    
    else:
        doc.add_paragraph('Aucun participant confirmé.')
    
    # -------------------------------
    # TABLEAU DE SIGNATURE / MÉTADONNÉES
    # -------------------------------
    doc.add_paragraph()
    doc.add_paragraph()
    
    signature_table = doc.add_table(rows=3, cols=2)
    signature_table.style = 'Light Grid Accent 1'
    
    signature_data = [
        ('Généré le:', datetime.now().strftime('%d/%m/%Y à %H:%M')),
        ('Par:', 'QR Meeting System'),
        ('Signature organisateur:', ''),
    ]
    
    for i, (label, value) in enumerate(signature_data):
        cell_label = signature_table.cell(i, 0)
        cell_value = signature_table.cell(i, 1)
        cell_label.text = label
        cell_value.text = value
        cell_label.paragraphs[0].runs[0].font.bold = True
    
    # -------------------------------
    # EXPORT DU DOCUMENT EN MÉMOIRE
    # -------------------------------
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    # -------------------------------
    # RÉPONSE HTTP POUR TÉLÉCHARGEMENT
    # -------------------------------
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    
    response['Content-Disposition'] = (
        f'attachment; filename="presence_{reunion.titre.replace(" ", "_")}_'
        f'{datetime.now().strftime("%Y%m%d_%H%M")}.docx"'
    )
    
    return response


def send_compte_rendu_email(compte_rendu):
    """Envoie le compte-rendu aux participants confirmés"""
    reunion = compte_rendu.reunion
    participants = reunion.presence_requests.filter(status='confirmed')
    
    if not participants.exists():
        print("❌ Aucun participant confirmé pour l'envoi du compte-rendu")
        return False
    
    subject = f"Compte-rendu - {reunion.titre}"
    
    # URL de base pour les liens
    protocol = 'https' if getattr(settings, 'SECURE_SSL_REDIRECT', False) else 'http'
    if hasattr(settings, 'SITE_URL') and settings.SITE_URL:
        base_url = settings.SITE_URL.rstrip('/')
    else:
        if hasattr(settings, 'ALLOWED_HOSTS') and settings.ALLOWED_HOSTS:
            host = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS[0] != '*' else '196.216.227.105'
        else:
            host = '196.216.227.105'
        base_url = f"{protocol}://{host}"
    
    # Créer le contexte pour le template
    context = {
        'reunion': reunion,
        'compte_rendu': compte_rendu,
        'participant_count': participants.count(),
        'base_url': base_url,
    }
    
    # Rendu du template HTML
    try:
        html_content = render_to_string('reunions/email_compte_rendu.html', context)
    except Exception as e:
        print(f"⚠️ Erreur template HTML compte-rendu: {e}")
        html_content = None
    
    text_content = f"""
Bonjour,

Vous trouverez en pièce jointe le compte-rendu de la réunion "{reunion.titre}" 
qui s'est tenue le {reunion.date_debut.strftime('%d/%m/%Y à %H:%M')}.

Détails de la réunion :
- Lieu : {reunion.lieu}
- Organisateur : {reunion.organisateur.first_name} {reunion.organisateur.last_name}
- Nombre de participants : {participants.count()}

Document joint : {compte_rendu.titre} (Version {compte_rendu.version})
Créé par : {compte_rendu.cree_par.first_name} {compte_rendu.cree_par.last_name}

Cordialement,
{compte_rendu.cree_par.first_name} {compte_rendu.cree_par.last_name}
Secrétaire de la réunion

---
Cet email a été envoyé automatiquement par QR Meeting.
"""
    
    # Préparer la liste des emails
    recipient_list = [p.email for p in participants]
    
    try:
        print(f"📧 Tentative d'envoi compte-rendu à {len(recipient_list)} participants")
        
        # Créer l'email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list
        )
        
        # Attacher la version HTML si disponible
        if html_content:
            email.attach_alternative(html_content, "text/html")
        
        # Attacher le fichier du compte-rendu
        if compte_rendu.fichier:
            try:
                if compte_rendu.fichier.name and hasattr(compte_rendu.fichier, 'path'):
                    import os
                    if os.path.exists(compte_rendu.fichier.path):
                        email.attach_file(compte_rendu.fichier.path)
                        print(f"📎 Fichier attaché: {compte_rendu.fichier.name}")
                    else:
                        print(f"⚠️ Fichier introuvable: {compte_rendu.fichier.path}")
                else:
                    print(f"⚠️ Aucun fichier associé au compte-rendu")
            except Exception as e:
                print(f"⚠️ Erreur lors de l'attachement du fichier: {e}")
        
        # Envoyer l'email
        result = email.send()
        
        print(f"✅ Compte-rendu envoyé avec succès à {len(recipient_list)} participants (result: {result})")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi du compte-rendu: {e}")
        print(f"   Destinataires: {recipient_list}")
        print(f"   From: {settings.DEFAULT_FROM_EMAIL}")
        return False