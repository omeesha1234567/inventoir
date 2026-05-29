from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView
from django_tables2 import SingleTableView
from django_tables2.export.views import ExportMixin

from accounts.mixins import CompanyAccessMixin, CompanyAdminRequiredMixin
from companies.archive_views import ArchivableDeleteView

from .models import Invoice
from .pdf import build_invoice_pdf
from .tables import InvoiceTable


class InvoiceListView(CompanyAccessMixin, ExportMixin, SingleTableView):
    model = Invoice
    table_class = InvoiceTable
    template_name = 'invoice/invoicelist.html'
    context_object_name = 'invoices'
    paginate_by = 10
    table_pagination = False

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related('sale')
            .order_by('-date', '-id')
        )


class InvoiceDetailView(CompanyAccessMixin, DetailView):
    model = Invoice
    template_name = 'invoice/invoicedetail.html'
    context_object_name = 'invoice'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invoice_items'] = (
            self.object.invoice_items.select_related('item').all()
        )
        return context


class InvoicePdfView(CompanyAccessMixin, DetailView):
    model = Invoice

    def get(self, request, *args, **kwargs):
        invoice = self.get_object()
        if not invoice.invoice_items.exists():
            raise Http404('Invoice has no line items.')
        pdf_buffer = build_invoice_pdf(invoice)
        filename = f'invoice-{invoice.id}.pdf'
        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=filename,
            content_type='application/pdf',
        )


class InvoiceCreateView(CompanyAdminRequiredMixin, DetailView):
    def get(self, request, *args, **kwargs):
        return redirect('invoicelist')


class InvoiceUpdateView(CompanyAdminRequiredMixin, DetailView):
    def get(self, request, *args, **kwargs):
        return redirect('invoicelist')


class InvoiceDeleteView(CompanyAdminRequiredMixin, ArchivableDeleteView):
    model = Invoice
    template_name = 'invoice/invoicedelete.html'
    success_url = reverse_lazy('invoicelist')

    @property
    def archive_success_message(self):
        return 'Invoice archived successfully.'
