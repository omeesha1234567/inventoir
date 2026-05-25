from django.db.models.signals import post_save
from django.dispatch import receiver

from transactions.models import Sale
from invoice.models import Invoice


@receiver(post_save, sender=Sale)
def create_invoice_after_sale(sender, instance, created, **kwargs):
    if created:
        Invoice.objects.get_or_create(
            sale=instance,
            defaults={
                "customer_name": str(instance.customer),
                "contact_number": instance.customer.phone or "",
                "total": float(instance.sub_total),
                "grand_total": float(instance.grand_total),
                "shipping": 0.00
            }
        )