from django.http import HttpResponse
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
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
    """Génère un rapport PDF de présence avec mention légale en pied de page."""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=0.8 * inch,
        bottomMargin=1.5 * inch,  # Augmenté pour le pied de page
        leftMargin=0.4 * inch,
        rightMargin=0.4 * inch
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        textColor=colors.HexColor('#FF6B35'),
        alignment=1  # Centré
    )

    story = []

    # --- TITRE ---
    title = Paragraph(f"Liste de Présence - {reunion.titre}", title_style)
    story.append(title)
    story.append(Spacer(1, 12))

    # --- INFORMATIONS DE LA RÉUNION ---
    info_data = [
        ['Date :', reunion.date_debut.strftime('%d/%m/%Y à %H:%M')],
        ['Lieu :', reunion.lieu],
        ['Organisateur :', f"{reunion.organisateur.first_name} {reunion.organisateur.last_name}"],
        ['Nombre de participants :', str(presences.count())],
    ]
    info_table = Table(info_data, colWidths=[2 * inch, 4 * inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 24))

    # --- TABLEAU DES PARTICIPANTS ---
    if presences:
        headers = ['N°', 'Nom', 'Prénom', 'Structure/Organisation', 'Fonction', 'Contact', 'Email']

        # Style pour les cellules
        cell_style = ParagraphStyle(
            name='CellStyle',
            fontName='Helvetica',
            fontSize=8,
            leading=10,
        )

        # Construire les données avec Paragraph (pour retour à la ligne)
        data = [headers]
        for i, presence in enumerate(presences, 1):
            data.append([
                Paragraph(str(i), cell_style),
                Paragraph(presence.nom or '—', cell_style),
                Paragraph(presence.prenom or '—', cell_style),
                Paragraph(presence.organisation or '—', cell_style),
                Paragraph(presence.fonction or '—', cell_style),
                Paragraph(presence.contact or '—', cell_style),
                Paragraph(presence.email or '—', cell_style),
            ])

        # Largeur totale disponible sur la page (A4 = 8.27 in - marges)
        total_width = 8.27 * inch - (0.8 * inch)
        # Répartition des colonnes (proportion selon importance du contenu)
        col_widths = [
            0.4 * inch,  # N°
            1.5 * inch,  # Nom
            1.5 * inch,  # Prénom
            1.6 * inch,  # Structure/Organisation
            1.0 * inch,  # Fonction
            1.0 * inch,  # Contact
            1.7 * inch,  # Email
        ]

        # Ajustement pour que le total tienne sur la page
        scale = total_width / sum(col_widths)
        col_widths = [w * scale for w in col_widths]

        # Création du tableau
        table = Table(data, repeatRows=1, colWidths=col_widths)

        # Style visuel
        table.setStyle(TableStyle([
            # En-têtes
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF6B35')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

            # Corps
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),

            # Bordures visibles
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),

            # Lignes alternées
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [colors.white, colors.HexColor('#F8F9FA')]),
        ]))

        story.append(table)
    else:
        story.append(Paragraph("Aucun participant confirmé.", styles['Normal']))

    # --- ESPACE ENTRE LE TABLEAU ET LE PIED DE PAGE ---
    story.append(Spacer(1, 48))

    # --- FONCTION POUR AJOUTER LE PIED DE PAGE ---
    def add_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        
        # Position du pied de page (bas de page)
        page_width = A4[0]
        page_height = A4[1]
        footer_y = 0.4 * inch
        
        # Ligne de séparation horizontale
        canvas_obj.setStrokeColor(colors.HexColor('#CCCCCC'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(0.4 * inch, footer_y + 1.0 * inch, page_width - 0.4 * inch, footer_y + 1.0 * inch)
        
        # Style pour la mention légale
        legal_style_footer = ParagraphStyle(
            'LegalNoticeFooter',
            fontName='Helvetica',
            fontSize=7,
            leading=8.5,
            textColor=colors.HexColor('#555555'),
            alignment=4,  # Justifié
        )
        
        # Texte de la mention légale
        legal_text = """Vos données personnelles sont collectées et traitées par la Direction de la Protection des Données Personnelles de l'ARTCI, dans le cadre de la présente rencontre exclusivement aux fins de vous identifier. Conformément à la loi n°2013-450 du 19 juin 2013, vous pouvez exercer vos droits d'accès, d'opposition, de rectification et de suppression auprès de ladite Direction."""
        
        # Créer le paragraphe de mention légale
        legal_para = Paragraph(legal_text, legal_style_footer)
        available_width = page_width - (0.8 * inch)
        w, h = legal_para.wrap(available_width, 2 * inch)
        legal_para.drawOn(canvas_obj, 0.4 * inch, footer_y + 0.55 * inch)
        
        # Informations de signature
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.HexColor('#333333'))
        
        signature_y = footer_y + 0.15 * inch
        canvas_obj.drawString(0.4 * inch, signature_y, f"Généré le : {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
        canvas_obj.drawString(0.4 * inch, signature_y - 0.15 * inch, "Par : QR Meeting System")
        
        # Signature organisateur à droite
        canvas_obj.drawRightString(page_width - 0.4 * inch, signature_y, "Signature organisateur : _______________")
        
        canvas_obj.restoreState()

    # --- EXPORT PDF avec pied de page ---
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="presence_{reunion.titre.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf"'
    )

    return response


def generate_excel_report(reunion, presences):
    """Génère un rapport Excel de présence avec mention légale en pied de page"""
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
    column_widths = [8, 20, 20, 25, 20, 15, 30]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[chr(64 + i)].width = width
    
    # Ajuster la hauteur des lignes pour le contenu
    for row in range(9, 9 + presences.count()):
        ws.row_dimensions[row].height = 20
    
    # Ajouter des bordures
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    for row in range(8, 9 + presences.count()):
        for col in range(1, 8):
            ws.cell(row=row, column=col).border = thin_border
    
    # --- ESPACE ENTRE LE TABLEAU ET LE PIED DE PAGE ---
    space_row = 9 + presences.count() + 2
    
    # --- PIED DE PAGE ---
    footer_start_row = space_row + 1
    
    # Ligne de séparation
    ws.merge_cells(f'A{footer_start_row}:G{footer_start_row}')
    separator_cell = ws[f'A{footer_start_row}']
    separator_cell.value = ""
    separator_cell.border = Border(top=Side(style='thin', color='CCCCCC'))
    
    # Mention légale (sans titre)
    legal_row = footer_start_row + 1
    ws.merge_cells(f'A{legal_row}:G{legal_row + 1}')
    legal_cell = ws[f'A{legal_row}']
    legal_text = (
        "Vos données personnelles sont collectées et traitées par la Direction de la Protection des Données Personnelles de l'ARTCI, "
        "dans le cadre de la présente rencontre exclusivement aux fins de vous identifier. "
        "Conformément à la loi n°2013-450 du 19 juin 2013, vous pouvez exercer vos droits d'accès, d'opposition, "
        "de rectification et de suppression auprès de ladite Direction."
    )
    legal_cell.value = legal_text
    legal_cell.font = Font(size=8, italic=True, color="555555")
    legal_cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    legal_cell.fill = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid")
    ws.row_dimensions[legal_row].height = 50
    
    # Ligne vide
    empty_row = legal_row + 2
    
    # Informations de signature
    signature_row = empty_row + 1
    ws[f'A{signature_row}'] = f"Généré le : {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
    ws[f'A{signature_row}'].font = Font(size=9)
    
    ws[f'A{signature_row + 1}'] = "Par : QR Meeting System"
    ws[f'A{signature_row + 1}'].font = Font(size=9)
    
    ws[f'E{signature_row}'] = "Signature organisateur :"
    ws[f'E{signature_row}'].font = Font(size=9, bold=True)
    ws.merge_cells(f'F{signature_row}:G{signature_row}')
    ws[f'F{signature_row}'].value = "_______________"
    
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
    """Génère un rapport Word de présence avec mention légale en pied de page"""
    doc = Document()
    
    # Configuration des marges
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(1.2)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)
        
        # Configurer le pied de page
        footer = section.footer
        
        # Ligne de séparation dans le pied de page
        footer_para_separator = footer.paragraphs[0]
        footer_para_separator.text = ""
        footer_para_separator.paragraph_format.border_top = True
        
        # Mention légale dans le pied de page
        legal_para = footer.add_paragraph()
        legal_text = (
            "Vos données personnelles sont collectées et traitées par la Direction de la Protection des Données Personnelles de l'ARTCI, "
            "dans le cadre de la présente rencontre exclusivement aux fins de vous identifier. "
            "Conformément à la loi n°2013-450 du 19 juin 2013, vous pouvez exercer vos droits d'accès, d'opposition, "
            "de rectification et de suppression auprès de ladite Direction."
        )
        legal_run = legal_para.add_run(legal_text)
        legal_run.font.size = Pt(8)
        legal_run.font.italic = True
        legal_run.font.color.rgb = RGBColor(85, 85, 85)
        legal_para.paragraph_format.left_indent = Inches(0.3)
        legal_para.paragraph_format.right_indent = Inches(0.3)
        legal_para.paragraph_format.space_after = Pt(6)
        
        # Fond gris clair pour la mention légale
        shading_elm = OxmlElement('w:shd')
        shading_elm.set(qn('w:fill'), 'F8F9FA')
        legal_para._element.get_or_add_pPr().append(shading_elm)
        
        # Table de signature dans le pied de page
        footer.add_paragraph()  # Espace
        signature_table = footer.add_table(rows=2, cols=2)
        
        # Première ligne
        signature_table.cell(0, 0).text = f"Généré le : {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
        signature_table.cell(0, 0).paragraphs[0].runs[0].font.size = Pt(9)
        
        signature_table.cell(0, 1).text = "Signature organisateur : _______________"
        signature_table.cell(0, 1).paragraphs[0].runs[0].font.size = Pt(9)
        signature_table.cell(0, 1).paragraphs[0].runs[0].font.bold = True
        signature_table.cell(0, 1).paragraphs[0].alignment = 2  # Aligné à droite
        
        # Deuxième ligne
        signature_table.cell(1, 0).text = "Par : QR Meeting System"
        signature_table.cell(1, 0).paragraphs[0].runs[0].font.size = Pt(9)
        
        # Supprimer les bordures du tableau de signature
        for row in signature_table.rows:
            for cell in row.cells:
                cell._element.get_or_add_tcPr().append(
                    OxmlElement('w:tcBorders')
                )
    
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
        hdr_cells = table.rows[0].cells
        for i, header in enumerate(headers):
            hdr_cells[i].text = header
            hdr_cells[i].paragraphs[0].runs[0].font.bold = True
        
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

        table.autofit = True
        
    else:
        doc.add_paragraph('Aucun participant confirmé')
    
    # Espace entre le tableau et le pied de page (le pied de page est automatique)
    doc.add_paragraph()
    doc.add_paragraph()
    
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