from django.contrib import admin
from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ("item", "price", "quantity", "line_total")
    can_delete = False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "sale",
        "customer_name",
        "contact_number",
        "total",
        "shipping",
        "grand_total",
        "items_count",
        "date",
    )
    search_fields = ("customer_name", "contact_number", "sale__id")
    list_filter = ("date",)
    readonly_fields = (
        "sale",
        "customer_name",
        "contact_number",
        "total",
        "grand_total",
        "date",
        "items_count",
    )
    inlines = [InvoiceItemInline]


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ("id", "invoice", "item", "price", "quantity", "line_total")
    search_fields = ("invoice__id", "item__name")
    readonly_fields = ("line_total",)