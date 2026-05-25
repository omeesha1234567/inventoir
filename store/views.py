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
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

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

@login_required
def dashboard(request):
    profiles = Profile.objects.all()
    items = Item.objects.all()

    total_items = Item.objects.aggregate(
        total_quantity=Sum("quantity")
    ).get("total_quantity") or 0

    items_count = items.count()
    profiles_count = profiles.count()
    sales_count = Sale.objects.count()
    total_categories = Category.objects.count()

    sale_dates = (
        Sale.objects.values("date_added__date")
        .annotate(total_sales=Sum("grand_total"))
        .order_by("date_added__date")
    )

    sale_dates_labels = [
        entry["date_added__date"].strftime("%Y-%m-%d")
        for entry in sale_dates
        if entry["date_added__date"]
    ]
    sale_dates_values = [
        float(entry["total_sales"] or 0)
        for entry in sale_dates
        if entry["date_added__date"]
    ]

    purchase_dates = (
        Purchase.objects.values("delivery_date")
        .annotate(total_purchases=Count("id"))
        .order_by("delivery_date")
    )

    purchase_dates_labels = [
        entry["delivery_date"].strftime("%Y-%m-%d")
        for entry in purchase_dates
        if entry["delivery_date"]
    ]
    purchase_dates_values = [
        int(entry["total_purchases"] or 0)
        for entry in purchase_dates
        if entry["delivery_date"]
    ]

    context = {
        "items": items,
        "profiles": profiles,
        "profiles_count": profiles_count,
        "items_count": items_count,
        "total_items": total_items,
        "total_categories": total_categories,
        "sales_count": sales_count,
        "vendors": Vendor.objects.all(),
        "delivery": Delivery.objects.all(),
        "sales": Sale.objects.all(),
        "sale_dates_labels": sale_dates_labels,
        "sale_dates_values": sale_dates_values,
        "purchase_dates_labels": purchase_dates_labels,
        "purchase_dates_values": purchase_dates_values,
    }

    response = render(request, "store/dashboard.html", context)
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


class ProductListView(LoginRequiredMixin, ExportMixin, tables.SingleTableView):
    model = Item
    table_class = ItemTable
    template_name = "store/productslist.html"
    context_object_name = "items"
    paginate_by = 10
    tables.SingleTableView.table_pagination = False

    def get_queryset(self):
        return Item.objects.select_related("category", "vendor").order_by("name")


class ItemSearchListView(ProductListView):
    paginate_by = 10

    def get_queryset(self):
        result = Item.objects.select_related("category", "vendor").all().order_by("name")

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


class ProductDetailView(LoginRequiredMixin, DetailView):
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

class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Item
    template_name = "store/productcreate.html"
    form_class = ItemForm
    success_url = reverse_lazy("productslist")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all().order_by("name")
        context["vendors"] = Vendor.objects.all().order_by("name")
        return context


class ProductUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Item
    template_name = "store/productupdate.html"
    form_class = ItemForm
    success_url = reverse_lazy("productslist")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all().order_by("name")
        context["vendors"] = Vendor.objects.all().order_by("name")
        return context

    def test_func(self):
        return self.request.user.is_superuser


class ProductDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Item
    template_name = "store/productdelete.html"
    success_url = reverse_lazy("productslist")

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        used_in_sales = SaleDetail.objects.filter(item=self.object).exists()
        used_in_purchases = PurchaseItem.objects.filter(item=self.object).exists()

        if used_in_sales or used_in_purchases:
            messages.error(
                request,
                "This product cannot be deleted because it is already linked to sales or purchases."
            )
            return redirect("productslist")

        messages.success(request, "Product deleted successfully.")
        return super().post(request, *args, **kwargs)


class DeliveryListView(LoginRequiredMixin, ExportMixin, tables.SingleTableView):
    model = Delivery
    pagination = 10
    template_name = "store/deliveries.html"
    context_object_name = "deliveries"


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


class DeliveryDetailView(LoginRequiredMixin, DetailView):
    model = Delivery
    template_name = "store/deliverydetail.html"


class DeliveryCreateView(LoginRequiredMixin, CreateView):
    model = Delivery
    form_class = DeliveryForm
    template_name = "store/delivery_form.html"
    success_url = "/deliveries"


class DeliveryUpdateView(LoginRequiredMixin, UpdateView):
    model = Delivery
    form_class = DeliveryForm
    template_name = "store/delivery_form.html"
    success_url = "/deliveries"


class DeliveryDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Delivery
    template_name = "store/productdelete.html"
    success_url = "/deliveries"

    def test_func(self):
        return self.request.user.is_superuser


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = "store/category_list.html"
    context_object_name = "categories"
    paginate_by = 10
    login_url = "login"

    def get_queryset(self):
        return (
            Category.objects
            .annotate(
                item_count=Count("item"),
                name_lower=Lower("name")
            )
            .order_by("name_lower", "name")
        )


class CategoryDetailView(LoginRequiredMixin, DetailView):
    model = Category
    template_name = "store/category_detail.html"
    context_object_name = "category"
    login_url = "login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_items"] = (
            Item.objects
            .filter(category=self.object)
            .select_related("vendor")
            .order_by("name")
        )
        context["item_count"] = context["category_items"].count()
        context["total_quantity"] = (
            context["category_items"].aggregate(total=Sum("quantity")).get("total") or 0
        )
        return context


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    template_name = "store/category_form.html"
    form_class = CategoryForm
    login_url = "login"

    def get_success_url(self):
        return reverse_lazy("category-detail", kwargs={"pk": self.object.pk})


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    template_name = "store/category_form.html"
    form_class = CategoryForm
    login_url = "login"

    def get_success_url(self):
        return reverse_lazy("category-detail", kwargs={"pk": self.object.pk})


class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = "store/category_confirm_delete.html"
    context_object_name = "category"
    success_url = reverse_lazy("category-list")
    login_url = "login"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        category_items = Item.objects.filter(category=self.object)

        if not category_items.exists():
            messages.success(request, "Category deleted successfully.")
            return super().post(request, *args, **kwargs)

        used_in_sales = SaleDetail.objects.filter(item__in=category_items).exists()
        used_in_purchases = PurchaseItem.objects.filter(item__in=category_items).exists()

        if used_in_sales or used_in_purchases:
            messages.error(
                request,
                "This category cannot be deleted because one or more items in it are already linked to sales or purchases."
            )
            return redirect("category-detail", pk=self.object.pk)

        category_items.delete()
        messages.success(request, "Category and its unused items deleted successfully.")
        return super().post(request, *args, **kwargs)

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

            items = Item.objects.filter(name__icontains=term)
            for item in items[:10]:
                data.append(item.to_json())

            return JsonResponse(data, safe=False)
        except Exception as error:
            return JsonResponse({"error": str(error)}, status=500)

    return JsonResponse({"error": "Not an AJAX request"}, status=400)