from csv import DictWriter
from datetime import datetime
from io import StringIO
from decimal import Decimal

from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from openpyxl import Workbook

from accounts.mixins import CompanyAdminRequiredMixin
from accounts.utils import get_default_company, get_user_company
from .services import (
    get_customer_metrics,
    resolve_date_range,
    get_insights,
    get_overview_metrics,
    get_product_metrics,
    get_purchase_metrics,
    get_revenue_metrics,
    get_vendor_metrics,
    get_payment_metrics,
)

TAB_NAMES = [
    'overview',
    'revenue',
    'purchases',
    'products',
    'customers',
    'vendors',
    'payments',
    'insights',
]

DATE_FILTERS = [
    ('today', 'Today'),
    ('last_7_days', 'Last 7 Days'),
    ('last_30_days', 'Last 30 Days'),
    ('this_month', 'This Month'),
    ('last_month', 'Last Month'),
    ('this_quarter', 'This Quarter'),
    ('this_year', 'This Year'),
    ('custom', 'Custom Range'),
]


def resolve_company(request):
    company = get_user_company(request.user)
    if company is None and request.user.is_superuser:
        company = get_default_company()
    return company


def get_tab_date_range(request):
    filter_key = request.GET.get('filter', 'last_30_days')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        start_date = parse_date(start_date)
    if end_date:
        end_date = parse_date(end_date)
    try:
        return resolve_date_range(filter_key, start_date, end_date)
    except ValueError as exc:
        raise ValueError(str(exc))


class AnalyticsDashboardView(CompanyAdminRequiredMixin, TemplateView):
    template_name = 'analytics/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tabs'] = TAB_NAMES
        context['date_filters'] = DATE_FILTERS
        context['initial_tab'] = 'overview'
        return context


class AnalyticsTabTemplateView(CompanyAdminRequiredMixin, View):
    def get(self, request, tab):
        if tab not in TAB_NAMES:
            return HttpResponseBadRequest('Invalid analytics tab.')
        return render(request, f'analytics/tabs/{tab}.html', {'tab': tab})


class AnalyticsDataViewBase(CompanyAdminRequiredMixin, View):
    def get_company(self):
        return resolve_company(self.request)

    def get_date_range(self):
        return get_tab_date_range(self.request)

    def error_response(self, message, status=400):
        return JsonResponse({'error': message}, status=status)


class AnalyticsOverviewDataView(AnalyticsDataViewBase):
    def get(self, request):
        company = self.get_company()
        if company is None:
            return self.error_response('Company context is required.')
        try:
            start_date, end_date = self.get_date_range()
        except ValueError as exc:
            return self.error_response(str(exc))
        data = get_overview_metrics(company, start_date, end_date)
        return JsonResponse(data)


class AnalyticsRevenueDataView(AnalyticsDataViewBase):
    def get(self, request):
        company = self.get_company()
        if company is None:
            return self.error_response('Company context is required.')
        try:
            start_date, end_date = self.get_date_range()
        except ValueError as exc:
            return self.error_response(str(exc))
        data = get_revenue_metrics(company, start_date, end_date)
        return JsonResponse(data)


class AnalyticsPurchasesDataView(AnalyticsDataViewBase):
    def get(self, request):
        company = self.get_company()
        if company is None:
            return self.error_response('Company context is required.')
        try:
            start_date, end_date = self.get_date_range()
        except ValueError as exc:
            return self.error_response(str(exc))
        data = get_purchase_metrics(company, start_date, end_date)
        return JsonResponse(data)


class AnalyticsProductsDataView(AnalyticsDataViewBase):
    def get(self, request):
        company = self.get_company()
        if company is None:
            return self.error_response('Company context is required.')
        try:
            start_date, end_date = self.get_date_range()
        except ValueError as exc:
            return self.error_response(str(exc))
        days = int(request.GET.get('dead_stock_days', 90))
        data = get_product_metrics(company, start_date, end_date, dead_stock_days=days)
        return JsonResponse(data)


class AnalyticsCustomersDataView(AnalyticsDataViewBase):
    def get(self, request):
        company = self.get_company()
        if company is None:
            return self.error_response('Company context is required.')
        try:
            start_date, end_date = self.get_date_range()
        except ValueError as exc:
            return self.error_response(str(exc))
        data = get_customer_metrics(company, start_date, end_date)
        return JsonResponse(data)


