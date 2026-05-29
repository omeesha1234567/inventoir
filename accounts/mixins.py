from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from accounts.models import ROLE_COMPANY_ADMIN, ROLE_COORDINATOR
from accounts.utils import get_user_company, company_is_active


class CompanyAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        company = get_user_company(request.user)
        if company is None or not company_is_active(company):
            raise PermissionDenied('Company access is not available.')
        if not request.user.is_active:
            raise PermissionDenied('Account is inactive.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        from accounts.utils import filter_by_company
        return filter_by_company(qs, self.request.user)


class CompanyAdminRequiredMixin(CompanyAccessMixin, UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        profile = getattr(user, 'profile', None)
        return (
            profile is not None
            and profile.role == ROLE_COMPANY_ADMIN
            and profile.company_id is not None
        )


class CoordinatorOrAdminMixin(CompanyAccessMixin, UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        profile = getattr(user, 'profile', None)
        return profile is not None and profile.role in (
            ROLE_COMPANY_ADMIN,
            ROLE_COORDINATOR,
        )


class RoleDashboardRedirectMixin:
    def get_dashboard_url_name(self):
        user = self.request.user
        if user.is_superuser:
            return 'dashboard'
        profile = getattr(user, 'profile', None)
        if profile and profile.role == ROLE_COORDINATOR:
            return 'coordinator-dashboard'
        return 'admin-dashboard'


def redirect_to_role_dashboard(user):
    if user.is_superuser:
        return redirect('dashboard')
    profile = getattr(user, 'profile', None)
    if profile and profile.role == ROLE_COORDINATOR:
        return redirect('coordinator-dashboard')
    return redirect('admin-dashboard')
