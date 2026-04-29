import operator
from functools import reduce

from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Sum

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from django.views.generic import (
    DetailView, CreateView, UpdateView, DeleteView, ListView
)
from django.views.generic.edit import FormMixin

from django_tables2 import SingleTableView
import django_tables2 as tables
from django_tables2.export.views import ExportMixin

from accounts.models import Profile, Vendor
from transactions.models import Sale
from .models import Category, Item, Delivery
from .forms import ItemForm, CategoryForm, DeliveryForm
from .tables import ItemTable


@login_required
def dashboard(request):
    profiles = Profile.objects.all()
    items = Item.objects.all()

    total_items = (
        Item.objects.aggregate(Sum("quantity")).get("quantity__sum") or 0
    )

    items_count = items.count()
    profiles_count = profiles.count()

    category_data = Category.objects.annotate(
        item_count=Count("item")
    ).values("name", "item_count")

    categories = [entry["name"] for entry in category_data]
    category_counts = [entry["item_count"] for entry in category_data]

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
        float(entry["total_sales"]) for entry in sale_dates
    ]

    context = {
        "items": items,
        "profiles": profiles,
        "profiles_count": profiles_count,
        "items_count": items_count,
        "total_items": total_items,
        "vendors": Vendor.objects.all(),
        "delivery": Delivery.objects.all(),
        "sales": Sale.objects.all(),
        "categories": categories,
        "category_counts": category_counts,
        "sale_dates_labels": sale_dates_labels,
        "sale_dates_values": sale_dates_values,
    }
    return render(request, "store/dashboard.html", context)


class ProductListView(LoginRequiredMixin, ExportMixin, tables.SingleTableView):
    model = Item
    table_class = ItemTable
    template_name = "store/productslist.html"
    context_object_name = "items"
    paginate_by = 10
    SingleTableView.table_pagination = False


class ItemSearchListView(ProductListView):
    paginate_by = 10

    def get_queryset(self):
        result = super().get_queryset()

        query = self.request.GET.get("q")
        if query:
            query_list = query.split()
            result = result.filter(
                reduce(
                    operator.and_,
                    (Q(name__icontains=value) for value in query_list)
                )
            )
        return result


class ProductDetailView(LoginRequiredMixin, FormMixin, DetailView):
    model = Item
    template_name = "store/productdetail.html"

    def get_success_url(self):
        return reverse("product-detail", kwargs={"slug": self.object.slug})


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
    success_url = "/products"

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        return False


class ProductDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Item
    template_name = "store/productdelete.html"
    success_url = "/products"

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        return False


class DeliveryListView(
    LoginRequiredMixin, ExportMixin, tables.SingleTableView
):
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
        if self.request.user.is_superuser:
            return True
        return False


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = "store/category_list.html"
    context_object_name = "categories"
    paginate_by = 10
    login_url = "login"


class CategoryDetailView(LoginRequiredMixin, DetailView):
    model = Category
    template_name = "store/category_detail.html"
    context_object_name = "category"
    login_url = "login"


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