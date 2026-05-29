from companies.models import Company


def get_user_company(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return None
    profile = getattr(user, 'profile', None)
    if profile is None:
        return None
    return profile.company


def company_is_active(company):
    return company is not None and company.is_active


def filter_by_company(queryset, user, *, include_archived=False):
    company = get_user_company(user)
    if user.is_superuser:
        if include_archived:
            return queryset
        if hasattr(queryset.model, 'is_archived'):
            return queryset.filter(is_archived=False)
        return queryset

    if company is None or not company_is_active(company):
        return queryset.none()

    qs = queryset.filter(company=company)
    if not include_archived and hasattr(queryset.model, 'is_archived'):
        qs = qs.filter(is_archived=False)
    return qs


def assign_company(instance, user):
    company = get_user_company(user)
    if company is not None and hasattr(instance, 'company_id'):
        instance.company = company
    return instance


def set_audit_user(instance, user, *, is_create=False):
    if not user.is_authenticated:
        return instance
    if is_create and hasattr(instance, 'created_by_id'):
        instance.created_by = user
    if hasattr(instance, 'updated_by_id'):
        instance.updated_by = user
    return instance


def get_default_company():
    return Company.objects.filter(company_code='INV-DEFAULT').first()
