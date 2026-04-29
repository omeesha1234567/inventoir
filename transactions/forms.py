from django import forms
from store.models import Item, Category
from accounts.models import Vendor
from .models import Purchase


class BootstrapMixin(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class PurchaseForm(BootstrapMixin, forms.ModelForm):
    item_name = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Select or type item',
                'list': 'item-options'
            }
        )
    )

    category_name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Required only for new item',
                'list': 'category-options'
            }
        )
    )

    vendor_name = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Select or type vendor',
                'list': 'vendor-options'
            }
        )
    )

    item_description = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 1,
                'placeholder': 'Required only for new item'
            }
        )
    )

    class Meta:
        model = Purchase
        fields = [
            'price',
            'description',
            'quantity',
            'delivery_date',
            'delivery_status'
        ]
        widgets = {
            'delivery_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'datetime-local'
                }
            ),
            'description': forms.Textarea(
                attrs={
                    'rows': 1,
                    'cols': 40,
                    'class': 'form-control'
                }
            ),
            'quantity': forms.NumberInput(
                attrs={'class': 'form-control'}
            ),
            'delivery_status': forms.Select(
                attrs={'class': 'form-control'}
            ),
            'price': forms.NumberInput(
                attrs={'class': 'form-control'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            if self.instance.item:
                self.fields['item_name'].initial = self.instance.item.name
                self.fields['item_description'].initial = self.instance.item.description
                self.fields['category_name'].initial = self.instance.item.category.name
            if self.instance.vendor:
                self.fields['vendor_name'].initial = self.instance.vendor.name

    def clean_item_name(self):
        item_name = " ".join(self.cleaned_data.get('item_name', '').split())
        if not item_name:
            raise forms.ValidationError('Item is required.')
        return item_name

    def clean_vendor_name(self):
        vendor_name = " ".join(self.cleaned_data.get('vendor_name', '').split())
        if not vendor_name:
            raise forms.ValidationError('Vendor is required.')
        return vendor_name

    def clean_category_name(self):
        category_name = " ".join(self.cleaned_data.get('category_name', '').split())
        return category_name

    def clean_item_description(self):
        item_description = " ".join(self.cleaned_data.get('item_description', '').split())
        return item_description

    def clean(self):
        cleaned_data = super().clean()

        item_name = cleaned_data.get('item_name')
        category_name = cleaned_data.get('category_name')
        item_description = cleaned_data.get('item_description')

        item_obj = None
        if item_name:
            item_obj = Item.objects.filter(name__iexact=item_name).first()

        if item_obj is None:
            if not category_name:
                self.add_error(
                    'category_name',
                    'Category is required when creating a new item.'
                )

            if not item_description:
                self.add_error(
                    'item_description',
                    'Item description is required when creating a new item.'
                )

        return cleaned_data

    def save(self, commit=True):
        purchase = super().save(commit=False)

        item_name = self.cleaned_data.get('item_name')
        category_name = self.cleaned_data.get('category_name')
        vendor_name = self.cleaned_data.get('vendor_name')
        item_description = self.cleaned_data.get('item_description')

        item_obj = Item.objects.filter(name__iexact=item_name).first()

        if item_obj is None:
            category_obj = Category.objects.filter(name__iexact=category_name).first()
            if category_obj is None:
                category_obj = Category.objects.create(name=category_name)

            item_obj = Item.objects.create(
                name=item_name,
                description=item_description,
                category=category_obj,
                quantity=0,
                price=self.cleaned_data.get('price')
            )

        vendor_obj = Vendor.objects.filter(name__iexact=vendor_name).first()
        if vendor_obj is None:
            vendor_obj = Vendor.objects.create(name=vendor_name)

        purchase.item = item_obj
        purchase.vendor = vendor_obj

        if commit:
            purchase.save()

        return purchase