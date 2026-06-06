from django.urls import path

from .views import (
    AnalyticsDashboardView,
    AnalyticsTabTemplateView,
    AnalyticsOverviewDataView,
    AnalyticsRevenueDataView,
    AnalyticsPurchasesDataView,
    AnalyticsProductsDataView,
    AnalyticsCustomersDataView,
    AnalyticsVendorsDataView,
    AnalyticsPaymentsDataView,
    AnalyticsInsightsDataView,
    AnalyticsExportCsvView,
    AnalyticsExportExcelView,
)

urlpatterns = [
    path('', AnalyticsDashboardView.as_view(), name='analytics-dashboard'),
    path('tab/<str:tab>/', AnalyticsTabTemplateView.as_view(), name='analytics-tab-template'),
    path('data/overview/', AnalyticsOverviewDataView.as_view(), name='analytics-overview-data'),
    path('data/revenue/', AnalyticsRevenueDataView.as_view(), name='analytics-revenue-data'),
    path('data/purchases/', AnalyticsPurchasesDataView.as_view(), name='analytics-purchases-data'),
    path('data/products/', AnalyticsProductsDataView.as_view(), name='analytics-products-data'),
    path('data/customers/', AnalyticsCustomersDataView.as_view(), name='analytics-customers-data'),
    path('data/vendors/', AnalyticsVendorsDataView.as_view(), name='analytics-vendors-data'),
    path('data/payments/', AnalyticsPaymentsDataView.as_view(), name='analytics-payments-data'),
    path('data/insights/', AnalyticsInsightsDataView.as_view(), name='analytics-insights-data'),
    path('export/csv/<str:tab>/', AnalyticsExportCsvView.as_view(), name='analytics-export-csv'),
    path('export/excel/<str:tab>/', AnalyticsExportExcelView.as_view(), name='analytics-export-excel'),
]
