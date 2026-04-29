from django import forms
from accounts.models import Vendor
from .models import Item, Category, Delivery


class ItemForm(forms.ModelForm):
    category_name = forms.CharField(
    required=True,
    widget=forms.TextInput(
        attrs={
            'class': 'form-control',
            'placeholder': 'Select or type category',
            'list': 'category-options'
        }
    )
)

    vendor_name = forms.CharField(
    required=False,
    widget=forms.TextInput(
        attrs={
            'class': 'form-control',
            'placeholder': 'Select or type vendor',
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
            'expiring_date'
        ]
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
                    'step': '0.01'
                }
            ),
            'expiring_date': forms.DateTimeInput(
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
        category_name = " ".join(
            self.cleaned_data.get('category_name', '').split()
        )
        if not category_name:
            raise forms.ValidationError('Category is required.')
        return category_name

    def clean_vendor_name(self):
        vendor_name = " ".join(
            self.cleaned_data.get('vendor_name', '').split()
        )
        return vendor_name

    def save(self, commit=True):
        item = super().save(commit=False)

        category_name = self.cleaned_data.get('category_name')
        vendor_name = self.cleaned_data.get('vendor_name')

        category_obj = Category.objects.filter(
            name__iexact=category_name
        ).first()
        if category_obj is None:
            category_obj = Category.objects.create(name=category_name)

        item.category = category_obj

        if vendor_name:
            vendor_obj = Vendor.objects.filter(
                name__iexact=vendor_name
            ).first()
            if vendor_obj is None:
                vendor_obj = Vendor.objects.create(name=vendor_name)
            item.vendor = vendor_obj
        else:
            item.vendor = None

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