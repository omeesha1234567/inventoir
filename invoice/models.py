from django.db import models
from django_extensions.db.fields import AutoSlugField

from store.models import Item


class Invoice(models.Model):
    slug = AutoSlugField(unique=True, populate_from='date')

    sale = models.OneToOneField(
        "transactions.Sale",
        on_delete=models.CASCADE,
        related_name="invoice",
        null=True,
        blank=True
    )

    date = models.DateTimeField(
        auto_now=True,
        verbose_name='Date'
    )

    customer_name = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    contact_number = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    shipping = models.FloatField(
        verbose_name='Shipping and Handling',
        default=0.00
    )

    total = models.FloatField(
        verbose_name='Total Amount',
        editable=False,
        default=0.00
    )

    grand_total = models.FloatField(
        verbose_name='Grand Total',
        editable=False,
        default=0.00
    )

    def save(self, *args, **kwargs):
        if self.sale:
            self.customer_name = str(self.sale.customer)

            if self.sale.customer and self.sale.customer.phone:
                self.contact_number = self.sale.customer.phone

            self.total = round(float(self.sale.sub_total), 2)
            self.grand_total = round(float(self.sale.grand_total), 2)

        return super().save(*args, **kwargs)

    @property
    def items_count(self):
        return self.invoice_items.count()

    def __str__(self):
        if self.sale:
            return f"Invoice for Sale ID: {self.sale.id}"
        return self.slug


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="invoice_items"
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE
    )

    price = models.FloatField(default=0.00)
    quantity = models.FloatField(default=0.00)
    line_total = models.FloatField(default=0.00)

    def save(self, *args, **kwargs):
        self.line_total = round(float(self.price) * float(self.quantity), 2)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice} - {self.item.name}"