from django.contrib.auth.models import User
from django.db import transaction

from companies.models import Company
from accounts.models import ROLE_COMPANY_ADMIN, STATUS_ACTIVE


@transaction.atomic
def register_company_with_admin(
    *,
    company_name,
    gst_number,
    company_email,
    phone,
    address,
    owner_name,
    username,
    password,
    user_email=None,
):
    company = Company.objects.create(
        name=company_name,
        gst_number=gst_number,
        email=company_email,
        phone=phone,
        address=address,
        owner_name=owner_name,
    )

    user = User.objects.create_user(
        username=username,
        email=user_email or company_email,
        password=password,
        first_name=owner_name,
    )

    profile = user.profile
    profile.company = company
    profile.role = ROLE_COMPANY_ADMIN
    profile.status = STATUS_ACTIVE
    profile.email = user_email or company_email
    profile.first_name = owner_name
    profile.save()

    return company, user
