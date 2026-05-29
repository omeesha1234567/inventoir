from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView, UpdateView

from accounts.mixins import (
    CompanyAdminRequiredMixin,
    CoordinatorOrAdminMixin,
    redirect_to_role_dashboard,
)
from accounts.models import (
    Customer,
    Profile,
    ROLE_COMPANY_ADMIN,
    ROLE_COORDINATOR,
    STATUS_ACTIVE,
    Vendor,
)
from accounts.utils import filter_by_company
from companies.base import archive_instance, restore_instance
from companies.forms import CompanyRegistrationForm, CoordinatorCreateForm
from companies.models import Company
from companies.services import register_company_with_admin
from invoice.models import Invoice
from store.models import Category, Item
from transactions.models import Purchase, PurchasePayment, Sale, SalePayment


class OwnerLoginView(LoginView):
    template_name = 'companies/owner_login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('admin-dashboard')

    def form_valid(self, form):
        user = form.get_user()
        profile = getattr(user, 'profile', None)
        if user.is_superuser:
            return super().form_valid(form)
        if profile is None or not profile.is_company_admin():
            messages.error(
                self.request,
                'This login is for company owners only. Use coordinator login.',
            )
            return self.form_invalid(form)
        if not user.is_active:
            messages.error(self.request, 'Your account is inactive.')
            return self.form_invalid(form)
        company = profile.company
        if company is None or not company.is_active:
            messages.error(self.request, 'Your company is inactive.')
            return self.form_invalid(form)
        return super().form_valid(form)


class CoordinatorLoginView(LoginView):
    template_name = 'companies/coordinator_login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('coordinator-dashboard')

    def form_valid(self, form):
        user = form.get_user()
        profile = getattr(user, 'profile', None)
        if user.is_superuser:
            messages.error(
                self.request,
                'Superusers should use Django admin or owner login.',
            )
            return self.form_invalid(form)
        if profile is None or not profile.is_coordinator():
            messages.error(
                self.request,
                'This login is for coordinators only. Use owner login.',
            )
            return self.form_invalid(form)
        if not user.is_active:
            messages.error(self.request, 'Your account is inactive.')
            return self.form_invalid(form)
        company = profile.company
        if company is None or not company.is_active:
            messages.error(self.request, 'Your company is inactive.')
            return self.form_invalid(form)
        return super().form_valid(form)


class CompanyRegistrationView(FormView):
    template_name = 'companies/company_register.html'
    form_class = CompanyRegistrationForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect_to_role_dashboard(request.user)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            company, user = register_company_with_admin(
                company_name=form.cleaned_data['company_name'],
                gst_number=form.cleaned_data['gst_number'],
                company_email=form.cleaned_data['company_email'],
                phone=form.cleaned_data['phone'],
                address=form.cleaned_data['address'],
                owner_name=form.cleaned_data['owner_name'],
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password1'],
                user_email=form.cleaned_data['company_email'],
            )
        except Exception as exc:
            messages.error(self.request, str(exc))
            return self.form_invalid(form)

        login(
            self.request,
            user,
            backend='django.contrib.auth.backends.ModelBackend',
        )
        messages.success(
            self.request,
            f'Company {company.name} registered. Code: {company.company_code}',
        )
        return redirect('admin-dashboard')


class CompanySettingsView(CompanyAdminRequiredMixin, UpdateView):
    model = Company
    template_name = 'companies/company_settings.html'
    fields = ['name', 'gst_number', 'email', 'phone', 'address']
    context_object_name = 'company'

    def get_object(self, queryset=None):
        return get_object_or_404(Company, pk=self.request.user.profile.company_id)

    def get_success_url(self):
        messages.success(self.request, 'Company settings updated.')
        return reverse('company-settings')


