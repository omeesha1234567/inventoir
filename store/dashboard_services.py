from datetime import timedelta

from django.db.models import Count, F, Sum
from django.utils import timezone

from accounts.models import Customer, Profile, ROLE_COORDINATOR, Vendor
from store.models import Category, Item
from transactions.models import Purchase, Sale


LOW_STOCK_THRESHOLD = 5


def _company_filter(company):
    return {'company': company}


def get_dashboard_metrics(company, *, coordinator=False):
    cf = _company_filter(company)
    today = timezone.now().date()

    sales_qs = Sale.active.filter(**cf)
    purchases_qs = Purchase.active.filter(**cf)
    items_qs = Item.active.filter(**cf)

    total_sales = sales_qs.aggregate(t=Sum('grand_total')).get('t') or 0
    total_purchases_count = purchases_qs.count()

    today_sales = sales_qs.filter(date_added__date=today).aggregate(
        t=Sum('grand_total'),
    ).get('t') or 0

    item_count = items_qs.count()
    inventory_value = items_qs.aggregate(
        total=Sum(F('price') * F('quantity')),
    ).get('total') or 0

    metrics = {
        'total_sales': total_sales,
        'total_purchases_count': total_purchases_count,
        'revenue': total_sales,
        'inventory_value': round(inventory_value, 2),
        'product_count': item_count,
        'items_count': item_count,
        'total_categories': Category.active.filter(**cf).count(),
        'sales_count': sales_qs.count(),
        'vendor_count': Vendor.active.filter(**cf).count(),
        'customer_count': Customer.active.filter(**cf).count(),
        'coordinator_count': Profile.objects.filter(
            company=company, role=ROLE_COORDINATOR, user__is_active=True,
        ).count(),
        'today_sales': today_sales,
        'recent_sales': sales_qs.select_related('customer').order_by('-date_added')[:5],
        'recent_purchases': purchases_qs.select_related('vendor').order_by('-order_date')[:5],
        'low_stock_items': items_qs.filter(quantity__lte=LOW_STOCK_THRESHOLD).order_by('quantity')[:10],
        'company': company,
    }
    return metrics
