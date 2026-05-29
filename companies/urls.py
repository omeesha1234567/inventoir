from django.urls import path

from companies import views
from accounts.models import Customer, Vendor
from store.models import Category, Item
from transactions.models import Sale, Purchase
from invoice.models import Invoice

urlpatterns = [
    path('owner/login/', views.OwnerLoginView.as_view(), name='owner-login'),
    path(
        'coordinator/login/',
        views.CoordinatorLoginView.as_view(),
        name='coordinator-login',
    ),
    path(
        'register/company/',
        views.CompanyRegistrationView.as_view(),
        name='company-register',
    ),
    path(
        'owner/settings/',
        views.CompanySettingsView.as_view(),
        name='company-settings',
    ),
    path('owner/users/', views.CoordinatorListView.as_view(), name='coordinator-list'),
    path(
        'owner/users/create/',
        views.CoordinatorCreateView.as_view(),
        name='coordinator-create',
    ),
    path(
        'owner/users/<int:pk>/deactivate/',
        views.CoordinatorDeactivateView.as_view(),
        name='coordinator-deactivate',
    ),
    path(
        'owner/archived/<str:section>/',
        views.ArchivedRecordsView.as_view(),
        name='archived-records',
    ),
    path(
        'owner/archived/<str:section>/<int:pk>/restore/',
        views.RestoreArchivedView.as_view(),
        name='archived-restore',
    ),
    path(
        'customers/<int:pk>/archive/',
        views.archive_view_for_model(Customer, 'customer_list').as_view(),
        name='customer-archive',
    ),
    path(
        'vendors/<int:pk>/archive/',
        views.archive_view_for_model(Vendor, 'vendor-list').as_view(),
        name='vendor-archive',
    ),
    path(
        'product/<slug:slug>/archive/',
        views.ProductArchiveView.as_view(),
        name='product-archive',
    ),
    path(
        'categories/<int:pk>/archive/',
        views.archive_view_for_model(Category, 'category-list').as_view(),
        name='category-archive',
    ),
    path(
        'transactions/sale/<int:pk>/archive/',
        views.archive_view_for_model(Sale, 'saleslist').as_view(),
        name='sale-archive',
    ),
    path(
        'transactions/purchase/<int:pk>/archive/',
        views.archive_view_for_model(Purchase, 'purchaseslist').as_view(),
        name='purchase-archive',
    ),
    path(
        'invoice/<int:pk>/archive/',
        views.archive_view_for_model(Invoice, 'invoicelist').as_view(),
        name='invoice-archive',
    ),
]
