from django.db import models

from companies.codes import generate_unique_company_code


class Company(models.Model):
    name = models.CharField(max_length=200, verbose_name='Company Name')
    company_code = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name='Company Code',
    )
    gst_number = models.CharField(max_length=30, verbose_name='GST Number')
    email = models.EmailField(max_length=254)
    phone = models.CharField(max_length=30)
    address = models.TextField()
    owner_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.company_code})'

    def save(self, *args, **kwargs):
        if not self.company_code:
            self.company_code = generate_unique_company_code()
        super().save(*args, **kwargs)
