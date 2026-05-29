from django import forms

from accounts.tenant import company_for_request, scoped_queryset
from accounts.models import Vendor
from .models import Purchase


class BootstrapMixin(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class PurchaseForm(BootstrapMixin, forms.ModelForm):
    vendor_name = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Select or type vendor',
                'list': 'vendor-options',
            }
        ),
    )

    class Meta:
        model = Purchase
        fields = [
            'description',
            'delivery_date',
        ]
        widgets = {
            'delivery_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                }
            ),
            'description': forms.Textarea(
                attrs={
                    'rows': 2,
                    'cols': 40,
                    'class': 'form-control',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk and self.instance.vendor:
            self.fields['vendor_name'].initial = self.instance.vendor.name

    def clean_vendor_name(self):
        vendor_name = ' '.join(self.cleaned_data.get('vendor_name', '').split())
        if not vendor_name:
            raise forms.ValidationError('Vendor is required.')
        return vendor_name

    def save(self, commit=True):
        purchase = super().save(commit=False)
        vendor_name = self.cleaned_data.get('vendor_name')
        user = getattr(self.request, 'user', None)

        vendor_obj = None
        if user and user.is_authenticated:
            vendor_obj = scoped_queryset(Vendor, user).filter(
                name__iexact=vendor_name,
            ).first()
            company = company_for_request(self.request) if self.request else None
        else:
            company = None

        if vendor_obj is None:
            vendor_obj = Vendor.objects.create(
                name=vendor_name,
                company=company or purchase.company,
            )

        purchase.vendor = vendor_obj

        if commit:
            purchase.save()

        return purchase
