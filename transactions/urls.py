from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from .views import (
    PurchaseListView,
    PurchaseDetailView,
    PurchaseCreateView,
    PurchaseUpdateView,
    PurchaseDeleteView,
    SaleListView,
    SaleDetailView,
    SaleCreateView,
    SaleDeleteView,
    export_sales_to_excel,
    export_purchases_to_excel,
    get_customer_details,
    get_vendor_details,
    get_item_details,
    add_purchase_payment,
    add_sale_payment,
    SalePaymentUpdateView,
    SalePaymentArchiveView,
    archive_purchase_payment,
)

urlpatterns = [
    path('purchases/', PurchaseListView.as_view(), name='purchaseslist'),
    path('purchase/<slug:slug>/', PurchaseDetailView.as_view(), name='purchase-detail'),
    path('new-purchase/', PurchaseCreateView, name='purchase-create'),
    path('purchase/<int:pk>/update/', PurchaseUpdateView.as_view(), name='purchase-update'),
    path('purchase/<int:pk>/delete/', PurchaseDeleteView.as_view(), name='purchase-delete'),
    path('purchase/<int:pk>/add-payment/', add_purchase_payment, name='purchase-add-payment'),
    path(
        'purchase-payment/<int:pk>/archive/',
        archive_purchase_payment,
        name='purchase-payment-archive',
    ),

    path('sales/', SaleListView.as_view(), name='saleslist'),
    path('sale/<int:pk>/', SaleDetailView.as_view(), name='sale-detail'),
    path('new-sale/', SaleCreateView, name='sale-create'),
    path('sale/<int:pk>/archive/', SaleDeleteView.as_view(), name='sale-delete'),
    path('sale/<int:pk>/add-payment/', add_sale_payment, name='sale-add-payment'),
    path(
        'sale-payment/<int:pk>/update/',
        SalePaymentUpdateView.as_view(),
        name='sale-payment-update',
    ),
    path(
        'sale-payment/<int:pk>/archive/',
        SalePaymentArchiveView.as_view(),
        name='sale-payment-archive',
    ),
    path(
    "get-item-details/",
    get_item_details,
    name="get-item-details",
),
    path('get-customer-details/', get_customer_details, name='get-customer-details'),
    path('get-vendor-details/', get_vendor_details, name='get-vendor-details'),

    path('sales/export/', export_sales_to_excel, name='sales-export'),
    path('purchases/export/', export_purchases_to_excel, name='purchases-export'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)