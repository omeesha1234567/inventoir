from django.contrib import admin
from .models import Profile, Vendor, Customer


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'telephone', 'email', 'role', 'status')
    list_filter = ('role', 'company')


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'phone_number', 'is_archived')
    search_fields = ('name', 'phone_number', 'address')
    list_filter = ('company', 'is_archived')

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'company', 'phone', 'is_archived')
    list_filter = ('company', 'is_archived')

    def has_delete_permission(self, request, obj=None):
        return False
