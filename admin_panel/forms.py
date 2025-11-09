from django import forms
from auroramart.models import Product, Customer
from django.core.validators import MinValueValidator

class ProductForm(forms.ModelForm):
    # Override quantity fields to ensure non-negative
    quantity_on_hand = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Quantity on hand'})
    )
    reorder_quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Reorder quantity'})
    )

    class Meta:
        model = Product
        fields = [
            'sku', 'name', 'description', 'category', 'subcategory',
            'quantity_on_hand', 'reorder_quantity', 'unit_price',
            'rating', 'is_active'
        ]
        widgets = {
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SKU Code'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Product Description', 'rows':3}),
            # Use select widgets so option labels use __str__ of Category/SubCategory (names)
            'category': forms.Select(attrs={'class': 'form-select'}),
            'subcategory': forms.Select(attrs={'class': 'form-select'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'max': '5'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = '__all__'  # or specify the fields you want: ['age', 'gender', 'occupation', 'education']
        widgets = {
            'age': forms.NumberInput(attrs={'style': 'padding: 8px; border: 1px solid #ccc; border-radius: 4px;'}),
            'gender': forms.TextInput(attrs={'style': 'padding: 8px; border: 1px solid #ccc; border-radius: 4px;'}),
            'occupation': forms.TextInput(attrs={'style': 'padding: 8px; border: 1px solid #ccc; border-radius: 4px;'}),
            'education': forms.TextInput(attrs={'style': 'padding: 8px; border: 1px solid #ccc; border-radius: 4px;'}),
        }
