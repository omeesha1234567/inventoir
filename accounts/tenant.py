"""Server-side multi-tenant queryset helpers."""
from django.http import JsonResponse

from accounts.utils import (
    company_is_active,
    filter_by_company,
    get_default_company,
    get_user_company,
)


def company_for_request(request):
    """
    Resolve the active company for the current request.
    Company admins/coordinators always use their profile company.
  """
    if not request.user.is_authenticated:
        return None
    if request.user.is_superuser:
        return get_default_company()
    company = get_user_company(request.user)
    if company is None or not company_is_active(company):
        return None
    return company


def scoped_queryset(model, user, *, include_archived=False):
    """Company-filtered queryset; excludes archived unless requested."""
    return filter_by_company(
        model.objects.all(),
        user,
        include_archived=include_archived,
    )


def tenant_guard_json(request):
    """
    Return None if the request may proceed, else a JsonResponse error.
    Non-superusers must belong to an active company.
    """
    if not request.user.is_authenticated:
        return JsonResponse(
            {'status': 'error', 'message': 'Authentication required'},
            status=401,
        )
    if request.user.is_superuser:
        return None
    company = get_user_company(request.user)
    if company is None or not company_is_active(company):
        return JsonResponse(
            {'status': 'error', 'message': 'Company access denied'},
            status=403,
        )
    return None
