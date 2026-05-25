from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from django.views.generic import (
    DetailView, DeleteView
)

from django_tables2 import SingleTableView
from django_tables2.export.views import ExportMixin

from .models import Invoice
from .tables import InvoiceTable


class InvoiceListView(LoginRequiredMixin, ExportMixin, SingleTableView):
    model = Invoice
    table_class = InvoiceTable
    template_name = 'invoice/invoicelist.html'
    context_object_name = 'invoices'
    paginate_by = 10
    table_pagination = False


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'invoice/invoicedetail.html'
    context_object_name = 'invoice'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invoice_items"] = self.object.invoice_items.select_related("item").all()
        return context


class InvoiceCreateView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    def get(self, request, *args, **kwargs):
        return redirect("invoicelist")

    def test_func(self):
        return self.request.user.is_superuser


class InvoiceUpdateView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    def get(self, request, *args, **kwargs):
        return redirect("invoicelist")

    def test_func(self):
        return self.request.user.is_superuser


class InvoiceDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Invoice
    template_name = 'invoice/invoicedelete.html'

    def get_success_url(self):
        return reverse('invoicelist')

    def test_func(self):
        return self.request.user.is_superuser