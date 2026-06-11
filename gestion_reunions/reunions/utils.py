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
from docx.shared import Inches, Pt, RGBColor, Cm
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
    """
    Feuille de présence officielle ARTCI.
    En-tête institutionnel, tableau signataire avec case Signature vide.
    """
    import os
    from reportlab.platypus import Image as RLImage
    from django.conf import settings as django_settings

    ORANGE   = colors.HexColor('#FF6B35')
    DARK     = colors.HexColor('#1A1A2E')
    LIGHT_BG = colors.HexColor('#FFF8F4')
    GREY_BG  = colors.HexColor('#F2F2F2')
    WHITE    = colors.white
    BORDER   = colors.HexColor('#CCCCCC')

    PAGE_W, PAGE_H = A4
    LEFT = RIGHT = 0.5 * inch
    TOP  = 0.5 * inch
    BOT  = 1.6 * inch   # espace pour le pied de page légal
    CONTENT_W = PAGE_W - LEFT - RIGHT

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=TOP, bottomMargin=BOT,
        leftMargin=LEFT, rightMargin=RIGHT,
    )

    styles = getSampleStyleSheet()

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    cell_s  = ps('Cell',  fontName='Helvetica', fontSize=7, leading=9)
    cell_sm = ps('CellSm', fontName='Helvetica', fontSize=6.5, leading=8.5,
                 wordWrap='CJK')   # CJK = coupe à n'importe quel caractère (emails sans espaces)
    hdr_s   = ps('Hdr',   fontName='Helvetica-Bold', fontSize=7.5, leading=9,
                 textColor=WHITE, alignment=1)
    info_k  = ps('InfoK', fontName='Helvetica-Bold', fontSize=9, leading=12)
    info_v  = ps('InfoV', fontName='Helvetica',      fontSize=9, leading=12)
    sub_s   = ps('Sub',   fontName='Helvetica-Oblique', fontSize=8,
                 textColor=colors.HexColor('#666666'), leading=10)
    inst_s  = ps('Inst',  fontName='Helvetica-Oblique', fontSize=7.5,
                 textColor=colors.HexColor('#444444'), leading=10)

    story = []

    # ── 1. EN-TÊTE INSTITUTIONNEL ────────────────────────────────────────────
    logo_path = os.path.join(
        str(django_settings.BASE_DIR), '..', 'static', 'img', 'artci_logo.png'
    )
    logo_path = os.path.normpath(logo_path)

    INST_NAME = "Autorité de Régulation des Télécommunications/TIC de Côte d'Ivoire"

    if os.path.exists(logo_path):
        logo_img = RLImage(logo_path, width=2.6 * inch, height=0.52 * inch)
        ref_cell = Paragraph(
            f"Réf. : ARTCI/QRM/{reunion.pk:04d}<br/>"
            f"Date : {reunion.date_debut.strftime('%d/%m/%Y')}",
            ps('Ref', fontName='Helvetica', fontSize=8,
               textColor=colors.HexColor('#555555'), alignment=2),
        )
        # Ligne logo + référence
        header_t = Table(
            [[logo_img, '', ref_cell],
             [Paragraph(INST_NAME, inst_s), '', '']],
            colWidths=[2.8*inch, CONTENT_W - 2.8*inch - 1.4*inch, 1.4*inch],
        )
        header_t.setStyle(TableStyle([
            ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ('ALIGN',         (2,0), (2,0), 'RIGHT'),
            ('LINEBELOW',     (0,0), (-1,0), 0.5, BORDER),
            ('LINEBELOW',     (0,1), (-1,1), 1,   ORANGE),
            ('SPAN',          (0,1), (1,1)),           # sous-titre sur 2 cols
            ('TOPPADDING',    (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(header_t)
    else:
        story.append(Paragraph(
            f"ARTCI — {INST_NAME}",
            ps('ArtciTitle', fontName='Helvetica-Bold', fontSize=11,
               textColor=ORANGE, spaceAfter=4),
        ))

    story.append(Spacer(1, 8))

    # ── 2. TITRE DU DOCUMENT ─────────────────────────────────────────────────
    title_t = Table(
        [[Paragraph("FEUILLE DE PRÉSENCE", ps('DocTitle',
            fontName='Helvetica-Bold', fontSize=14,
            textColor=WHITE, alignment=1))]],
        colWidths=[CONTENT_W],
    )
    title_t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), ORANGE),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(title_t)
    story.append(Spacer(1, 10))

    # ── 3. BLOC INFORMATIONS RÉUNION ─────────────────────────────────────────
    sec  = reunion.secretaire
    sec_name = (f"{sec.first_name} {sec.last_name}".strip()
                if sec else "—")
    org_name = (f"{reunion.organisateur.first_name} {reunion.organisateur.last_name}".strip())

    info_data = [
        [Paragraph('Objet :', info_k),
         Paragraph(reunion.titre, ps('TitreVal', fontName='Helvetica-Bold',
                   fontSize=9, leading=12, textColor=DARK)),
         Paragraph('Lieu :', info_k),
         Paragraph(reunion.lieu, info_v)],
        [Paragraph('Date :', info_k),
         Paragraph(reunion.date_debut.strftime('%A %d %B %Y'), info_v),
         Paragraph('Heure :', info_k),
         Paragraph(f"{reunion.date_debut.strftime('%H:%M')} — {reunion.date_fin.strftime('%H:%M')}", info_v)],
        [Paragraph('Organisateur :', info_k),
         Paragraph(org_name, info_v),
         Paragraph('Secrétaire :', info_k),
         Paragraph(sec_name, info_v)],
        [Paragraph('Participants confirmés :', info_k),
         Paragraph(str(presences.count()), ps('NbPart', fontName='Helvetica-Bold',
                   fontSize=9, textColor=ORANGE)),
         Paragraph('', info_k), Paragraph('', info_v)],
    ]
    cw1 = 1.3 * inch
    cw2 = CONTENT_W / 2 - cw1
    info_t = Table(info_data, colWidths=[cw1, cw2, cw1, cw2])
    info_t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), LIGHT_BG),
        ('BOX',           (0,0), (-1,-1), 0.8, ORANGE),
        ('INNERGRID',     (0,0), (-1,-1), 0.3, BORDER),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(info_t)
    story.append(Spacer(1, 14))

    # ── 4. TABLEAU DE SIGNATURES ─────────────────────────────────────────────
    # Colonnes : N° | Nom | Prénom | Structure/Organisation | Fonction | Contact | Email | Signature
    SIGN_ROW_H = 0.55 * inch   # hauteur suffisante pour contenu wrappé + signature

    col_widths = [
        0.27 * inch,   # N°
        0.90 * inch,   # Nom
        0.90 * inch,   # Prénom
        1.15 * inch,   # Structure/Organisation
        1.05 * inch,   # Fonction
        0.82 * inch,   # Contact
        1.30 * inch,   # Email
        0.87 * inch,   # Signature
    ]
    # Ajuster proportionnellement pour tenir sur la page
    scale = CONTENT_W / sum(col_widths)
    col_widths = [w * scale for w in col_widths]

    headers = ['N°', 'Nom', 'Prénom', 'Structure/<br/>Organisation',
               'Fonction', 'Contact', 'Email', 'Signature']
    header_row = [Paragraph(h, hdr_s) for h in headers]
    data = [header_row]

    cnum_s = ps('Cnum', fontName='Helvetica', fontSize=7, alignment=1)

    for i, p in enumerate(presences, 1):
        # Colonne signature : image numérique si disponible, sinon case vide
        if p.signature:
            try:
                sig_w = col_widths[7] * 0.88
                sig_h = min(sig_w * 0.36, SIGN_ROW_H * 0.80)
                sig_cell = RLImage(p.signature.path, width=sig_w, height=sig_h)
            except Exception:
                sig_cell = Paragraph('', cell_s)
        else:
            sig_cell = Paragraph('', cell_s)

        row = [
            Paragraph(str(i),                  cnum_s),
            Paragraph(p.nom or '—',            cell_s),
            Paragraph(p.prenom or '—',         cell_s),
            Paragraph(p.organisation or '—',   cell_s),
            Paragraph(p.fonction or '—',       cell_s),
            Paragraph(p.contact or '—',        cell_s),
            Paragraph(p.email or '—',          cell_sm),
            sig_cell,
        ]
        data.append(row)

    #sign_table = Table(data, colWidths=col_widths,
    #                  rowHeights=[0.32 * inch] + [SIGN_ROW_H] * len(presences),
    #                   repeatRows=1)
    
    sign_table = Table(
        data,
        colWidths=col_widths,
        repeatRows=1
    )
    
    sign_table.setStyle(TableStyle([
        # En-tête
        ('BACKGROUND',    (0,0), (-1,0), ORANGE),
        ('TEXTCOLOR',     (0,0), (-1,0), WHITE),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,0), 7.5),
        ('ALIGN',         (0,0), (-1,0), 'CENTER'),
        ('VALIGN',        (0,0), (-1,0), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,0), 4),
        ('BOTTOMPADDING', (0,0), (-1,0), 4),
        # Corps
        ('FONTNAME',      (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE',      (0,1), (-1,-1), 7),
        ('VALIGN',        (0,1), (-1,-1), 'TOP'),
        ('TOPPADDING',    (0,1), (-1,-1), 6),
        ('BOTTOMPADDING', (0,1), (-1,-1), 6),
        ('LEFTPADDING',   (0,1), (-1,-1), 3),
        ('RIGHTPADDING',  (0,1), (-1,-1), 3),
        ('ALIGN',         (0,1), (0,-1), 'CENTER'),   # N° centré
        # Colonne Signature : fond légèrement grisé, séparateur marqué
        ('BACKGROUND',    (7,1), (7,-1), GREY_BG),
        ('LINEAFTER',     (6,1), (6,-1), 1.2, DARK),
        # Grille
        ('GRID',    (0,0), (-1,-1), 0.4, colors.HexColor('#AAAAAA')),
        ('BOX',     (0,0), (-1,-1), 0.8, DARK),
        # Alternance légère sur les colonnes de données
        ('ROWBACKGROUNDS', (0,1), (6,-1),
         [WHITE, colors.HexColor('#FAFAFA')]),
    ]))

    if presences:
        story.append(sign_table)
    else:
        story.append(Paragraph(
            "Aucun participant confirmé pour cette réunion.",
            ps('NoP', fontName='Helvetica-Oblique', fontSize=9,
               textColor=colors.HexColor('#888888')),
        ))

    story.append(Spacer(1, 20))

    # ── 5. BLOC VISA ORGANISATEUR ────────────────────────────────────────────
    visa_data = [[
        Paragraph("Le Secrétaire de séance", ps('Visa', fontName='Helvetica-Bold',
                  fontSize=9, alignment=1)),
        Paragraph("Lu et approuvé — L'Organisateur", ps('Visa', fontName='Helvetica-Bold',
                  fontSize=9, alignment=1)),
    ]]
    visa_t = Table(visa_data, colWidths=[CONTENT_W / 2, CONTENT_W / 2])
    visa_t.setStyle(TableStyle([
        ('BOX',        (0,0), (-1,-1), 0.5, BORDER),
        ('INNERGRID',  (0,0), (-1,-1), 0.5, BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 40),  # espace pour signer
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
    ]))
    story.append(visa_t)

    # ── 6. PIED DE PAGE (toutes les pages) ──────────────────────────────────
    LEGAL = (
        "Vos données personnelles sont collectées et traitées par la Direction de la Protection des Données Personnelles "
        "de l'ARTCI, dans le cadre de la présente rencontre, exclusivement aux fins de vous identifier. "
        "Conformément à la loi n°2013-450 du 19 juin 2013 relative à la protection des données à caractère personnel, "
        "vous disposez d'un droit d'accès, d'opposition, de rectification et de suppression auprès de ladite Direction."
    )

    def on_page(canvas_obj, doc_obj):
        canvas_obj.saveState()
        pw = PAGE_W
        fy = 0.35 * inch

        # Ligne de séparation
        canvas_obj.setStrokeColor(ORANGE)
        canvas_obj.setLineWidth(1)
        canvas_obj.line(LEFT, fy + 1.1 * inch, pw - RIGHT, fy + 1.1 * inch)

        # Mention légale
        legal_s = ParagraphStyle(
            'LF', fontName='Helvetica', fontSize=6.5, leading=8,
            textColor=colors.HexColor('#555555'), alignment=4,
        )
        lp = Paragraph(LEGAL, legal_s)
        aw = pw - LEFT - RIGHT
        lp.wrap(aw, 1.0 * inch)
        lp.drawOn(canvas_obj, LEFT, fy + 0.3 * inch)

        # Bas : généré le / page
        canvas_obj.setFont('Helvetica', 7)
        canvas_obj.setFillColor(colors.HexColor('#888888'))
        canvas_obj.drawString(
            LEFT, fy + 0.12 * inch,
            f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}  —  QR Meeting · ARTCI",
        )
        canvas_obj.drawRightString(
            pw - RIGHT, fy + 0.12 * inch,
            f"Page {doc_obj.page}",
        )
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buffer.seek(0)

    safe_title = reunion.titre.replace(' ', '_')[:40]
    filename = f"feuille_presence_{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
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
    """Feuille de présence Word — 8 colonnes avec signature numérique."""
    doc = Document()

    # ── Marges ───────────────────────────────────────────────────────────────
    for section in doc.sections:
        section.top_margin    = Inches(0.8)
        section.bottom_margin = Inches(1.0)
        section.left_margin   = Inches(0.5)
        section.right_margin  = Inches(0.5)

        # ── Pied de page ─────────────────────────────────────────────────────
        footer = section.footer
        fp = footer.paragraphs[0]
        fp.clear()
        legal_run = fp.add_run(
            "Données personnelles collectées et traitées par la Direction de la Protection des Données Personnelles "
            "de l'ARTCI conformément à la loi n°2013-450 du 19 juin 2013. "
            "Vous disposez d'un droit d'accès, d'opposition, de rectification et de suppression."
        )
        legal_run.font.size    = Pt(7)
        legal_run.font.italic  = True
        legal_run.font.color.rgb = RGBColor(85, 85, 85)
        gen_run = fp.add_run(
            f"\nGénéré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}  —  QR Meeting · ARTCI"
        )
        gen_run.font.size      = Pt(7)
        gen_run.font.color.rgb = RGBColor(136, 136, 136)

    # ── Titre ─────────────────────────────────────────────────────────────────
    title = doc.add_heading(f'Feuille de Présence — {reunion.titre}', 0)
    if title.runs:
        title.runs[0].font.color.rgb = RGBColor(255, 107, 53)

    # ── Infos réunion ─────────────────────────────────────────────────────────
    sec_name = (
        f"{reunion.secretaire.first_name} {reunion.secretaire.last_name}".strip()
        if reunion.secretaire else "—"
    )
    org_name = f"{reunion.organisateur.first_name} {reunion.organisateur.last_name}".strip()

    info_p = doc.add_paragraph()
    for label, value in [
        ('Date :', reunion.date_debut.strftime('%d/%m/%Y à %H:%M')),
        ('Lieu :', reunion.lieu),
        ('Organisateur :', org_name),
        ('Secrétaire :', sec_name),
        ('Participants confirmés :', str(presences.count())),
    ]:
        r_lbl = info_p.add_run(label + '  ')
        r_lbl.bold = True
        r_lbl.font.size = Pt(9)
        r_val = info_p.add_run(value + '     ')
        r_val.font.size = Pt(9)

    doc.add_paragraph()

    if not presences:
        doc.add_paragraph('Aucun participant confirmé pour cette réunion.')
    else:
        # ── Tableau 8 colonnes ────────────────────────────────────────────────
        # Largeurs (cm) sur A4 contenu ≈ 18.46 cm
        col_cms_raw = [0.7, 2.5, 2.5, 3.1, 2.9, 2.2, 3.3, 2.2]
        scale = 18.46 / sum(col_cms_raw)
        col_cms = [c * scale for c in col_cms_raw]

        hdrs = ['N°', 'Nom', 'Prénom', 'Structure/\nOrganisation',
                'Fonction', 'Contact', 'Email', 'Signature']

        table = doc.add_table(rows=1, cols=8)
        table.style = 'Table Grid'

        # En-tête orangé
        for i, h in enumerate(hdrs):
            cell = table.rows[0].cells[i]
            cell.width = Cm(col_cms[i])
            para = cell.paragraphs[0]
            para.clear()
            run = para.add_run(h)
            run.bold = True
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(255, 255, 255)
            para.paragraph_format.space_before = Pt(3)
            para.paragraph_format.space_after  = Pt(3)
            shd = OxmlElement('w:shd')
            shd.set(qn('w:fill'), 'FF6B35')
            shd.set(qn('w:val'),  'clear')
            cell._tc.get_or_add_tcPr().append(shd)

        # Données
        for idx, pr in enumerate(presences, 1):
            row_cells = table.add_row().cells
            values = [
                str(idx),
                pr.nom or '—',
                pr.prenom or '—',
                pr.organisation or '—',
                pr.fonction or '—',
                pr.contact or '—',
                pr.email or '—',
            ]
            for i, val in enumerate(values):
                cell = row_cells[i]
                cell.width = Cm(col_cms[i])
                para = cell.paragraphs[0]
                para.clear()
                run = para.add_run(val)
                run.font.size = Pt(7.5)
                para.paragraph_format.space_before = Pt(2)
                para.paragraph_format.space_after  = Pt(2)

            # Signature (colonne 7)
            sig_cell = row_cells[7]
            sig_cell.width = Cm(col_cms[7])
            sig_para = sig_cell.paragraphs[0]
            sig_para.clear()
            sig_para.paragraph_format.space_before = Pt(2)
            sig_para.paragraph_format.space_after  = Pt(2)
            if pr.signature:
                try:
                    run = sig_para.add_run()
                    run.add_picture(pr.signature.path, width=Cm(col_cms[7] * 0.82))
                except Exception:
                    pass

        # Forcer les largeurs de colonnes sur toutes les lignes
        for row in table.rows:
            for i, cell in enumerate(row.cells):
                cell.width = Cm(col_cms[i])

    doc.add_paragraph()

    # ── Bloc visa ─────────────────────────────────────────────────────────────
    doc.add_heading('Approbation', level=2)
    visa_t = doc.add_table(rows=2, cols=2)
    visa_t.style = 'Table Grid'
    for i, txt in enumerate(['Le Secrétaire de séance', "Lu et approuvé — L'Organisateur"]):
        c = visa_t.rows[0].cells[i]
        c.text = txt
        c.paragraphs[0].runs[0].bold = True
        c.paragraphs[0].runs[0].font.size = Pt(9)
    # Ligne vide pour signer
    for c in visa_t.rows[1].cells:
        c.text = ''
        tr = visa_t.rows[1]._tr
        trPr = tr.get_or_add_trPr()
        trH = OxmlElement('w:trHeight')
        trH.set(qn('w:val'), '720')
        trH.set(qn('w:hRule'), 'atLeast')
        trPr.append(trH)

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    safe = reunion.titre.replace(' ', '_')[:40]
    filename = f"presence_{safe}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
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


