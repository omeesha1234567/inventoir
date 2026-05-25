from django.contrib import admin
from .models import Sale, SaleDetail, Purchase, PurchaseItem


class SaleDetailInline(admin.TabularInline):
    model = SaleDetail
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "sub_total",
        "grand_total",
        "amount_paid",
        "amount_change",
        "date_added",
    )
    search_fields = ("customer__first_name", "customer__last_name", "id")
    list_filter = ("date_added",)
    inlines = [SaleDetailInline]


@admin.register(SaleDetail)
class SaleDetailAdmin(admin.ModelAdmin):
    list_display = ("id", "sale", "item", "price", "quantity", "total_detail")
    search_fields = ("sale__id", "item__name")


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0
    readonly_fields = ("item", "quantity", "price", "gst_percentage", "line_total")


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "vendor",
        "delivery_date",
        "delivery_status",
        "payment_mode",
        "amount_paid",
        "total_value",
        "remaining_amount",
        "items_count",
        "order_date",
    )
    search_fields = ("vendor__name", "id", "slug")
    list_filter = ("delivery_status", "payment_mode", "delivery_date", "order_date")
    inlines = [PurchaseItemInline]


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "purchase",
        "item",
        "quantity",
        "price",
        "gst_percentage",
        "line_total",
    )
    search_fields = ("purchase__id", "item__name")