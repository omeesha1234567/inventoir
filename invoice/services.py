"""Invoice field mapping and snapshot sync from sale/company records."""


def build_invoice_line_from_sale_detail(detail):
    """
    Map a SaleDetail row to invoice line dict.
    Rate = pre-GST unit price (base + margin embedded in total_detail).
    """
    qty = float(detail.quantity)
    gst_pct = float(getattr(detail, 'gst_percentage', 0) or 0)
    if not gst_pct and detail.item_id:
        gst_pct = float(detail.item.gst_percentage or 0)

    line_total = float(detail.total_detail)
    unit_inclusive = line_total / qty if qty else 0.0
    if gst_pct:
        unit_pretax = unit_inclusive / (1 + gst_pct / 100)
    else:
        unit_pretax = unit_inclusive

    return {
        'price': round(unit_pretax, 2),
        'quantity': qty,
        'gst_percentage': gst_pct,
        'line_total': round(line_total, 2),
    }


def sync_invoice_from_sale(invoice, *, save=False):
    """Copy business fields from the linked sale, customer, and company."""
    sale = invoice.sale
    if sale is None:
        return invoice

    customer = sale.customer
    company = invoice.company or sale.company

    invoice.customer_name = str(customer) if customer else ''
    invoice.contact_number = (customer.phone or '') if customer else ''
    invoice.customer_address = (customer.address or '') if customer else ''

    gst = (sale.customer_gst_number or '').strip()
    if not gst and customer and customer.gst_number:
        gst = (customer.gst_number or '').strip()
    invoice.customer_gst_number = gst or 'NA'

    invoice.total = round(float(sale.sub_total), 2)
    invoice.grand_total = round(float(sale.grand_total), 2)

    if company:
        invoice.company_name = company.name
        invoice.company_gst_number = company.gst_number or ''
        invoice.company_phone = company.phone or ''
        invoice.company_address = company.address or ''
        if invoice.company_id is None:
            invoice.company = company

    if save:
        invoice.save()
    return invoice


def create_invoice_items_from_sale(invoice, sale, company):
    """Rebuild invoice line items from sale details."""
    from invoice.models import InvoiceItem

    invoice.invoice_items.all().delete()
    for detail in sale.saledetail_set.select_related('item').all():
        line = build_invoice_line_from_sale_detail(detail)
        InvoiceItem.objects.create(
            invoice=invoice,
            item=detail.item,
            company=company,
            price=line['price'],
            quantity=line['quantity'],
            gst_percentage=line['gst_percentage'],
            line_total=line['line_total'],
        )
