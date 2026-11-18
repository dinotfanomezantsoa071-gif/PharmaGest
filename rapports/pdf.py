from io import BytesIO
from xml.sax.saxutils import escape

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_pdf_response(filename, title, headers, rows, summary=None, wide=False, sections=None):
    buffer = BytesIO()
    page_size = landscape(A4) if wide else A4
    document = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='ReportTitle',
        parent=styles['Title'],
        alignment=TA_CENTER,
        textColor=colors.HexColor('#14532d'),
        spaceAfter=8 * mm,
    ))
    cell_style = ParagraphStyle('ReportCell', parent=styles['BodyText'], fontSize=8, leading=10)
    content = [Paragraph(escape(title), styles['ReportTitle'])]
    if summary:
        content.extend([Paragraph(escape(summary), styles['BodyText']), Spacer(1, 5 * mm)])

    table_data = [[Paragraph(escape(str(value)), cell_style) for value in headers]]
    table_data.extend([
        [Paragraph(escape(str(value)), cell_style) for value in row]
        for row in rows
    ])
    if len(table_data) == 1:
        table_data.append([Paragraph('Aucune donnée pour cette période.', cell_style)] + [''] * (len(headers) - 1))

    table = Table(table_data, repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#14532d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    content.append(table)

    for section_title, section_headers, section_rows in sections or []:
        content.extend([Spacer(1, 6 * mm), Paragraph(escape(section_title), styles['Heading2'])])
        section_data = [[Paragraph(escape(str(value)), cell_style) for value in section_headers]]
        section_data.extend([
            [Paragraph(escape(str(value)), cell_style) for value in row]
            for row in section_rows
        ])
        if len(section_data) == 1:
            section_data.append([Paragraph('Aucune donnée.', cell_style)] + [''] * (len(section_headers) - 1))
        section_table = Table(section_data, repeatRows=1, hAlign='LEFT')
        section_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#14532d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#d1d5db')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        content.append(section_table)

    document.build(content)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