class CoordinatorListView(CompanyAdminRequiredMixin, ListView):
    model = Profile
    template_name = 'companies/coordinator_list.html'
    context_object_name = 'coordinators'

    def get_queryset(self):
        return Profile.objects.filter(
            company=self.request.user.profile.company,
            role=ROLE_COORDINATOR,
        ).select_related('user')


class CoordinatorCreateView(CompanyAdminRequiredMixin, FormView):
    template_name = 'companies/coordinator_create.html'
    form_class = CoordinatorCreateForm

    def form_valid(self, form):
        company = self.request.user.profile.company
        with transaction.atomic():
            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.first_name = form.cleaned_data['name']
            user.save()
            profile = user.profile
            profile.company = company
            profile.role = ROLE_COORDINATOR
            profile.status = STATUS_ACTIVE
            profile.email = form.cleaned_data['email']
            profile.first_name = form.cleaned_data['name']
            profile.save()
        messages.success(self.request, 'Coordinator created successfully.')
        return redirect('coordinator-list')


class CoordinatorDeactivateView(CompanyAdminRequiredMixin, View):
    def post(self, request, pk):
        profile = get_object_or_404(
            Profile,
            pk=pk,
            company=request.user.profile.company,
            role=ROLE_COORDINATOR,
        )
        profile.user.is_active = False
        profile.user.save(update_fields=['is_active'])
        profile.status = 'INA'
        profile.save(update_fields=['status'])
        messages.success(request, 'Coordinator deactivated.')
        return redirect('coordinator-list')


ARCHIVED_SECTIONS = {
    'customers': (Customer, 'customer_list'),
    'vendors': (Vendor, 'vendor-list'),
    'products': (Item, 'productslist'),
    'categories': (Category, 'category-list'),
    'sales': (Sale, 'saleslist'),
    'purchases': (Purchase, 'purchaseslist'),
    'invoices': (Invoice, 'invoicelist'),
    'sale-payments': (SalePayment, 'saleslist'),
    'purchase-payments': (PurchasePayment, 'purchaseslist'),
}


class ArchivedRecordsView(CompanyAdminRequiredMixin, ListView):
    template_name = 'companies/archived_records.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        section = self.kwargs.get('section', 'customers')
        model, _ = ARCHIVED_SECTIONS.get(section, ARCHIVED_SECTIONS['customers'])
        qs = model.objects.filter(
            company=self.request.user.profile.company,
            is_archived=True,
        )
        return qs.order_by('-archived_at', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section = self.kwargs.get('section', 'customers')
        context['section'] = section
        context['sections'] = ARCHIVED_SECTIONS.keys()
        context['section_label'] = section.replace('_', ' ').title()
        return context


class RestoreArchivedView(CompanyAdminRequiredMixin, View):
    def post(self, request, section, pk):
        model, redirect_name = ARCHIVED_SECTIONS.get(
            section, ARCHIVED_SECTIONS['customers']
        )
        obj = get_object_or_404(
            model,
            pk=pk,
            company=request.user.profile.company,
            is_archived=True,
        )
        restore_instance(obj)
        messages.success(request, f'{model.__name__} restored successfully.')
        return redirect('archived-records', section=section)


class ProductArchiveView(CompanyAdminRequiredMixin, View):
    def post(self, request, slug):
        obj = get_object_or_404(
            filter_by_company(Item.objects.all_records(), request.user),
            slug=slug,
        )
        if not obj.is_archived:
            archive_instance(obj, request.user)
        messages.success(request, 'Product archived successfully.')
        return redirect('productslist')


def archive_view_for_model(model, redirect_name):
    class ArchiveModelView(CompanyAdminRequiredMixin, View):
        def post(self, request, pk):
            obj = get_object_or_404(
                filter_by_company(model.objects.all_records(), request.user),
                pk=pk,
            )
            if obj.is_archived:
                messages.info(request, 'Already archived.')
            else:
                archive_instance(obj, request.user)
                messages.success(request, f'{model.__name__} archived successfully.')
            return redirect(redirect_name)

    return ArchiveModelView
