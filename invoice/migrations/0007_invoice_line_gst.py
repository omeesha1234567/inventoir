# Generated manually for invoice line GST and customer address snapshot

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0006_stabilization'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='customer_address',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='invoiceitem',
            name='gst_percentage',
            field=models.FloatField(default=0.0),
        ),
    ]
