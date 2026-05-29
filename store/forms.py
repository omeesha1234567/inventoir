from django import forms
from accounts.models import Vendor
from .models import Item, Category, Delivery


class ItemForm(forms.ModelForm):
    category_name = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'list': 'category-options'
            }
        )
    )

    vendor_name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'list': 'vendor-options'
            }
        )
    )

    class Meta:
        model = Item
        fields = [
            'name',
            'description',
            'quantity',
            'price',
            'gst_percentage',
            'purchase_date'
        ]
        labels = {
            'price': 'Cost Price',
            'gst_percentage': 'GST (%)',
            'purchase_date': 'Purchase Date',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 2
                }
            ),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'step': '0.01',
                    'id': 'id_price'
                }
            ),
            'gst_percentage': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'step': '0.01',
                    'id': 'id_gst_percentage',
                    'placeholder': 'Enter GST'
                }
            ),
            'purchase_date': forms.DateTimeInput(
                attrs={
                    'class': 'form-control',
                    'type': 'datetime-local'
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields['category_name'].initial = self.instance.category.name
            if self.instance.vendor:
                self.fields['vendor_name'].initial = self.instance.vendor.name

    def clean_category_name(self):
        category_name = " ".join(self.cleaned_data.get('category_name', '').split())
        if not category_name:
            raise forms.ValidationError('Category is required.')
        return category_name

    def clean_vendor_name(self):
        vendor_name = " ".join(self.cleaned_data.get('vendor_name', '').split())
        return vendor_name

    def __init__(self, *args, company=None, user=None, **kwargs):
        self.company = company
        self.user = user
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        item = super().save(commit=False)

        category_name = self.cleaned_data.get('category_name')
        vendor_name = self.cleaned_data.get('vendor_name')
        company = self.company or item.company

        category_qs = Category.objects.filter(name__iexact=category_name)
        if company:
            category_qs = category_qs.filter(company=company)
        category_obj = category_qs.first()
        if category_obj is None:
            category_obj = Category.objects.create(
                name=category_name,
                company=company,
            )

        item.category = category_obj

        if vendor_name:
            vendor_qs = Vendor.objects.filter(name__iexact=vendor_name)
            if company:
                vendor_qs = vendor_qs.filter(company=company)
            vendor_obj = vendor_qs.first()
            if vendor_obj is None:
                vendor_obj = Vendor.objects.create(name=vendor_name, company=company)
            item.vendor = vendor_obj
        else:
            item.vendor = None

        if company and not item.company_id:
            item.company = company

        if commit:
            item.save()

        return item


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category name',
                'aria-label': 'Category Name'
            }),
        }
        labels = {
            'name': 'Category Name',
        }


class DeliveryForm(forms.ModelForm):
    class Meta:
        model = Delivery
        fields = [
            'item',
            'customer_name',
            'phone_number',
            'location',
            'date',
            'is_delivered'
        ]
        widgets = {
            'item': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'Select item',
            }),
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter customer name',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number',
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter delivery location',
            }),
            'date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'placeholder': 'Select delivery date and time',
                'type': 'datetime-local'
            }),
            'is_delivered': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'label': 'Mark as delivered',
            }),
        }