class AnalyticsVendorsDataView(AnalyticsDataViewBase):
    def get(self, request):
        company = self.get_company()
        if company is None:
            return self.error_response('Company context is required.')
        try:
            start_date, end_date = self.get_date_range()
        except ValueError as exc:
            return self.error_response(str(exc))
        data = get_vendor_metrics(company, start_date, end_date)
        return JsonResponse(data)


class AnalyticsPaymentsDataView(AnalyticsDataViewBase):
    def get(self, request):
        company = self.get_company()
        if company is None:
            return self.error_response('Company context is required.')
        try:
            start_date, end_date = self.get_date_range()
        except ValueError as exc:
            return self.error_response(str(exc))
        data = get_payment_metrics(company, start_date, end_date)
        return JsonResponse(data)


class AnalyticsInsightsDataView(AnalyticsDataViewBase):
    def get(self, request):
        company = self.get_company()
        if company is None:
            return self.error_response('Company context is required.')
        try:
            start_date, end_date = self.get_date_range()
        except ValueError as exc:
            return self.error_response(str(exc))
        data = get_insights(company, start_date, end_date)
        return JsonResponse(data)


def _export_rows_for_tab(tab, company, start_date, end_date, query_params):
    if tab == 'overview':
        metrics = get_overview_metrics(company, start_date, end_date)
        return [
            {'metric': 'Total Revenue', 'value': metrics['total_revenue']},
            {'metric': 'Sales Count', 'value': metrics['sales_count']},
            {'metric': 'Purchase Count', 'value': metrics['purchase_count']},
            {'metric': 'Total Customers', 'value': metrics['total_customers']},
            {'metric': 'Total Vendors', 'value': metrics['total_vendors']},
            {'metric': 'Inventory Value', 'value': metrics['inventory_value']},
            {'metric': 'Outstanding Receivables', 'value': metrics['outstanding_receivables']},
            {'metric': 'Outstanding Payables', 'value': metrics['outstanding_payables']},
            {'metric': 'Average Order Value', 'value': metrics['average_order_value']},
        ]
    if tab == 'revenue':
        metrics = get_revenue_metrics(company, start_date, end_date)
        rows = []
        rows.append({'section': 'Daily Revenue Trend'})
        rows.extend([
            {'period': row['period'], 'value': row['value']} for row in metrics['daily_trend']
        ])
        rows.append({'section': 'Revenue by Category'})
        rows.extend([
            {'category': row['category'], 'value': row['value']} for row in metrics['revenue_by_category']
        ])
        rows.append({'section': 'Revenue by Customer'})
        rows.extend([
            {'customer': row['name'], 'value': row['value']} for row in metrics['revenue_by_customer']
        ])
        return rows
    if tab == 'purchases':
        metrics = get_purchase_metrics(company, start_date, end_date)
        rows = []
        rows.append({'section': 'Daily Purchase Trend'})
        rows.extend([{'period': row['period'], 'value': row['value']} for row in metrics['daily_trend']])
        rows.append({'section': 'Monthly Purchase Trend'})
        rows.extend([{'period': row['period'], 'value': row['value']} for row in metrics['monthly_trend']])
        rows.append({'section': 'Vendor Purchase Trend'})
        rows.extend([{'vendor': row['vendor'], 'value': row['value']} for row in metrics['vendor_trend']])
        return rows
    if tab == 'products':
        days = int(query_params.get('dead_stock_days', 90))
        metrics = get_product_metrics(company, start_date, end_date, dead_stock_days=days)
        rows = []
        rows.append({'section': 'Top Selling Products'})
        rows.extend([{'product': row['name'], 'quantity': row['quantity']} for row in metrics['top_selling_products']])
        rows.append({'section': 'Top Revenue Products'})
        rows.extend([{'product': row['name'], 'revenue': row['revenue']} for row in metrics['top_revenue_products']])
        rows.append({'section': 'Worst Performing Products'})
        rows.extend([{'product': row['name'], 'revenue': row['revenue']} for row in metrics['worst_performing_products']])
        rows.append({'section': 'Dead Stock'})
        rows.extend([{'product': row['name'], 'quantity': row['quantity'], 'last_sold': row['last_sold'] or 'Never'} for row in metrics['dead_stock']])
        rows.append({'section': 'Inventory Value by Category'})
        rows.extend([{'category': row['category'], 'value': row['value']} for row in metrics['inventory_value_by_category']])
        return rows
    if tab == 'customers':
        metrics = get_customer_metrics(company, start_date, end_date)
        rows = []
        rows.append({'section': 'Customer Lifetime Value'})
        rows.extend([{'customer': row['name'], 'revenue': row['revenue'], 'orders': row['orders']} for row in metrics['customer_lifetime_value']])
        rows.append({'section': 'Top Customers by Revenue'})
        rows.extend([{'customer': row['name'], 'value': row['value']} for row in metrics['top_customers_by_revenue']])
        rows.append({'section': 'Top Customers by Order Count'})
        rows.extend([{'customer': row['name'], 'orders': row['orders']} for row in metrics['top_customers_by_order_count']])
        rows.append({'section': 'Summary'})
        rows.append({'metric': 'Average Order Value', 'value': metrics['average_order_value']})
        rows.append({'metric': 'New Customers', 'value': metrics['new_customers']})
        rows.append({'metric': 'Returning Customers', 'value': metrics['returning_customers']})
        return rows
    if tab == 'vendors':
        metrics = get_vendor_metrics(company, start_date, end_date)
        return [
            {
                'vendor': row['name'],
                'spend': row['spend'],
                'frequency': row['frequency'],
                'contribution': row['contribution'],
            }
            for row in metrics['vendor_spend_ranking']
        ]
    if tab == 'payments':
        metrics = get_payment_metrics(company, start_date, end_date)
        return [
            {'metric': 'Outstanding Receivables', 'value': metrics['outstanding_receivables']},
            {'metric': 'Partial Sales', 'value': metrics['partial_sales']},
            {'metric': 'Unpaid Sales', 'value': metrics['unpaid_sales']},
            {'metric': 'Outstanding Payables', 'value': metrics['outstanding_payables']},
            {'metric': 'Partial Purchases', 'value': metrics['partial_purchases']},
            {'metric': 'Unpaid Purchases', 'value': metrics['unpaid_purchases']},
        ]
    if tab == 'insights':
        metrics = get_insights(company, start_date, end_date)
        rows = [{'metric': 'Business Health Score', 'value': metrics['business_health_score']}] + [
            {'title': insight['title'], 'message': insight['message']} for insight in metrics['insights']
        ]
        return rows
    return []


