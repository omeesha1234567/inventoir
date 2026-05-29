import django_tables2 as tables

from .models import Invoice


class InvoiceTable(tables.Table):
    sale_id = tables.Column(
        accessor='sale_id',
        verbose_name='Sale ID',
        orderable=False,
    )

    class Meta:
        model = Invoice
        template_name = 'django_tables2/semantic.html'
        fields = (
            'date',
            'customer_name',
            'contact_number',
            'customer_gst_number',
            'total',
            'grand_total',
        )
        order_by = '-date'
