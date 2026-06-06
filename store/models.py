from django.db import models
from django.urls import reverse
from django.forms import model_to_dict
from django_extensions.db.fields import AutoSlugField
from phonenumber_field.modelfields import PhoneNumberField

from accounts.models import Vendor
from companies.base import (
    ActiveCompanyManager,
    ArchivableModel,
    AuditedModel,
    CompanyOwnedModel,
)


class Category(CompanyOwnedModel, ArchivableModel, AuditedModel):
    name = models.CharField(max_length=50)
    slug = AutoSlugField(populate_from='name')

    objects = models.Manager()
    active = ActiveCompanyManager()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Categories'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'slug'],
                name='unique_category_slug_per_company',
            ),
        ]


class Item(CompanyOwnedModel, ArchivableModel, AuditedModel):
    slug = AutoSlugField(populate_from='name')
    name = models.CharField(max_length=50)
    description = models.TextField(max_length=256)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    price = models.FloatField(default=0)
    gst_percentage = models.FloatField(default=0)
    purchase_date = models.DateTimeField(null=True, blank=True)
    vendor = models.ForeignKey(
        Vendor, on_delete=models.SET_NULL, null=True, blank=True
    )

    objects = models.Manager()
    active = ActiveCompanyManager()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('product-detail', kwargs={'slug': self.slug})

    def get_final_price(self):
        return round(self.price + (self.price * self.gst_percentage / 100), 2)

    def to_json(self):
        product = model_to_dict(self)
        product['id'] = self.id
        product['text'] = self.name
        product['name'] = self.name
        product['category'] = self.category.name
        product['base_price'] = float(self.price)
        product['gst_percentage'] = float(self.gst_percentage)
        product['price'] = float(self.price)
        product['stock'] = int(self.quantity)
        product['quantity'] = 1
        product['margin'] = 0
        product['subtotal'] = 0
        product['total_product'] = 0
        return product

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Items'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'slug'],
                name='unique_item_slug_per_company',
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'quantity'], name='item_company_quantity_idx'),
        ]


class Delivery(CompanyOwnedModel):
    item = models.ForeignKey(
        Item, blank=True, null=True, on_delete=models.SET_NULL
    )
    customer_name = models.CharField(max_length=30, blank=True, null=True)
    phone_number = PhoneNumberField(blank=True, null=True)
    location = models.CharField(max_length=20, blank=True, null=True)
    date = models.DateTimeField()
    is_delivered = models.BooleanField(
        default=False, verbose_name='Is Delivered'
    )

    def __str__(self):
        return (
            f'Delivery of {self.item} to {self.customer_name} '
            f'at {self.location} on {self.date}'
        )
