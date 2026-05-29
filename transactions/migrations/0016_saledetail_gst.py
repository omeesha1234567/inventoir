# Generated manually — persist GST % on sale lines for invoice mapping

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0014_stabilization'),
    ]

    operations = [
        migrations.AddField(
            model_name='saledetail',
            name='gst_percentage',
            field=models.FloatField(default=0.0),
        ),
    ]
