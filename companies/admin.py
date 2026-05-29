from django.contrib import admin

from companies.models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'company_code',
        'gst_number',
        'email',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'company_code', 'gst_number', 'email')
    readonly_fields = ('company_code', 'created_at')

    def has_delete_permission(self, request, obj=None):
        return False
