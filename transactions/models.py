from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django_extensions.db.fields import AutoSlugField

from store.models import Item
from accounts.models import Vendor, Customer
from companies.base import (
    ActiveCompanyManager,
    ArchivableModel,
    AuditedModel,
    CompanyOwnedModel,
)

DELIVERY_CHOICES = [("P", "Pending"), ("S", "Successful")]

PAYMENT_MODE_CHOICES = [
    ("NONE", "None"),
    ("CASH", "Cash"),
    ("CREDIT_CARD", "Credit Card"),
    ("DEBIT_CARD", "Debit Card"),
    ("CHEQUE", "Cheque"),
    ("UPI", "UPI"),
    ("BANK_TRANSFER", "Bank Transfer"),
    ("OTHER", "Other"),
]


class Sale(CompanyOwnedModel, ArchivableModel, AuditedModel):
    date_added = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Sale Date",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.DO_NOTHING,
        db_column="customer",
    )
    sub_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
    )
    grand_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
    )
    tax_percentage = models.FloatField(default=0.0)
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
    )
    amount_change = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
    )
    customer_gst_number = models.CharField(
        max_length=30,
        blank=True,
        default='',
        verbose_name='Customer GST Number',
    )

    objects = models.Manager()
    active = ActiveCompanyManager()

    class Meta:
        db_table = "sales"
        verbose_name = "Sale"
        verbose_name_plural = "Sales"
        ordering = ['-date_added', '-id']
        indexes = [
            models.Index(fields=['company', 'date_added'], name='sale_company_date_added_idx'),
        ]

    def __str__(self):
        return (
            f"Sale ID: {self.id} | "
            f"Grand Total: {self.grand_total} | "
            f"Date: {self.date_added}"
        )

    @property
    def remaining_amount(self):
        remaining = self.grand_total - self.amount_paid
        if remaining < 0:
            return Decimal('0.00')
        return remaining

    @property
    def payment_status(self):
        if self.grand_total <= 0:
            return 'N/A'
        if self.remaining_amount <= 0:
            return 'Paid'
        if self.amount_paid > 0:
            return 'Partial'
        return 'Unpaid'

    def sync_payment_state(self, save=True):
        total_paid = self.payments.filter(is_archived=False).aggregate(
            total=Sum('amount'),
        ).get('total') or Decimal('0.00')

        if total_paid > self.grand_total:
            total_paid = self.grand_total

        self.amount_paid = total_paid
        self.amount_change = round(self.amount_paid - self.grand_total, 2)

        if save:
            self.save(update_fields=['amount_paid', 'amount_change'])

    def sum_(self):
        return sum(detail.quantity for detail in self.saledetail_set.all())


class SaleDetail(CompanyOwnedModel):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        db_column="sale",
        related_name="saledetail_set",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.DO_NOTHING,
        db_column="item",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    quantity = models.PositiveIntegerField()
    total_detail = models.DecimalField(max_digits=10, decimal_places=2)
    gst_percentage = models.FloatField(default=0.0)

    class Meta:
        db_table = "sale_details"
        verbose_name = "Sale Detail"
        verbose_name_plural = "Sale Details"

    def __str__(self):
        return (
            f"Detail ID: {self.id} | "
            f"Sale ID: {self.sale.id} | "
            f"Quantity: {self.quantity}"
        )


class Purchase(CompanyOwnedModel, ArchivableModel, AuditedModel):
    slug = AutoSlugField(populate_from="slug_source")
    vendor = models.ForeignKey(
        Vendor,
        related_name="purchases",
        on_delete=models.CASCADE,
    )
    invoice_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Invoice ID",
    )
    description = models.TextField(max_length=300, blank=True, null=True)
    order_date = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateField(
        blank=True, null=True, verbose_name="Delivery Date",
    )
    delivery_status = models.CharField(
        choices=DELIVERY_CHOICES,
        max_length=1,
        default="P",
        verbose_name="Delivery Status",
    )
    payment_mode = models.CharField(
        max_length=20,
        choices=PAYMENT_MODE_CHOICES,
        default="CASH",
        verbose_name="Payment Mode",
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
        verbose_name="Amount Paid",
    )

    objects = models.Manager()
    active = ActiveCompanyManager()

    class Meta:
        ordering = ["-order_date"]
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'slug'],
                name='unique_purchase_slug_per_company',
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'order_date'], name='purch_co_order_dt_idx'),
            models.Index(fields=['company', 'delivery_date'], name='purch_co_delivery_dt_idx'),
        ]

    @property
    def slug_source(self):
        if self.invoice_id:
            return self.invoice_id

        vendor_name = self.vendor.name if self.vendor else "purchase"
        if self.delivery_date:
            return f"{vendor_name}-{self.delivery_date}"
        return f"{vendor_name}-{self.order_date}"

    @property
    def total_value(self):
        total = self.purchase_items.aggregate(
            total=Sum("line_total"),
        ).get("total") or Decimal("0.00")
        return total

    @property
    def remaining_amount(self):
        remaining = self.total_value - self.amount_paid
        if remaining < 0:
            return Decimal("0.00")
        return remaining

    @property
    def items_count(self):
        return self.purchase_items.count()

    def sync_payment_state(self, save=True):
        total_paid = self.payments.filter(is_archived=False).aggregate(
            total=Sum("amount"),
        ).get("total") or Decimal("0.00")

        if total_paid > self.total_value:
            total_paid = self.total_value

        self.amount_paid = total_paid

        if self.total_value > 0 and self.amount_paid == self.total_value:
            self.delivery_status = "S"
        else:
            self.delivery_status = "P"

        if save:
            self.save(update_fields=["amount_paid", "delivery_status"])

    def __str__(self):
        if self.invoice_id:
            return f"{self.invoice_id} - {self.vendor.name}"
        return f"Purchase #{self.id} - {self.vendor.name}"


class PurchaseItem(CompanyOwnedModel):
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.CASCADE,
        related_name="purchase_items",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
    )
    quantity = models.PositiveIntegerField(default=0)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
    )
    gst_percentage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
    )
    line_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
    )

    def save(self, *args, **kwargs):
        base_total = Decimal(self.quantity) * Decimal(self.price)
        gst_amount = base_total * (Decimal(self.gst_percentage) / Decimal("100"))
        self.line_total = base_total + gst_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.purchase} - {self.item.name}"


class PurchasePayment(CompanyOwnedModel, ArchivableModel):
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    payment_mode = models.CharField(
        max_length=20,
        choices=PAYMENT_MODE_CHOICES,
        default="CASH",
    )
    note = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    paid_on = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()
    active = ActiveCompanyManager()

    class Meta:
        ordering = ["-paid_on", "-id"]

    def __str__(self):
        return f"Payment #{self.id} for Purchase #{self.purchase.id}"


class SalePayment(CompanyOwnedModel, ArchivableModel, AuditedModel):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='payments',
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    payment_mode = models.CharField(
        max_length=20,
        choices=PAYMENT_MODE_CHOICES,
        default='CASH',
    )
    note = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    paid_on = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()
    active = ActiveCompanyManager()

    class Meta:
        ordering = ['-paid_on', '-id']

    def __str__(self):
        return f'Payment #{self.id} for Sale #{self.sale_id}'
