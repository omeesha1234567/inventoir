"""Generate invoice PDF documents."""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from invoice.services import sync_invoice_from_sale


def build_invoice_pdf(invoice):
    sync_invoice_from_sale(invoice, save=True)
    invoice.refresh_from_db()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    story = []

    company_name = invoice.company_name or 'Company'
    story.append(Paragraph(f'<b>{company_name}</b>', styles['Title']))
    story.append(Paragraph('Tax Invoice', styles['Heading2']))
    story.append(Spacer(1, 6))

    for line in (
        invoice.company_address or '',
        f'GSTIN: {invoice.company_gst_number or "—"}',
        f'Phone: {invoice.company_phone or "—"}',
    ):
        if line.strip():
            story.append(Paragraph(line.replace('\n', '<br/>'), styles['Normal']))

    story.append(Spacer(1, 12))
    meta = [
        ['Invoice No.', str(invoice.id)],
        ['Sale ID', str(invoice.sale_id) if invoice.sale_id else '—'],
        ['Date', invoice.date.strftime('%d-%b-%Y')],
        ['Customer', invoice.customer_name or '—'],
        ['Address', (invoice.customer_address or '—')[:200]],
        ['Customer GST', invoice.customer_gst_number or 'NA'],
        ['Phone', invoice.contact_number or '—'],
    ]
    meta_table = Table(meta, colWidths=[35 * mm, 120 * mm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    rows = [['#', 'Item', 'Qty', 'Rate', 'GST %', 'Amount']]
    for idx, line in enumerate(
        invoice.invoice_items.select_related('item').all(), start=1
    ):
        rows.append([
            str(idx),
            line.item.name if line.item_id else '—',
            str(line.quantity),
            f'{line.price:.2f}',
            f'{line.gst_percentage:.2f}%',
            f'{line.line_total:.2f}',
        ])
    rows.append(['', '', '', '', 'Subtotal', f'{invoice.total:.2f}'])
    rows.append(['', '', '', '', 'Grand Total', f'{invoice.grand_total:.2f}'])

    table = Table(
        rows,
        colWidths=[8 * mm, 55 * mm, 15 * mm, 22 * mm, 18 * mm, 25 * mm],
    )
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1c8f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(table)

    doc.build(story)
    buffer.seek(0)
    return buffer
