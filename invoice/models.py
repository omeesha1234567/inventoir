from django.db import models
from django_extensions.db.fields import AutoSlugField

from store.models import Item
from companies.base import (
    ActiveCompanyManager,
    ArchivableModel,
    AuditedModel,
    CompanyOwnedModel,
)


class Invoice(CompanyOwnedModel, ArchivableModel, AuditedModel):
    slug = AutoSlugField(populate_from='date')

    sale = models.OneToOneField(
        "transactions.Sale",
        on_delete=models.CASCADE,
        related_name="invoice",
        null=True,
        blank=True,
    )

    date = models.DateTimeField(
        auto_now=True,
        verbose_name='Date',
    )

    customer_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    contact_number = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    customer_gst_number = models.CharField(
        max_length=30,
        blank=True,
        default='',
    )
    customer_address = models.TextField(
        blank=True,
        default='',
    )
    company_name = models.CharField(
        max_length=200,
        blank=True,
        default='',
    )
    company_gst_number = models.CharField(
        max_length=30,
        blank=True,
        default='',
    )
    company_phone = models.CharField(
        max_length=30,
        blank=True,
        default='',
    )
    company_address = models.TextField(
        blank=True,
        default='',
    )

    shipping = models.FloatField(
        verbose_name='Shipping and Handling',
        default=0.00,
    )

    total = models.FloatField(
        verbose_name='Total Amount',
        editable=False,
        default=0.00,
    )

    grand_total = models.FloatField(
        verbose_name='Grand Total',
        editable=False,
        default=0.00,
    )

    objects = models.Manager()
    active = ActiveCompanyManager()

    class Meta:
        ordering = ['-date', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'slug'],
                name='unique_invoice_slug_per_company',
            ),
        ]

    def save(self, *args, **kwargs):
        from invoice.services import sync_invoice_from_sale

        if self.sale:
            if self.company_id is None and self.sale.company_id:
                self.company = self.sale.company
            sync_invoice_from_sale(self, save=False)

        return super().save(*args, **kwargs)

    @property
    def items_count(self):
        return self.invoice_items.count()

    def __str__(self):
        if self.sale:
            return f"Invoice for Sale ID: {self.sale.id}"
        return self.slug


class InvoiceItem(CompanyOwnedModel):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="invoice_items",
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
    )

    price = models.FloatField(
        default=0.00,
        help_text='Unit rate before GST',
    )
    quantity = models.FloatField(default=0.00)
    gst_percentage = models.FloatField(default=0.00)
    line_total = models.FloatField(default=0.00)

    def save(self, *args, **kwargs):
        if self.company_id is None and self.invoice_id:
            self.company = self.invoice.company
        if self.line_total in (None, 0) and self.price and self.quantity:
            base = float(self.price) * float(self.quantity)
            gst = base * float(self.gst_percentage or 0) / 100
            self.line_total = round(base + gst, 2)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice} - {self.item.name}"
