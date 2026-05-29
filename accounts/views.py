# Django core imports
from django.db.models import Q
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.views.decorators.http import require_POST

# Authentication and permissions
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from accounts.mixins import (
    CompanyAccessMixin,
    CompanyAdminRequiredMixin,
    CoordinatorOrAdminMixin,
)
from accounts.utils import assign_company, filter_by_company, set_audit_user
from accounts.tenant import scoped_queryset
from companies.archive_views import ArchivableDeleteView
# Class-based views
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DeleteView
)

# Third-party packages
from django_tables2 import SingleTableView
from django_tables2.export.views import ExportMixin

# Local app imports
from .models import Profile, Customer, Vendor
from .forms import (
    CreateUserForm, UserUpdateForm,
    ProfileUpdateForm, CustomerForm,
    VendorForm
)
from .tables import ProfileTable


def register(request):
    return redirect('company-register')


@login_required
def profile(request):
    """
    Render the user profile page.
    Requires user to be logged in.
    """
    return render(request, 'accounts/profile.html')


@login_required
def profile_update(request):
    """
    Handle profile update.
    If the request is POST, process the form data
    to update user information and profile.
    Redirect to the profile page on success.
    For GET requests, render the update forms.
    """
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=request.user.profile
        )
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            return redirect('user-profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    return render(
        request,
        'accounts/profile_update.html',
        {'u_form': u_form, 'p_form': p_form}
    )


class ProfileListView(LoginRequiredMixin, ExportMixin, SingleTableView):
    """
    Display a list of profiles in a table format.
    Requires user to be logged in
    and supports exporting the table data.
    Pagination is applied with 10 profiles per page.
    """
    model = Profile
    template_name = 'accounts/stafflist.html'
    context_object_name = 'profiles'
    table_class = ProfileTable
    paginate_by = 10
    table_pagination = False


class ProfileCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new profile.
    Requires user to be logged in and have superuser status.
    Redirects to the profile list upon successful creation.
    """
    model = Profile
    template_name = 'accounts/staffcreate.html'
    fields = ['user', 'role', 'status']

    def get_success_url(self):
        """
        Return the URL to redirect to after successfully creating a profile.
        """
        return reverse('profile_list')

    def test_func(self):
        """
        Check if the user is a superuser.
        """
        return self.request.user.is_superuser


class ProfileUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Update an existing profile.
    Requires user to be logged in and have superuser status.
    Redirects to the profile list upon successful update.
    """
    model = Profile
    template_name = 'accounts/staffupdate.html'
    fields = ['user', 'role', 'status']

    def get_success_url(self):
        """
        Return the URL to redirect to after successfully updating a profile.
        """
        return reverse('profile_list')

    def test_func(self):
        """
        Check if the user is a superuser.
        """
        return self.request.user.is_superuser


class ProfileDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Delete an existing profile.
    Requires user to be logged in and have superuser status.
    Redirects to the profile list upon successful deletion.
    """
    model = Profile
    template_name = 'accounts/staffdelete.html'

    def get_success_url(self):
        """
        Return the URL to redirect to after successfully deleting a profile.
        """
        return reverse('profile_list')

    def test_func(self):
        """
        Check if the user is a superuser.
        """
        return self.request.user.is_superuser


class CustomerListView(CompanyAccessMixin, ListView):
    """
    View for listing all customers.

    Requires the user to be logged in. Displays a list of all Customer objects.
    """
    model = Customer
    template_name = 'accounts/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 10

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .order_by('first_name', 'last_name', 'id')
        )


class CustomerCreateView(CoordinatorOrAdminMixin, CreateView):
    """
    View for creating a new customer.

    Requires the user to be logged in.
    Provides a form for creating a new Customer object.
    On successful form submission, redirects to the customer list.
    """
    model = Customer
    template_name = 'accounts/customer_form.html'
    form_class = CustomerForm
    success_url = reverse_lazy('customer_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        assign_company(self.object, self.request.user)
        set_audit_user(self.object, self.request.user, is_create=True)
        self.object.save()
        return redirect(self.success_url)


class CustomerUpdateView(CoordinatorOrAdminMixin, UpdateView):
    """
    View for updating an existing customer.

    Requires the user to be logged in.
    Provides a form for editing an existing Customer object.
    On successful form submission, redirects to the customer list.
    """
    model = Customer
    template_name = 'accounts/customer_form.html'
    form_class = CustomerForm
    success_url = reverse_lazy('customer_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        set_audit_user(self.object, self.request.user)
        self.object.save()
        return redirect(self.success_url)


class CustomerDeleteView(CompanyAdminRequiredMixin, ArchivableDeleteView):
    model = Customer
    template_name = 'accounts/customer_confirm_delete.html'
    success_url = reverse_lazy('customer_list')

    @property
    def archive_success_message(self):
        return 'Customer archived successfully.'


def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


@require_POST
@login_required
def get_customers(request):
    if is_ajax(request) and request.method == 'POST':
        term = request.POST.get('term', '')
        customers = scoped_queryset(Customer, request.user).filter(
            Q(first_name__icontains=term) | Q(last_name__icontains=term),
        ).values('id', 'first_name', 'last_name')
        customer_list = [
            {
                'id': c['id'],
                'name': f"{c['first_name']} {c['last_name'] or ''}".strip(),
            }
            for c in customers
        ]
        return JsonResponse(customer_list, safe=False)
    return JsonResponse({'error': 'Invalid request method'}, status=400)


class VendorListView(CompanyAccessMixin, ListView):
    model = Vendor
    template_name = 'accounts/vendor_list.html'
    context_object_name = 'vendors'
    paginate_by = 10

    def get_queryset(self):
        return super().get_queryset().order_by('name', 'id')


class VendorCreateView(CoordinatorOrAdminMixin, CreateView):
    model = Vendor
    form_class = VendorForm
    template_name = 'accounts/vendor_form.html'
    success_url = reverse_lazy('vendor-list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        assign_company(self.object, self.request.user)
        set_audit_user(self.object, self.request.user, is_create=True)
        self.object.save()
        return redirect(self.success_url)


class VendorUpdateView(CoordinatorOrAdminMixin, UpdateView):
    model = Vendor
    form_class = VendorForm
    template_name = 'accounts/vendor_form.html'
    success_url = reverse_lazy('vendor-list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        set_audit_user(self.object, self.request.user)
        self.object.save()
        return redirect(self.success_url)


class VendorDeleteView(CompanyAdminRequiredMixin, ArchivableDeleteView):
    model = Vendor
    template_name = 'accounts/vendor_confirm_delete.html'
    success_url = reverse_lazy('vendor-list')

    @property
    def archive_success_message(self):
        return 'Vendor archived successfully.'
