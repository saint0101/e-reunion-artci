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
from openpyxl.styles import Font, Alignment, PatternFill
from docx import Document
from docx.shared import Inches
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
    """Génère un rapport PDF de présence avec nouveaux champs"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.8*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        textColor=colors.HexColor('#FF6B35'),
        alignment=1  # Center
    )
    
    # Contenu
    story = []
    
    # Titre
    title = Paragraph(f"Liste de Présence - {reunion.titre}", title_style)
    story.append(title)
    story.append(Spacer(1, 12))
    
    # Informations de la réunion
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
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 24))
    
    # Tableau des participants avec nouveaux champs
    if presences:
        # En-têtes dans l'ordre demandé : N°, Nom, Prénom, Structure, Fonction, Contact, Email
        data = [['N°', 'Nom', 'Prénom', 'Structure/Organisation', 'Fonction', 'Contact', 'Email']]
        
        # Données
        for i, presence in enumerate(presences, 1):
            data.append([
                str(i),
                presence.nom or '—',
                presence.prenom or '—',
                presence.organisation or '—',
                presence.fonction or '—',
                presence.contact or '—',
                presence.email,
            ])
        
        # Colonnes adaptées pour 7 colonnes
        table = Table(data, repeatRows=1, colWidths=[0.5*inch, 1.2*inch, 1.2*inch, 1.5*inch, 1.3*inch, 1*inch, 1.8*inch])
        table.setStyle(TableStyle([
            # En-tête
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF6B35')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            
            # Corps du tableau
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Numérotation centrée
            
            # Alternance de couleurs
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
            
            # Ajustement du texte pour éviter le débordement
            ('WORDWRAP', (0, 0), (-1, -1), True),
        ]))
        
        story.append(table)
    else:
        no_participants = Paragraph("Aucun participant confirmé", styles['Normal'])
        story.append(no_participants)
    
    # Signature
    story.append(Spacer(1, 48))
    signature_data = [
        ['Généré le:', datetime.now().strftime('%d/%m/%Y à %H:%M')],
        ['Par:', 'QR Meeting System'],
        ['Signature organisateur:', ''],
    ]
    
    signature_table = Table(signature_data, colWidths=[2*inch, 4*inch])
    signature_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    story.append(signature_table)
    
    # Génération du PDF
    doc.build(story)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="presence_{reunion.titre.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf"'
    
    return response

def generate_excel_report(reunion, presences):
    """Génère un rapport Excel de présence avec nouveaux champs"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Liste de Présence"
    
    # Styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="FF6B35", end_color="FF6B35", fill_type="solid")
    center_alignment = Alignment(horizontal="center", vertical="center")
    wrap_alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    
    # Titre et informations
    ws['A1'] = f"Liste de Présence - {reunion.titre}"
    ws['A1'].font = Font(bold=True, size=16, color="FF6B35")
    ws.merge_cells('A1:G1')
    
    ws['A3'] = "Date:"
    ws['B3'] = reunion.date_debut.strftime('%d/%m/%Y à %H:%M')
    ws['A4'] = "Lieu:"
    ws['B4'] = reunion.lieu
    ws['A5'] = "Organisateur:"
    ws['B5'] = f"{reunion.organisateur.first_name} {reunion.organisateur.last_name}"
    ws['A6'] = "Nombre de participants:"
    ws['B6'] = presences.count()
    
    # Mettre en gras les labels
    for row in range(3, 7):
        ws[f'A{row}'].font = Font(bold=True)
    
    # En-têtes du tableau dans l'ordre demandé
    headers = ['N°', 'Nom', 'Prénom', 'Structure/Organisation', 'Fonction', 'Contact', 'Email']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=8, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_alignment
    
    # Données
    for row, presence in enumerate(presences, 9):
        ws.cell(row=row, column=1, value=row-8).alignment = center_alignment
        ws.cell(row=row, column=2, value=presence.nom or '—').alignment = wrap_alignment
        ws.cell(row=row, column=3, value=presence.prenom or '—').alignment = wrap_alignment
        ws.cell(row=row, column=4, value=presence.organisation or '—').alignment = wrap_alignment
        ws.cell(row=row, column=5, value=presence.fonction or '—').alignment = wrap_alignment
        ws.cell(row=row, column=6, value=presence.contact or '—').alignment = wrap_alignment
        ws.cell(row=row, column=7, value=presence.email).alignment = wrap_alignment
    
    # Ajustement automatique des colonnes avec largeurs optimisées
    column_widths = [8, 20, 20, 25, 20, 15, 30]  # Largeurs personnalisées
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[chr(64 + i)].width = width
    
    # Ajuster la hauteur des lignes pour le contenu
    for row in range(9, 9 + presences.count()):
        ws.row_dimensions[row].height = 20
    
    # Ajouter des bordures
    from openpyxl.styles import Border, Side
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    for row in range(8, 9 + presences.count()):
        for col in range(1, 8):
            ws.cell(row=row, column=col).border = thin_border
    
    # Sauvegarde
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="presence_{reunion.titre.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    
    return response

def generate_word_report(reunion, presences):
    """Génère un rapport Word de présence avec nouveaux champs"""
    doc = Document()
    
    # Configuration des marges
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)
    
    # Titre
    title = doc.add_heading(f'Liste de Présence - {reunion.titre}', 0)
    title_format = title.runs[0]
    title_format.font.color.rgb = RGBColor(255, 107, 53)
    
    # Informations de la réunion
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
        info_table.cell(i, 0).text = label
        info_table.cell(i, 1).text = value
        info_table.cell(i, 0).paragraphs[0].runs[0].font.bold = True
    
    # Tableau des participants
    doc.add_paragraph()
    doc.add_heading('Liste des Participants', level=2)
    
    if presences:
        # Tableau avec 7 colonnes dans l'ordre demandé
        table = doc.add_table(rows=1, cols=7)
        table.style = 'Light Grid Accent 1'
        
        # En-têtes
        headers = ['N°', 'Nom', 'Prénom', 'Structure/Organisation', 'Fonction', 'Contact', 'Email']
        for i, header in enumerate(headers):
            cell = table.cell(0, i)
            cell.text = header
            cell.paragraphs[0].runs[0].font.bold = True
        
        # Données
        presences_list = list(presences)
        for i, presence in enumerate(presences_list):
            row_cells = table.add_row().cells
            row_cells[0].text = str(i + 1)
            row_cells[1].text = presence.nom or '—'
            row_cells[2].text = presence.prenom or '—'
            row_cells[3].text = presence.organisation or '—'
            row_cells[4].text = presence.fonction or '—'
            row_cells[5].text = presence.contact or '—'
            row_cells[6].text = presence.email
        
        # Ajuster la largeur des colonnes
        from docx.shared import Cm
        table.columns[0].width = Cm(1)    # N°
        table.columns[1].width = Cm(2.5)  # Nom
        table.columns[2].width = Cm(2.5)  # Prénom
        table.columns[3].width = Cm(3.5)  # Structure
        table.columns[4].width = Cm(3)    # Fonction
        table.columns[5].width = Cm(2.5)  # Contact
        table.columns[6].width = Cm(4)    # Email
        
    else:
        doc.add_paragraph('Aucun participant confirmé')
    
    # Signature
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
        signature_table.cell(i, 0).text = label
        signature_table.cell(i, 1).text = value
        signature_table.cell(i, 0).paragraphs[0].runs[0].font.bold = True
    
    # Sauvegarde
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="presence_{reunion.titre.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M")}.docx"'
    
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