from django.conf import settings
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True


class AuditedModel(TimestampedModel):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_updated',
    )

    class Meta:
        abstract = True


class CompanyOwnedModel(models.Model):
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_set',
    )

    class Meta:
        abstract = True


class ArchivableModel(models.Model):
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_archived',
    )

    class Meta:
        abstract = True


class ActiveCompanyQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_archived=False)

    def archived(self):
        return self.filter(is_archived=True)

    def for_company(self, company):
        if company is None:
            return self
        return self.filter(company=company)


class ActiveCompanyManager(models.Manager):
    def get_queryset(self):
        return ActiveCompanyQuerySet(self.model, using=self._db).filter(
            is_archived=False
        )

    def archived(self):
        return ActiveCompanyQuerySet(self.model, using=self._db).filter(
            is_archived=True
        )

    def all_records(self):
        return ActiveCompanyQuerySet(self.model, using=self._db)

    def for_company(self, company):
        return self.all_records().for_company(company)


def archive_instance(instance, user):
    instance.is_archived = True
    instance.archived_at = timezone.now()
    instance.archived_by = user
    instance.save(update_fields=['is_archived', 'archived_at', 'archived_by'])


def restore_instance(instance):
    instance.is_archived = False
    instance.archived_at = None
    instance.archived_by = None
    instance.save(update_fields=['is_archived', 'archived_at', 'archived_by'])