# ─── Export Diligences ────────────────────────────────────────────────────────

def export_diligences(reunion, format_type='pdf'):
    """Dispatch vers PDF ou Excel."""
    diligences = (
        reunion.diligences
        .select_related('responsable_interne', 'created_by')
        .prefetch_related('commentaires__auteur')
        .order_by('-priorite', 'echeance', 'created_at')
    )
    if format_type == 'excel':
        return _diligences_excel(reunion, diligences)
    return _diligences_pdf(reunion, diligences)


def _diligences_pdf(reunion, diligences):
    import os
    from reportlab.platypus import Image as RLImage
    from django.conf import settings as django_settings

    ORANGE   = colors.HexColor('#FF6B35')
    DARK     = colors.HexColor('#1A1A2E')
    LIGHT_BG = colors.HexColor('#FFF8F4')
    GREY_BG  = colors.HexColor('#F5F5F5')
    WHITE    = colors.white
    BORDER   = colors.HexColor('#CCCCCC')

    STATUS_COLORS = {
        'open':        colors.HexColor('#6C757D'),
        'in_progress': colors.HexColor('#0D6EFD'),
        'completed':   colors.HexColor('#198754'),
        'cancelled':   colors.HexColor('#DC3545'),
    }
    STATUS_LABELS = {
        'open': 'À faire', 'in_progress': 'En cours',
        'completed': 'Terminée', 'cancelled': 'Annulée',
    }
    PRIO_LABELS = {'low': 'Faible', 'medium': 'Normale', 'high': 'Urgente'}

    PAGE_W, PAGE_H = A4
    LEFT = RIGHT = 0.5 * inch
    CONTENT_W = PAGE_W - LEFT - RIGHT

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=0.5 * inch, bottomMargin=1.5 * inch,
        leftMargin=LEFT, rightMargin=RIGHT,
    )

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    cell_s  = ps('C',   fontName='Helvetica',       fontSize=8,  leading=10)
    cell_b  = ps('CB',  fontName='Helvetica-Bold',  fontSize=8,  leading=10)
    hdr_s   = ps('H',   fontName='Helvetica-Bold',  fontSize=8,  leading=10,
                textColor=WHITE, alignment=1)
    tiny_s  = ps('T',   fontName='Helvetica',       fontSize=7,  leading=9,
                textColor=colors.HexColor('#555555'))
    info_k  = ps('IK',  fontName='Helvetica-Bold',  fontSize=9,  leading=12)
    info_v  = ps('IV',  fontName='Helvetica',       fontSize=9,  leading=12)

    story = []

    # ── En-tête ARTCI ────────────────────────────────────────────────────────
    logo_path = os.path.normpath(os.path.join(
        str(django_settings.BASE_DIR), '..', 'static', 'img', 'artci_logo.png'))
    if os.path.exists(logo_path):
        logo = RLImage(logo_path, width=2.6 * inch, height=0.52 * inch)
        ref  = Paragraph(
            f"Réf. ARTCI/QRM/{reunion.pk:04d}<br/>Date : {datetime.now().strftime('%d/%m/%Y')}",
            ps('R', fontName='Helvetica', fontSize=8,
               textColor=colors.HexColor('#555555'), alignment=2),
        )
        ht = Table([[logo, '', ref]],
                   colWidths=[2.8*inch, CONTENT_W-2.8*inch-1.4*inch, 1.4*inch])
        ht.setStyle(TableStyle([
            ('VALIGN',    (0,0), (-1,-1), 'MIDDLE'),
            ('LINEBELOW', (0,0), (-1,0),  1, ORANGE),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(ht)
    story.append(Spacer(1, 6))

    # ── Titre ─────────────────────────────────────────────────────────────────
    tt = Table(
        [[Paragraph("SUIVI DES DILIGENCES", ps('DT', fontName='Helvetica-Bold',
          fontSize=13, textColor=WHITE, alignment=1))]],
        colWidths=[CONTENT_W],
    )
    tt.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), ORANGE),
        ('TOPPADDING',    (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(tt)
    story.append(Spacer(1, 8))

    # ── Infos réunion ─────────────────────────────────────────────────────────
    cw = CONTENT_W / 4
    info_t = Table([
        [Paragraph('Réunion :', info_k),
         Paragraph(reunion.titre, ps('TV', fontName='Helvetica-Bold', fontSize=9,
                   textColor=DARK)),
         Paragraph('Date :', info_k),
         Paragraph(reunion.date_debut.strftime('%d/%m/%Y'), info_v)],
        [Paragraph('Lieu :', info_k), Paragraph(reunion.lieu, info_v),
         Paragraph('Total diligences :', info_k),
         Paragraph(str(diligences.count()), ps('N', fontName='Helvetica-Bold',
                   fontSize=9, textColor=ORANGE))],
    ], colWidths=[cw*0.7, cw*1.3, cw*0.8, cw*1.2])
    info_t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), LIGHT_BG),
        ('BOX',           (0,0), (-1,-1), 0.8, ORANGE),
        ('INNERGRID',     (0,0), (-1,-1), 0.3, BORDER),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(info_t)
    story.append(Spacer(1, 12))

    # ── Résumé statistique ────────────────────────────────────────────────────
    counts = {'open': 0, 'in_progress': 0, 'completed': 0, 'cancelled': 0}
    for d in diligences:
        counts[d.status] = counts.get(d.status, 0) + 1

    stat_data = [[
        Paragraph(f"{counts['open']}\nÀ faire",        ps('SC', fontName='Helvetica-Bold', fontSize=9, textColor=STATUS_COLORS['open'],        alignment=1)),
        Paragraph(f"{counts['in_progress']}\nEn cours", ps('SC', fontName='Helvetica-Bold', fontSize=9, textColor=STATUS_COLORS['in_progress'], alignment=1)),
        Paragraph(f"{counts['completed']}\nTerminées",  ps('SC', fontName='Helvetica-Bold', fontSize=9, textColor=STATUS_COLORS['completed'],   alignment=1)),
        Paragraph(f"{counts['cancelled']}\nAnnulées",   ps('SC', fontName='Helvetica-Bold', fontSize=9, textColor=STATUS_COLORS['cancelled'],   alignment=1)),
    ]]
    stat_t = Table(stat_data, colWidths=[CONTENT_W/4]*4)
    stat_t.setStyle(TableStyle([
        ('BOX',       (0,0), (-1,-1), 0.5, BORDER),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER),
        ('ALIGN',     (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(stat_t)
    story.append(Spacer(1, 14))

    # ── Tableau des diligences ────────────────────────────────────────────────
    if diligences:
        col_w = [
            0.28 * inch,  # N°
            1.50 * inch,  # Titre
            0.72 * inch,  # Statut
            0.62 * inch,  # Priorité
            1.10 * inch,  # Responsable
            0.68 * inch,  # Échéance
            2.10 * inch,  # Commentaires
        ]
        scale = CONTENT_W / sum(col_w)
        col_w = [w * scale for w in col_w]

        headers = ['N°', 'Titre / Description', 'Statut', 'Priorité',
                   'Responsable', 'Échéance', 'Commentaires']
        data = [[Paragraph(h, hdr_s) for h in headers]]

        for i, d in enumerate(diligences, 1):
            # Commentaires : derniers 3 max
            comments = d.commentaires.all()
            if comments:
                lines = []
                for c in comments[:3]:
                    auteur = (f"{c.auteur.first_name} {c.auteur.last_name}".strip()
                              if c.auteur else '?')
                    date_c = c.created_at.strftime('%d/%m %H:%M')
                    if c.is_status_change():
                        lines.append(
                            f"<b>{auteur}</b> ({date_c}) : "
                            f"{STATUS_LABELS.get(c.ancien_status, c.ancien_status)} → "
                            f"{STATUS_LABELS.get(c.nouveau_status, c.nouveau_status)}"
                            + (f"<br/><i>{c.contenu}</i>" if c.contenu else '')
                        )
                    elif c.contenu:
                        lines.append(f"<b>{auteur}</b> ({date_c}) :<br/><i>{c.contenu}</i>")
                if len(comments) > 3:
                    lines.append(f"<i>+ {len(comments)-3} autre(s)…</i>")
                comment_p = Paragraph('<br/>'.join(lines), tiny_s)
            else:
                comment_p = Paragraph('—', tiny_s)

            # Titre + description
            titre_txt = f"<b>{d.titre}</b>"
            if d.description:
                titre_txt += f"<br/><font size='7' color='#666666'>{d.description[:80]}{'…' if len(d.description)>80 else ''}</font>"
            titre_p = Paragraph(titre_txt, cell_s)

            # Responsable
            resp = d.get_responsable_display()

            # Échéance (rouge si en retard)
            if d.echeance:
                from django.utils import timezone
                overdue = d.is_overdue()
                ech_color = '#DC3545' if overdue else '#333333'
                ech_txt = f"<font color='{ech_color}'>{d.echeance.strftime('%d/%m/%Y')}</font>"
                ech_p = Paragraph(ech_txt, tiny_s)
            else:
                ech_p = Paragraph('—', tiny_s)

            status_color = STATUS_COLORS.get(d.status, DARK)
            status_label = STATUS_LABELS.get(d.status, d.status)

            row = [
                Paragraph(str(i), ps('Cn', fontName='Helvetica', fontSize=8, alignment=1)),
                titre_p,
                Paragraph(status_label, ps('SL', fontName='Helvetica-Bold', fontSize=7,
                          textColor=status_color, alignment=1)),
                Paragraph(PRIO_LABELS.get(d.priorite, d.priorite),
                          ps('PL', fontName='Helvetica', fontSize=7,
                             textColor=colors.HexColor('#555555'), alignment=1)),
                Paragraph(resp[:30], cell_s),
                ech_p,
                comment_p,
            ]
            data.append(row)

        tbl = Table(data, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), ORANGE),
            ('TEXTCOLOR',     (0,0), (-1,0), WHITE),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN',         (0,0), (-1,0), 'CENTER'),
            ('VALIGN',        (0,0), (-1,0), 'MIDDLE'),
            ('TOPPADDING',    (0,0), (-1,0), 5),
            ('BOTTOMPADDING', (0,0), (-1,0), 5),
            ('FONTNAME',  (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE',  (0,1), (-1,-1), 8),
            ('VALIGN',    (0,1), (-1,-1), 'TOP'),
            ('TOPPADDING',(0,1), (-1,-1), 4),
            ('BOTTOMPADDING', (0,1), (-1,-1), 4),
            ('ROWBACKGROUNDS', (0,1), (-1,-1),
             [WHITE, colors.HexColor('#FAFAFA')]),
            ('GRID',      (0,0), (-1,-1), 0.3, BORDER),
            ('BOX',       (0,0), (-1,-1), 0.8, DARK),
            # Fond colonne commentaires légèrement différent
            ('BACKGROUND', (6,1), (6,-1), GREY_BG),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph(
            "Aucune diligence enregistrée pour cette réunion.",
            ps('NP', fontName='Helvetica-Oblique', fontSize=9,
               textColor=colors.HexColor('#888888')),
        ))

    story.append(Spacer(1, 10))

    # ── Pied de page ─────────────────────────────────────────────────────────
    LEGAL = (
        "Document généré automatiquement par QR Meeting — ARTCI. "
        "Les diligences et commentaires présentés sont issus du système de gestion de réunions. "
        "Pour toute question, contacter le responsable de la réunion."
    )

    def on_page(c, doc_obj):
        c.saveState()
        pw = PAGE_W
        fy = 0.35 * inch
        c.setStrokeColor(ORANGE)
        c.setLineWidth(0.8)
        c.line(LEFT, fy + 1.0 * inch, pw - RIGHT, fy + 1.0 * inch)
        lp = Paragraph(LEGAL, ps('LF', fontName='Helvetica', fontSize=6.5,
                                  leading=8, textColor=colors.HexColor('#666666')))
        lp.wrap(pw - LEFT - RIGHT, 1.0 * inch)
        lp.drawOn(c, LEFT, fy + 0.28 * inch)
        c.setFont('Helvetica', 7)
        c.setFillColor(colors.HexColor('#888888'))
        c.drawString(LEFT, fy + 0.10 * inch,
                     f"Exporté le {datetime.now().strftime('%d/%m/%Y à %H:%M')}  —  QR Meeting · ARTCI")
        c.drawRightString(pw - RIGHT, fy + 0.10 * inch, f"Page {doc_obj.page}")
        c.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buffer.seek(0)

    safe_title = reunion.titre.replace(' ', '_')[:35]
    filename = f"diligences_{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _diligences_excel(reunion, diligences):
    from openpyxl.utils import get_column_letter

    STATUS_LABELS = {
        'open': 'À faire', 'in_progress': 'En cours',
        'completed': 'Terminée', 'cancelled': 'Annulée',
    }
    PRIO_LABELS = {'low': 'Faible', 'medium': 'Normale', 'high': 'Urgente'}
    STATUS_FILLS = {
        'open':        PatternFill('solid', fgColor='6C757D'),
        'in_progress': PatternFill('solid', fgColor='0D6EFD'),
        'completed':   PatternFill('solid', fgColor='198754'),
        'cancelled':   PatternFill('solid', fgColor='DC3545'),
    }
    PRIO_FILLS = {
        'high':   PatternFill('solid', fgColor='DC3545'),
        'medium': PatternFill('solid', fgColor='FFC107'),
        'low':    PatternFill('solid', fgColor='6C757D'),
    }

    wb = Workbook()
    ws = wb.active
    ws.title = "Diligences"

    thin  = Side(style='thin', color='CCCCCC')
    thick = Side(style='medium', color='FF6B35')
    thin_border  = Border(left=thin, right=thin, top=thin, bottom=thin)
    thick_border = Border(left=thick, right=thick, top=thick, bottom=thick)

    # ── Entête réunion ────────────────────────────────────────────────────────
    ws.merge_cells('A1:H1')
    ws['A1'] = f"SUIVI DES DILIGENCES — {reunion.titre}"
    ws['A1'].font = Font(bold=True, size=14, color='FF6B35')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 28

    info = [
        ('Date réunion :', reunion.date_debut.strftime('%d/%m/%Y à %H:%M')),
        ('Lieu :', reunion.lieu),
        ('Organisateur :', f"{reunion.organisateur.first_name} {reunion.organisateur.last_name}".strip()),
        ('Total diligences :', str(diligences.count())),
    ]
    for r, (k, v) in enumerate(info, 3):
        ws.cell(r, 1, k).font = Font(bold=True, size=9)
        ws.cell(r, 2, v).font = Font(size=9)
    ws.merge_cells('B3:H6')

    # ── En-têtes colonnes ─────────────────────────────────────────────────────
    headers = ['N°', 'Titre', 'Description', 'Statut', 'Priorité',
               'Responsable', 'Échéance', 'Commentaires']
    col_widths = [5, 28, 35, 12, 10, 22, 14, 50]

    HDR_ROW = 8
    orange_fill = PatternFill('solid', fgColor='FF6B35')
    for c, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(HDR_ROW, c, h)
        cell.font = Font(bold=True, color='FFFFFF', size=9)
        cell.fill = orange_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = thick_border
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.row_dimensions[HDR_ROW].height = 20

    # ── Données ────────────────────────────────────────────────────────────────
    for i, d in enumerate(diligences, 1):
        row_n = HDR_ROW + i

        # Commentaires — tout en texte brut pour Excel
        comments_parts = []
        for c in d.commentaires.all():
            auteur = (f"{c.auteur.first_name} {c.auteur.last_name}".strip()
                      if c.auteur else '?')
            date_c = c.created_at.strftime('%d/%m/%Y %H:%M')
            if c.is_status_change():
                line = (f"[{date_c}] {auteur} : "
                        f"{STATUS_LABELS.get(c.ancien_status,'')} → "
                        f"{STATUS_LABELS.get(c.nouveau_status,'')}")
                if c.contenu:
                    line += f"\n  {c.contenu}"
            elif c.contenu:
                line = f"[{date_c}] {auteur} :\n  {c.contenu}"
            else:
                continue
            comments_parts.append(line)
        comments_txt = '\n\n'.join(comments_parts) if comments_parts else '—'

        resp = d.get_responsable_display()
        echeance_val = d.echeance.strftime('%d/%m/%Y') if d.echeance else '—'
        status_label = STATUS_LABELS.get(d.status, d.status)
        prio_label   = PRIO_LABELS.get(d.priorite, d.priorite)

        row_data = [
            i, d.titre, d.description or '—',
            status_label, prio_label, resp,
            echeance_val, comments_txt,
        ]
        for c_idx, val in enumerate(row_data, 1):
            cell = ws.cell(row_n, c_idx, val)
            cell.alignment = Alignment(
                horizontal='left', vertical='top', wrap_text=True)
            cell.border = thin_border
            cell.font = Font(size=8)

        # Coloration badge statut
        stat_cell = ws.cell(row_n, 4)
        stat_cell.fill = STATUS_FILLS.get(d.status, PatternFill())
        stat_cell.font = Font(bold=True, color='FFFFFF', size=8)
        stat_cell.alignment = Alignment(horizontal='center', vertical='center')

        # Coloration badge priorité
        prio_cell = ws.cell(row_n, 5)
        prio_cell.fill = PRIO_FILLS.get(d.priorite, PatternFill())
        prio_cell.font = Font(bold=True,
                              color='000000' if d.priorite == 'medium' else 'FFFFFF',
                              size=8)
        prio_cell.alignment = Alignment(horizontal='center', vertical='center')

        # N° centré
        ws.cell(row_n, 1).alignment = Alignment(horizontal='center', vertical='top')
        ws.cell(row_n, 1).font = Font(size=8)

        # Hauteur auto selon nb lignes commentaires
        nb_lines = max(1, comments_txt.count('\n') + 1, len(d.titre) // 25 + 1)
        ws.row_dimensions[row_n].height = max(18, min(nb_lines * 13, 80))

    # ── Figer la ligne d'en-têtes ──────────────────────────────────────────────
    ws.freeze_panes = f'A{HDR_ROW + 1}'

    # ── Onglet résumé statuts ─────────────────────────────────────────────────
    ws2 = wb.create_sheet("Résumé")
    ws2['A1'] = "Statut"
    ws2['B1'] = "Nombre"
    for c in [ws2['A1'], ws2['B1']]:
        c.font = Font(bold=True, color='FFFFFF', size=9)
        c.fill = orange_fill
        c.alignment = Alignment(horizontal='center')
    from collections import Counter
    counts = Counter(d.status for d in diligences)
    STATUS_LABELS_ALL = {'open':'À faire','in_progress':'En cours',
                         'completed':'Terminée','cancelled':'Annulée'}
    for r, (st, lbl) in enumerate(STATUS_LABELS_ALL.items(), 2):
        ws2.cell(r, 1, lbl).font = Font(size=9)
        cnt_cell = ws2.cell(r, 2, counts.get(st, 0))
        cnt_cell.font = Font(bold=True, size=9)
        cnt_cell.fill = STATUS_FILLS.get(st, PatternFill())
        cnt_cell.font = Font(bold=True, color='FFFFFF', size=9)
        cnt_cell.alignment = Alignment(horizontal='center')
    ws2.column_dimensions['A'].width = 14
    ws2.column_dimensions['B'].width = 10

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    safe_title = reunion.titre.replace(' ', '_')[:35]
    filename = f"diligences_{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response