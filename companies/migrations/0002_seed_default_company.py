from django.db import migrations


def seed_default_company(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    Profile = apps.get_model('accounts', 'Profile')
    User = apps.get_model('auth', 'User')

    company, _ = Company.objects.get_or_create(
        company_code='INV-DEFAULT',
        defaults={
            'name': 'Default Company',
            'gst_number': 'NA',
            'email': 'default@inventoir.local',
            'phone': '0000000000',
            'address': 'Default',
            'owner_name': 'System',
            'is_active': True,
        },
    )

    model_names = [
        ('accounts', 'Customer'),
        ('accounts', 'Vendor'),
        ('store', 'Category'),
        ('store', 'Item'),
        ('store', 'Delivery'),
        ('transactions', 'Sale'),
        ('transactions', 'SaleDetail'),
        ('transactions', 'Purchase'),
        ('transactions', 'PurchaseItem'),
        ('transactions', 'PurchasePayment'),
        ('invoice', 'Invoice'),
        ('invoice', 'InvoiceItem'),
    ]

    for app_label, model_name in model_names:
        Model = apps.get_model(app_label, model_name)
        if hasattr(Model, 'company_id'):
            Model.objects.filter(company__isnull=True).update(company=company)

    role_map = {
        'AD': 'CA',
        'EX': 'CO',
        'OP': 'CO',
    }
    for profile in Profile.objects.all():
        if profile.company_id is None and not profile.user.is_superuser:
            profile.company = company
        if profile.role in role_map:
            profile.role = role_map[profile.role]
        elif profile.role is None:
            profile.role = 'CO'
        profile.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_multi_company_saas'),
        ('accounts', '0004_multi_company_saas'),
        ('store', '0006_multi_company_saas'),
        ('transactions', '0013_multi_company_saas'),
        ('invoice', '0005_multi_company_saas'),
    ]

    operations = [
        migrations.RunPython(seed_default_company, noop_reverse),
    ]