class AnalyticsExportCsvView(AnalyticsDataViewBase):
    def get(self, request, tab):
        company = self.get_company()
        if company is None:
            return self.error_response('Company context is required.')
        if tab not in TAB_NAMES:
            return self.error_response('Invalid export tab.')
        try:
            start_date, end_date = self.get_date_range()
        except ValueError as exc:
            return self.error_response(str(exc))

        rows = _export_rows_for_tab(tab, company, start_date, end_date, request.GET)
        if not rows:
            return self.error_response('No export data available for this tab.')

        output = StringIO()
        fieldnames = sorted({key for row in rows for key in row.keys()})
        writer = DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        filename = f'analytics-{tab}-{start_date}-{end_date}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class AnalyticsExportExcelView(AnalyticsDataViewBase):
    def get(self, request, tab):
        company = self.get_company()
        if company is None:
            return self.error_response('Company context is required.')
        if tab not in TAB_NAMES:
            return self.error_response('Invalid export tab.')
        try:
            start_date, end_date = self.get_date_range()
        except ValueError as exc:
            return self.error_response(str(exc))

        rows = _export_rows_for_tab(tab, company, start_date, end_date, request.GET)
        if not rows:
            return self.error_response('No export data available for this tab.')

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = tab.capitalize()
        headers = sorted({key for row in rows for key in row.keys()})
        sheet.append(headers)
        for row in rows:
            sheet.append([row.get(key, '') for key in headers])

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f'analytics-{tab}-{start_date}-{end_date}.xlsx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        workbook.save(response)
        return response
