from django.db import models
from django.contrib.auth.models import User

from django_extensions.db.fields import AutoSlugField
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill
from phonenumber_field.modelfields import PhoneNumberField

from companies.base import (
    ActiveCompanyManager,
    ArchivableModel,
    AuditedModel,
    CompanyOwnedModel,
)


STATUS_INACTIVE = 'INA'
STATUS_ACTIVE = 'A'
STATUS_ON_LEAVE = 'OL'

STATUS_CHOICES = [
    (STATUS_INACTIVE, 'Inactive'),
    (STATUS_ACTIVE, 'Active'),
    (STATUS_ON_LEAVE, 'On leave'),
]

ROLE_COMPANY_ADMIN = 'CA'
ROLE_COORDINATOR = 'CO'
ROLE_EMPLOYEE = 'EM'

ROLE_CHOICES = [
    (ROLE_COMPANY_ADMIN, 'Company Admin'),
    (ROLE_COORDINATOR, 'Company Coordinator'),
    (ROLE_EMPLOYEE, 'Employee'),
]

LEGACY_ROLE_CHOICES = [
    ('OP', 'Operative'),
    ('EX', 'Executive'),
    ('AD', 'Admin'),
]


class Profile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, verbose_name='User'
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='profiles',
    )
    slug = AutoSlugField(
        unique=True,
        verbose_name='Account ID',
        populate_from='email',
    )
    profile_picture = ProcessedImageField(
        default='profile_pics/default.jpg',
        upload_to='profile_pics',
        format='JPEG',
        processors=[ResizeToFill(150, 150)],
        options={'quality': 100},
    )
    telephone = PhoneNumberField(
        null=True, blank=True, verbose_name='Telephone'
    )
    email = models.EmailField(
        max_length=150, blank=True, null=True, verbose_name='Email'
    )
    first_name = models.CharField(
        max_length=30, blank=True, verbose_name='First Name'
    )
    last_name = models.CharField(
        max_length=30, blank=True, verbose_name='Last Name'
    )
    status = models.CharField(
        choices=STATUS_CHOICES,
        max_length=12,
        default=STATUS_INACTIVE,
        verbose_name='Status',
    )
    role = models.CharField(
        choices=ROLE_CHOICES + LEGACY_ROLE_CHOICES,
        max_length=12,
        blank=True,
        null=True,
        verbose_name='Role',
    )

    @property
    def image_url(self):
        from django.templatetags.static import static

        try:
            if self.profile_picture and self.profile_picture.name:
                if self.profile_picture.storage.exists(self.profile_picture.name):
                    return self.profile_picture.url
        except (AttributeError, ValueError, OSError):
            pass
        return static('images/default-avatar.png')

    def is_company_admin(self):
        return self.role in (ROLE_COMPANY_ADMIN, 'AD')

    def is_coordinator(self):
        return self.role in (ROLE_COORDINATOR, 'OP', 'EX')

    def __str__(self):
        return f'{self.user.username} Profile'

    class Meta:
        ordering = ['slug']
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'


class Vendor(CompanyOwnedModel, ArchivableModel, AuditedModel):
    name = models.CharField(max_length=50, verbose_name='Name')
    slug = AutoSlugField(
        populate_from='name',
        verbose_name='Slug',
    )
    phone_number = models.BigIntegerField(
        blank=True, null=True, verbose_name='Phone Number'
    )
    email = models.EmailField(
        max_length=150, blank=True, null=True, verbose_name='Email'
    )
    gst_number = models.CharField(
        max_length=30, blank=True, null=True, verbose_name='GST Number'
    )
    address = models.CharField(
        max_length=100, blank=True, null=True, verbose_name='Address'
    )

    objects = models.Manager()
    active = ActiveCompanyManager()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Vendor'
        verbose_name_plural = 'Vendors'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'slug'],
                name='unique_vendor_slug_per_company',
            ),
        ]


class Customer(CompanyOwnedModel, ArchivableModel, AuditedModel):
    first_name = models.CharField(max_length=256)
    last_name = models.CharField(max_length=256, blank=True, null=True)
    address = models.TextField(max_length=256, blank=True, null=True)
    email = models.EmailField(max_length=256, blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    gst_number = models.CharField(max_length=30, blank=True, null=True)
    loyalty_points = models.IntegerField(default=0)

    objects = models.Manager()
    active = ActiveCompanyManager()

    class Meta:
        db_table = 'Customers'

    def __str__(self) -> str:
        return self.get_full_name()

    def get_full_name(self):
        first_name = self.first_name or ''
        last_name = self.last_name or ''
        full_name = f'{first_name} {last_name}'.strip()
        if full_name:
            return full_name
        return 'Unknown Customer'

    def to_select2(self):
        return {
            'label': self.get_full_name(),
            'value': self.id,
        }
