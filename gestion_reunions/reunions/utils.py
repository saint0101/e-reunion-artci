
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
    """Génère un rapport PDF de présence"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)
    
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
    
    # Tableau des participants
    if presences:
        # En-têtes
        data = [['N°', 'Email', 'Nom', 'Prénom', 'Organisation', 'Heure de confirmation']]
        
        # Données
        for i, presence in enumerate(presences, 1):
            data.append([
                str(i),
                presence.email,
                presence.nom or '—',
                presence.prenom or '—',
                presence.organisation or '—',
                presence.confirmed_at.strftime('%H:%M') if presence.confirmed_at else '—'
            ])
        
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            # En-tête
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF6B35')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            
            # Corps du tableau
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Numérotation centrée
            
            # Alternance de couleurs
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
        ]))
        
        story.append(table)
    else:
        no_participants = Paragraph("Aucun participant confirmé", styles['Normal'])
        story.append(no_participants)
    
    # Signature
    story.append(Spacer(1, 48))
    signature_data = [
        ['Généré le:', datetime.now().strftime('%d/%m/%Y à %H:%M')],
        ['Signature:', ''],
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
    response['Content-Disposition'] = f'attachment; filename="presence_{reunion.titre}_{datetime.now().strftime("%Y%m%d")}.pdf"'
    
    return response

def generate_excel_report(reunion, presences):
    """Génère un rapport Excel de présence"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Liste de Présence"
    
    # Styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="FF6B35", end_color="FF6B35", fill_type="solid")
    center_alignment = Alignment(horizontal="center", vertical="center")
    
    # Titre et informations
    ws['A1'] = f"Liste de Présence - {reunion.titre}"
    ws['A1'].font = Font(bold=True, size=16)
    ws.merge_cells('A1:F1')
    
    ws['A3'] = "Date:"
    ws['B3'] = reunion.date_debut.strftime('%d/%m/%Y à %H:%M')
    ws['A4'] = "Lieu:"
    ws['B4'] = reunion.lieu
    ws['A5'] = "Organisateur:"
    ws['B5'] = f"{reunion.organisateur.first_name} {reunion.organisateur.last_name}"
    ws['A6'] = "Nombre de participants:"
    ws['B6'] = presences.count()
    
    # En-têtes du tableau
    headers = ['N°', 'Email', 'Nom', 'Prénom', 'Organisation', 'Heure de confirmation']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=8, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_alignment
    
    # Données
    for row, presence in enumerate(presences, 9):
        ws.cell(row=row, column=1, value=row-8)
        ws.cell(row=row, column=2, value=presence.email)
        ws.cell(row=row, column=3, value=presence.nom or '—')
        ws.cell(row=row, column=4, value=presence.prenom or '—')
        ws.cell(row=row, column=5, value=presence.organisation or '—')
        ws.cell(row=row, column=6, value=presence.confirmed_at.strftime('%H:%M') if presence.confirmed_at else '—')
    
    # Ajustement automatique des colonnes
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Sauvegarde
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="presence_{reunion.titre}_{datetime.now().strftime("%Y%m%d")}.xlsx"'
    
    return response

def generate_word_report(reunion, presences):
    """Génère un rapport Word de présence"""
    doc = Document()
    
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
    doc.add_heading('Participants', level=2)
    
    if presences:
        table = doc.add_table(rows=1, cols=6)
        table.style = 'Light Grid Accent 1'
        
        # En-têtes
        headers = ['N°', 'Email', 'Nom', 'Prénom', 'Organisation', 'Heure de confirmation']
        for i, header in enumerate(headers):
            cell = table.cell(0, i)
            cell.text = header
            cell.paragraphs[0].runs[0].font.bold = True
        
        # Données
        presences_list = list(presences)
        for i, presence in enumerate(presences_list):
            row_cells = table.add_row().cells
            row_cells[0].text = str(i + 1)
            row_cells[1].text = presence.email
            row_cells[2].text = presence.nom or '—'
            row_cells[3].text = presence.prenom or '—'
            row_cells[4].text = presence.organisation or '—'
            row_cells[5].text = presence.confirmed_at.strftime('%H:%M') if presence.confirmed_at else '—'
    else:
        doc.add_paragraph('Aucun participant confirmé')
    
    # Signature
    doc.add_paragraph()
    doc.add_paragraph()
    doc.add_paragraph(f'Généré le {datetime.now().strftime("%d/%m/%Y à %H:%M")}')
    
    # Sauvegarde
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="presence_{reunion.titre}_{datetime.now().strftime("%Y%m%d")}.docx"'
    
    return response

def send_compte_rendu_email(compte_rendu):
    """Envoie le compte-rendu aux participants confirmés"""
    reunion = compte_rendu.reunion
    participants = reunion.presence_requests.filter(status='confirmed')
    
    if not participants.exists():
        return False
    
    subject = f"Compte-rendu - {reunion.titre}"
    
    # Créer le contexte pour le template
    context = {
        'reunion': reunion,
        'compte_rendu': compte_rendu,
        'participant_count': participants.count(),
    }
    
    # Rendu du template HTML
    html_content = render_to_string('reunions/email_compte_rendu.html', context)
    text_content = f"""
    Bonjour,
    
    Vous trouverez en pièce jointe le compte-rendu de la réunion "{reunion.titre}" 
    qui s'est tenue le {reunion.date_debut.strftime('%d/%m/%Y à %H:%M')}.
    
    Cordialement,
    {compte_rendu.cree_par.first_name} {compte_rendu.cree_par.last_name}
    """
    
    # Préparer la liste des emails
    recipient_list = [p.email for p in participants]
    
    try:
        # Créer l'email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list
        )
        
        # Attacher la version HTML
        email.attach_alternative(html_content, "text/html")
        
        # Attacher le fichier du compte-rendu
        if compte_rendu.fichier:
            email.attach_file(compte_rendu.fichier.path)
        
        # Envoyer l'email
        email.send()
        return True
        
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email: {e}")
        return False