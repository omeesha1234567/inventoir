import operator
from functools import reduce

from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Sum
from django.db.models.functions import Lower
from django.contrib import messages

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages as django_messages

from accounts.mixins import (
    CompanyAccessMixin,
    CompanyAdminRequiredMixin,
    CoordinatorOrAdminMixin,
)
from accounts.models import ROLE_COMPANY_ADMIN, ROLE_COORDINATOR
from accounts.tenant import scoped_queryset
from accounts.utils import (
    assign_company,
    filter_by_company,
    get_user_company,
    set_audit_user,
)
from companies.archive_views import ArchivableDeleteView
from companies.base import archive_instance
from store.dashboard_services import get_dashboard_metrics

from django.views.generic import (
    DetailView, CreateView, UpdateView, DeleteView, ListView
)

import django_tables2 as tables
from django_tables2.export.views import ExportMixin

from accounts.models import Profile, Vendor
from transactions.models import Sale, Purchase, SaleDetail, PurchaseItem
from .models import Category, Item, Delivery
from .forms import ItemForm, CategoryForm, DeliveryForm
from .tables import ItemTable

def _dashboard_context(request, *, coordinator=False):
    company = get_user_company(request.user)
    if request.user.is_superuser and company is None:
        from accounts.utils import get_default_company
        company = get_default_company()
    if company is None:
        return None
    metrics = get_dashboard_metrics(company, coordinator=coordinator)
    cf = {'company': company}
    sale_dates = (
        Sale.active.filter(**cf)
        .values('date_added__date')
        .annotate(total_sales=Sum('grand_total'))
        .order_by('date_added__date')
    )
    metrics['sale_dates_labels'] = [
        e['date_added__date'].strftime('%Y-%m-%d')
        for e in sale_dates if e['date_added__date']
    ]
    metrics['sale_dates_values'] = [
        float(e['total_sales'] or 0) for e in sale_dates if e['date_added__date']
    ]
    purchase_dates = (
        Purchase.active.filter(**cf)
        .values('delivery_date')
        .annotate(total_purchases=Count('id'))
        .order_by('delivery_date')
    )
    metrics['purchase_dates_labels'] = [
        e['delivery_date'].strftime('%Y-%m-%d')
        for e in purchase_dates if e['delivery_date']
    ]
    metrics['purchase_dates_values'] = [
        int(e['total_purchases'] or 0) for e in purchase_dates if e['delivery_date']
    ]
    metrics['is_coordinator_dashboard'] = coordinator
    metrics['is_admin_dashboard'] = not coordinator
    return metrics


@login_required
def dashboard(request):
    profile = getattr(request.user, 'profile', None)
    if profile and profile.role == ROLE_COORDINATOR:
        return redirect('coordinator-dashboard')
    return redirect('admin-dashboard')


