from datetime import date, timedelta
from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    FloatField,
    Max,
    Min,
    Q,
    Sum,
)
from django.db.models.functions import (
    TruncDay,
    TruncMonth,
    TruncQuarter,
    TruncWeek,
    TruncYear,
)
from django.utils import timezone

from accounts.models import Customer, Vendor
from store.models import Item
from transactions.models import Purchase, PurchaseItem, Sale, SaleDetail


def resolve_date_range(filter_name, start_date=None, end_date=None):
    today = timezone.localdate()
    if filter_name == 'today':
        return today, today
    if filter_name == 'last_7_days':
        return today - timedelta(days=6), today
    if filter_name == 'last_30_days':
        return today - timedelta(days=29), today
    if filter_name == 'this_month':
        start = today.replace(day=1)
        return start, today
    if filter_name == 'last_month':
        first = today.replace(day=1)
        last = first - timedelta(days=1)
        start = last.replace(day=1)
        return start, last
    if filter_name == 'this_quarter':
        quarter = ((today.month - 1) // 3) + 1
        start_month = 3 * (quarter - 1) + 1
        start = date(today.year, start_month, 1)
        return start, today
    if filter_name == 'this_year':
        start = date(today.year, 1, 1)
        return start, today
    if filter_name == 'custom':
        if not start_date or not end_date:
            raise ValueError('Custom range requires start_date and end_date.')
        return start_date, end_date
    return today - timedelta(days=29), today


def get_previous_period(start_date, end_date):
    interval = end_date - start_date
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - interval
    return previous_start, previous_end


def growth_rate(current, previous):
    try:
        current = Decimal(current or 0)
        previous = Decimal(previous or 0)
        if previous == 0:
            return 100 if current > 0 else 0
        return float(((current - previous) / previous) * Decimal(100))
    except Exception:
        return 0.0


def _round(value, precision=2):
    try:
        return float(round(Decimal(value or 0), precision))
    except Exception:
        return 0.0


def get_overview_metrics(company, start_date, end_date):
    sales_qs = Sale.active.filter(company=company, date_added__date__range=(start_date, end_date))
    purchases_qs = Purchase.active.filter(company=company, delivery_date__range=(start_date, end_date))

    total_revenue = sales_qs.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
    total_purchase_value = purchases_qs.annotate(
        total_value=Sum('purchase_items__line_total')
    ).aggregate(total=Sum('total_value'))['total'] or Decimal('0.00')
    total_customers = Customer.active.filter(company=company).count()
    total_vendors = Vendor.active.filter(company=company).count()
    inventory_value = Item.active.filter(company=company).aggregate(
        total=Sum(
            ExpressionWrapper(
                F('price') * F('quantity'), output_field=FloatField()
            )
        )
    )['total'] or 0.0

    outstanding_receivables = sales_qs.aggregate(
        total=Sum(
            ExpressionWrapper(
                F('grand_total') - F('amount_paid'),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        )
    )['total'] or Decimal('0.00')

    purchase_values = purchases_qs.annotate(
        total_value=Sum('purchase_items__line_total')
    )
    outstanding_payables = purchase_values.aggregate(
        total=Sum(
            ExpressionWrapper(
                F('total_value') - F('amount_paid'),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        )
    )['total'] or Decimal('0.00')

    sales_count = sales_qs.count()
    purchase_count = purchases_qs.count()
    average_order_value = (
        total_revenue / sales_count if sales_count else Decimal('0.00')
    )

    previous_start, previous_end = get_previous_period(start_date, end_date)
    previous_sales = Sale.active.filter(company=company, date_added__date__range=(previous_start, previous_end))
    previous_purchases = Purchase.active.filter(company=company, delivery_date__range=(previous_start, previous_end))
    previous_revenue = previous_sales.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
    previous_sales_count = previous_sales.count()
    previous_purchase_count = previous_purchases.count()

    return {
        'total_revenue': float(total_revenue),
        'total_purchase_value': float(total_purchase_value),
        'sales_count': sales_count,
        'purchase_count': purchase_count,
        'total_customers': total_customers,
        'total_vendors': total_vendors,
        'inventory_value': float(round(inventory_value, 2)),
        'outstanding_receivables': float(outstanding_receivables),
        'outstanding_payables': float(outstanding_payables),
        'average_order_value': float(round(average_order_value, 2)),
        'revenue_growth': growth_rate(total_revenue, previous_revenue),
        'sales_growth': growth_rate(sales_count, previous_sales_count),
        'purchase_growth': growth_rate(purchase_count, previous_purchase_count),
        'daily_trend': _trend_rows(sales_qs, TruncDay),
    }


def _trend_queryset(queryset, trunc_func, field_name='date_added'):
    return (
        queryset
        .annotate(period=trunc_func(field_name))
        .values('period')
        .annotate(total=Sum('grand_total'))
        .order_by('period')
    )


def _trend_rows(queryset, trunc_func, field_name='date_added'):
    rows = _trend_queryset(queryset, trunc_func, field_name)
    return [
        {
            'period': row['period'].date().isoformat() if row['period'] else None,
            'value': float(row['total'] or 0),
        }
        for row in rows
    ]


def get_revenue_metrics(company, start_date, end_date):
    sales_qs = Sale.active.filter(company=company, date_added__date__range=(start_date, end_date))
    category_qs = SaleDetail.objects.filter(
        company=company,
        sale__date_added__date__range=(start_date, end_date),
    ).values('item__category__name').annotate(
        revenue=Sum('total_detail')
    ).order_by('-revenue')
    customer_qs = sales_qs.values(
        'customer__id', 'customer__first_name', 'customer__last_name'
    ).annotate(revenue=Sum('grand_total')).order_by('-revenue')[:12]

    return {
        'daily_trend': _trend_rows(sales_qs, TruncDay),
        'weekly_trend': _trend_rows(sales_qs, TruncWeek),
        'monthly_trend': _trend_rows(sales_qs, TruncMonth),
        'quarterly_trend': _trend_rows(sales_qs, TruncQuarter),
        'yearly_trend': _trend_rows(sales_qs, TruncYear),
        'revenue_by_category': [
            {'category': row['item__category__name'] or 'Uncategorized', 'value': float(row['revenue'] or 0)}
            for row in category_qs
        ],
        'revenue_by_customer': [
            {
                'name': f"{row['customer__first_name']} {row['customer__last_name'] or ''}".strip(),
                'value': float(row['revenue'] or 0),
            }
            for row in customer_qs
        ],
    }


def get_purchase_metrics(company, start_date, end_date):
    purchase_values = Purchase.active.filter(company=company, delivery_date__range=(start_date, end_date)).annotate(
        total_value=Sum('purchase_items__line_total')
    )
    vendor_qs = purchase_values.values(
        'vendor__id', 'vendor__name'
    ).annotate(spend=Sum('purchase_items__line_total')).order_by('-spend')[:15]

    return {
        'daily_trend': [
            {
                'period': row['period'].date().isoformat() if row['period'] else None,
                'value': float(row['total'] or 0),
            }
            for row in purchase_values.annotate(period=TruncDay('delivery_date')).values('period').annotate(total=Sum('purchase_items__line_total')).order_by('period')
        ],
        'monthly_trend': [
            {
                'period': row['period'].date().isoformat() if row['period'] else None,
                'value': float(row['total'] or 0),
            }
            for row in purchase_values.annotate(period=TruncMonth('delivery_date')).values('period').annotate(total=Sum('purchase_items__line_total')).order_by('period')
        ],
        'vendor_trend': [
            {'vendor': row['vendor__name'] or 'Unknown', 'value': float(row['spend'] or 0)}
            for row in vendor_qs
        ],
    }


def get_product_metrics(company, start_date, end_date, dead_stock_days=90):
    product_qs = SaleDetail.objects.filter(
        company=company,
        sale__date_added__date__range=(start_date, end_date),
    ).select_related('item')
    sold_groups = product_qs.values(
        'item__id', 'item__name'
    ).annotate(
        quantity=Sum('quantity'),
        revenue=Sum('total_detail'),
    )
    top_selling = sold_groups.order_by('-quantity')[:12]
    top_revenue = sold_groups.order_by('-revenue')[:12]
    worst_selling = sold_groups.order_by('revenue')[:12]
    threshold_date = timezone.localdate() - timedelta(days=dead_stock_days)
    dead_stock_qs = Item.active.filter(company=company, quantity__gt=0).annotate(
        last_sold=Max('saledetail__sale__date_added')
    ).filter(Q(last_sold__lt=threshold_date) | Q(last_sold__isnull=True)).order_by('quantity')[:50]
    category_value = Item.active.filter(company=company).values(
        'category__name'
    ).annotate(value=Sum(ExpressionWrapper(F('price') * F('quantity'), output_field=FloatField()))).order_by('-value')

    return {
        'top_selling_products': [
            {'name': row['item__name'], 'quantity': int(row['quantity'] or 0)}
            for row in top_selling
        ],
        'top_revenue_products': [
            {'name': row['item__name'], 'revenue': float(row['revenue'] or 0)}
            for row in top_revenue
        ],
        'worst_performing_products': [
            {'name': row['item__name'], 'revenue': float(row['revenue'] or 0)}
            for row in worst_selling
        ],
        'dead_stock': [
            {
                'name': item.name,
                'quantity': int(item.quantity),
                'last_sold': item.last_sold.isoformat() if item.last_sold else None,
            }
            for item in dead_stock_qs
        ],
        'inventory_value_by_category': [
            {'category': row['category__name'] or 'Uncategorized', 'value': float(row['value'] or 0)}
            for row in category_value
        ],
    }


def get_customer_metrics(company, start_date, end_date):
    sales_qs = Sale.active.filter(company=company, date_added__date__range=(start_date, end_date))
    customer_qs = sales_qs.values(
        'customer__id', 'customer__first_name', 'customer__last_name'
    ).annotate(
        revenue=Sum('grand_total'),
        orders=Count('id'),
    ).order_by('-revenue')[:15]
    total_revenue = sales_qs.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
    average_order_value = total_revenue / sales_qs.count() if sales_qs.count() else Decimal('0.00')
    new_customers = Customer.active.filter(
        company=company,
        sale__date_added__date__range=(start_date, end_date),
    ).exclude(sale__date_added__date__lt=start_date).distinct().count()
    returning_customers = Customer.active.filter(
        company=company,
        sale__date_added__date__range=(start_date, end_date),
        sale__date_added__date__lt=start_date,
    ).distinct().count()

    return {
        'customer_lifetime_value': [
            {
                'name': f"{row['customer__first_name']} {row['customer__last_name'] or ''}".strip(),
                'revenue': float(row['revenue'] or 0),
                'orders': row['orders'],
            }
            for row in customer_qs
        ],
        'top_customers_by_revenue': [
            {'name': f"{row['customer__first_name']} {row['customer__last_name'] or ''}".strip(), 'value': float(row['revenue'] or 0)}
            for row in customer_qs[:12]
        ],
        'top_customers_by_order_count': [
            {'name': f"{row['customer__first_name']} {row['customer__last_name'] or ''}".strip(), 'orders': row['orders']}
            for row in sorted(customer_qs, key=lambda r: r['orders'], reverse=True)[:12]
        ],
        'average_order_value': float(round(average_order_value, 2)),
        'new_customers': new_customers,
        'returning_customers': returning_customers,
    }


def get_vendor_metrics(company, start_date, end_date):
    purchase_qs = Purchase.active.filter(company=company, delivery_date__range=(start_date, end_date)).annotate(
        total_value=Sum('purchase_items__line_total')
    )
    vendor_qs = purchase_qs.values(
        'vendor__id', 'vendor__name'
    ).annotate(
        spend=Sum('purchase_items__line_total'),
        frequency=Count('id'),
    ).order_by('-spend')[:20]
    total_spend = vendor_qs.aggregate(total=Sum('spend'))['total'] or Decimal('0.00')

    return {
        'vendor_spend_ranking': [
            {
                'name': row['vendor__name'] or 'Unknown',
                'spend': float(row['spend'] or 0),
                'frequency': row['frequency'],
                'contribution': float(round((row['spend'] / total_spend * 100) if total_spend else 0, 2)),
            }
            for row in vendor_qs
        ],
    }


def get_payment_metrics(company, start_date, end_date):
    sales_qs = Sale.active.filter(company=company, date_added__date__range=(start_date, end_date))
    purchase_qs = Purchase.active.filter(company=company, delivery_date__range=(start_date, end_date)).annotate(
        total_value=Sum('purchase_items__line_total')
    )
    outstanding_receivables = sales_qs.aggregate(
        total=Sum(
            ExpressionWrapper(
                F('grand_total') - F('amount_paid'),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        )
    )['total'] or Decimal('0.00')
    outstanding_payables = purchase_qs.aggregate(
        total=Sum(
            ExpressionWrapper(
                F('total_value') - F('amount_paid'),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        )
    )['total'] or Decimal('0.00')
    partial_sales = sales_qs.filter(amount_paid__gt=0).filter(amount_paid__lt=F('grand_total')).count()
    unpaid_sales = sales_qs.filter(amount_paid=0, grand_total__gt=0).count()
    partial_purchases = purchase_qs.filter(amount_paid__gt=0).filter(amount_paid__lt=F('total_value')).count()
    unpaid_purchases = purchase_qs.filter(amount_paid=0, total_value__gt=0).count()

    return {
        'outstanding_receivables': float(outstanding_receivables),
        'partial_sales': partial_sales,
        'unpaid_sales': unpaid_sales,
        'outstanding_payables': float(outstanding_payables),
        'partial_purchases': partial_purchases,
        'unpaid_purchases': unpaid_purchases,
    }


def get_insights(company, start_date, end_date):
    overview = get_overview_metrics(company, start_date, end_date)
    previous_start, previous_end = get_previous_period(start_date, end_date)
    previous_overview = get_overview_metrics(company, previous_start, previous_end)
    product_metrics = get_product_metrics(company, start_date, end_date, dead_stock_days=90)
    customer_metrics = get_customer_metrics(company, start_date, end_date)
    vendor_metrics = get_vendor_metrics(company, start_date, end_date)

    revenue_growth = overview['revenue_growth']
    top_vendor = next(iter(vendor_metrics['vendor_spend_ranking']), None)
    top_customer = next(iter(customer_metrics['customer_lifetime_value']), None)
    dead_stock_count = len(product_metrics['dead_stock'])
    inventory_delta = overview['inventory_value'] - get_overview_metrics(company, previous_start, previous_end)['inventory_value']
    business_health_score = _compute_health_score(overview, previous_overview, dead_stock_count)

    insights = [
        {
            'title': 'Revenue velocity',
            'message': f"Revenue { 'increased' if revenue_growth >= 0 else 'decreased' } {abs(round(revenue_growth, 2))}% compared to the previous period.",
        },
        {
            'title': 'Vendor strength',
            'message': f"{top_vendor['name']} contributes {round(top_vendor['contribution'], 2)}% of purchase spend." if top_vendor else 'No vendor purchase data available.',
        },
        {
            'title': 'Customer concentration',
            'message': f"{top_customer['name']} accounts for {round(top_customer['revenue'] / (overview['total_revenue'] or 1) * 100, 2)}% of revenue." if top_customer and overview['total_revenue'] else 'No customer revenue data available.',
        },
        {
            'title': 'Dead stock alert',
            'message': f"{dead_stock_count} products have not sold in 90 days or more.",
        },
        {
            'title': 'Inventory movement',
            'message': f"Inventory value changed by ₹{round(inventory_delta, 2)} compared to the previous period.",
        },
    ]

    return {
        'business_health_score': int(max(0, min(100, business_health_score))),
        'insights': insights,
    }


def _compute_health_score(current, previous, dead_stock_count):
    score = 72.0
    score += max(-15.0, min(15.0, current['revenue_growth'] * 0.1))
    receivables_ratio = (current['outstanding_receivables'] / (current['total_revenue'] or Decimal('1.0'))) * 100
    score -= min(receivables_ratio * 0.08, 15.0)
    payables_ratio = (current['outstanding_payables'] / (current['total_purchase_value'] or Decimal('1.0'))) * 100
    score -= min(payables_ratio * 0.05, 12.0)
    stock_penalty = min(dead_stock_count * 0.5, 10.0)
    score -= stock_penalty
    growth_delta = current['revenue_growth'] - previous['revenue_growth']
    score += max(-8.0, min(8.0, growth_delta * 0.05))
    return round(score, 0)