@login_required
def admin_dashboard(request):
    profile = getattr(request.user, 'profile', None)
    if not request.user.is_superuser:
        if profile is None or not profile.is_company_admin():
            return redirect('coordinator-dashboard')
    context = _dashboard_context(request, coordinator=False)
    if context is None:
        django_messages.error(request, 'No company assigned.')
        return redirect('owner-login')
    response = render(request, 'store/admin_dashboard.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@login_required
def coordinator_dashboard(request):
    profile = getattr(request.user, 'profile', None)
    if not request.user.is_superuser:
        if profile is None or not profile.is_coordinator():
            return redirect('admin-dashboard')
    context = _dashboard_context(request, coordinator=True)
    if context is None:
        django_messages.error(request, 'No company assigned.')
        return redirect('coordinator-login')
    response = render(request, 'store/coordinator_dashboard.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


class ProductListView(CompanyAccessMixin, ExportMixin, tables.SingleTableView):
    model = Item
    table_class = ItemTable
    template_name = "store/productslist.html"
    context_object_name = "items"
    paginate_by = 10
    tables.SingleTableView.table_pagination = False

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related('category', 'vendor')
            .order_by('name')
        )


class ItemSearchListView(ProductListView):
    paginate_by = 10

    def get_queryset(self):
        result = filter_by_company(
            Item.objects.select_related('category', 'vendor'),
            self.request.user,
        ).order_by('name')

        query = self.request.GET.get("q")
        if query:
            query_list = query.split()
            result = result.filter(
                reduce(
                    operator.and_,
                    (
                        Q(name__icontains=value) |
                        Q(category__name__icontains=value) |
                        Q(vendor__name__icontains=value)
                        for value in query_list
                    )
                )
            ).order_by("name")
        return result


class ProductDetailView(CompanyAccessMixin, DetailView):
    model = Item
    template_name = "store/productdetail.html"
    context_object_name = "item"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        recent_purchase_items = (
            PurchaseItem.objects
            .filter(item=self.object)
            .select_related("purchase", "purchase__vendor")
            .order_by("-purchase__order_date", "-id")
        )

        recent_sale_details = (
            SaleDetail.objects
            .filter(item=self.object)
            .select_related("sale", "sale__customer")
            .order_by("-sale__date_added", "-id")
        )

        latest_purchase_item = recent_purchase_items.first()

        context["recent_purchase_items"] = recent_purchase_items[:10]
        context["recent_sale_details"] = recent_sale_details[:10]
        context["latest_purchase_item"] = latest_purchase_item
        context["final_price"] = self.object.get_final_price()

        return context

class ProductCreateView(CoordinatorOrAdminMixin, CreateView):
    model = Item
    template_name = "store/productcreate.html"
    form_class = ItemForm
    success_url = reverse_lazy("productslist")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = filter_by_company(
            Category.objects.all(), self.request.user,
        ).order_by('name')
        context['vendors'] = filter_by_company(
            Vendor.objects.all(), self.request.user,
        ).order_by('name')
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = get_user_company(self.request.user)
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        assign_company(self.object, self.request.user)
        set_audit_user(self.object, self.request.user, is_create=True)
        self.object.save()
        return redirect(self.success_url)


class ProductUpdateView(CoordinatorOrAdminMixin, UpdateView):
    model = Item
    template_name = "store/productupdate.html"
    form_class = ItemForm
    success_url = reverse_lazy("productslist")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = get_user_company(self.request.user)
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = filter_by_company(
            Category.objects.all(), self.request.user,
        ).order_by('name')
        context['vendors'] = filter_by_company(
            Vendor.objects.all(), self.request.user,
        ).order_by('name')
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        set_audit_user(self.object, self.request.user)
        self.object.save()
        return redirect(self.success_url)


class ProductDeleteView(CompanyAdminRequiredMixin, ArchivableDeleteView):
    """Archive-only: never hard-deletes."""
    model = Item
    template_name = 'store/productdelete.html'
    success_url = reverse_lazy('productslist')

    @property
    def archive_success_message(self):
        return 'Product archived successfully.'


class DeliveryListView(CompanyAccessMixin, ExportMixin, tables.SingleTableView):
    model = Delivery
    pagination = 10
    template_name = "store/deliveries.html"
    context_object_name = "deliveries"

    def get_queryset(self):
        return super().get_queryset().select_related('item').order_by('-date', '-id')


class DeliverySearchListView(DeliveryListView):
    paginate_by = 10

    def get_queryset(self):
        result = super().get_queryset()

        query = self.request.GET.get("q")
        if query:
            query_list = query.split()
            result = result.filter(
                reduce(
                    operator.and_,
                    (Q(customer_name__icontains=value) for value in query_list)
                )
            )
        return result


class DeliveryDetailView(CompanyAccessMixin, DetailView):
    model = Delivery
    template_name = "store/deliverydetail.html"


class DeliveryCreateView(CoordinatorOrAdminMixin, CreateView):
    model = Delivery
    form_class = DeliveryForm
    template_name = "store/delivery_form.html"
    success_url = "/deliveries"


class DeliveryUpdateView(CoordinatorOrAdminMixin, UpdateView):
    model = Delivery
    form_class = DeliveryForm
    template_name = "store/delivery_form.html"
    success_url = "/deliveries"


class DeliveryDeleteView(CompanyAdminRequiredMixin, DeleteView):
    model = Delivery
    success_url = '/deliveries'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        messages.success(request, 'Delivery removed.')
        return redirect(self.success_url)


class CategoryListView(CompanyAccessMixin, ListView):
    model = Category
    template_name = "store/category_list.html"
    context_object_name = "categories"
    paginate_by = 10
    login_url = "login"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(
                item_count=Count('item'),
                name_lower=Lower('name'),
            )
            .order_by('name_lower', 'name')
        )


class CategoryDetailView(CompanyAccessMixin, DetailView):
    model = Category
    template_name = "store/category_detail.html"
    context_object_name = "category"
    login_url = "login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_items"] = (
            filter_by_company(
                Item.objects.filter(category=self.object),
                self.request.user,
            )
            .select_related("vendor")
            .order_by("name")
        )
        context["item_count"] = context["category_items"].count()
        context["total_quantity"] = (
            context["category_items"].aggregate(total=Sum("quantity")).get("total") or 0
        )
        return context


class CategoryCreateView(CoordinatorOrAdminMixin, CreateView):
    model = Category
    template_name = "store/category_form.html"
    form_class = CategoryForm
    login_url = "login"

    def form_valid(self, form):
        self.object = form.save(commit=False)
        assign_company(self.object, self.request.user)
        set_audit_user(self.object, self.request.user, is_create=True)
        self.object.save()
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy("category-detail", kwargs={"pk": self.object.pk})


class CategoryUpdateView(CoordinatorOrAdminMixin, UpdateView):
    model = Category
    template_name = "store/category_form.html"
    form_class = CategoryForm
    login_url = "login"

    def get_success_url(self):
        return reverse_lazy("category-detail", kwargs={"pk": self.object.pk})


class CategoryDeleteView(CompanyAdminRequiredMixin, ArchivableDeleteView):
    model = Category
    template_name = 'store/category_confirm_delete.html'
    success_url = reverse_lazy('category-list')
    login_url = 'login'

    @property
    def archive_success_message(self):
        return 'Category archived successfully.'

def is_ajax(request):
    return request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"


@csrf_exempt
@require_POST
@login_required
def get_items_ajax_view(request):
    if is_ajax(request):
        try:
            term = request.POST.get("term", "")
            data = []

            items = scoped_queryset(Item, request.user).filter(
                name__icontains=term,
            )
            for item in items[:10]:
                data.append(item.to_json())

            return JsonResponse(data, safe=False)
        except Exception as error:
            return JsonResponse({"error": str(error)}, status=500)

    return JsonResponse({"error": "Not an AJAX request"}, status=400)