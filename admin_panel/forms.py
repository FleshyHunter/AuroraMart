from django import forms
from auroramart.models import Product, Customer, SubCategory
from django.core.validators import MinValueValidator, FileExtensionValidator
from .models import Voucher


class VoucherForm(forms.ModelForm):
    class Meta:
        model = Voucher
        fields = ['name', 'days_valid', 'percent_off', 'cap_amount']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Voucher name'}),
            'days_valid': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'percent_off': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'cap_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }

    def clean_percent_off(self):
        val = self.cleaned_data.get('percent_off')
        if val is None:
            return val
        if val < 0 or val > 100:
            raise forms.ValidationError('Percent off must be between 0 and 100')
        return val

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
    # Only allow image file uploads
    image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp'])]
    )

    class Meta:
        model = Product
        fields = [
            'sku', 'name', 'description', 'category', 'subcategory',
            'quantity_on_hand', 'reorder_quantity', 'unit_price',
            'rating', 'is_active', 'image'
        ]
        widgets = {
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SKU Code'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Product Description', 'rows':3}),
            # Use select widgets so option labels use __str__ of Category/SubCategory (names)
            'category': forms.Select(attrs={'class': 'form-select', 'id': 'id_category'}),
            'subcategory': forms.Select(attrs={'class': 'form-select', 'id': 'id_subcategory'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'max': '5'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            # image widget overridden above with accept="image/*"
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get the selected category from POST data or from the instance
        category_id = None
        
        if self.is_bound and 'category' in self.data:
            # Form is bound (POST request) - get category from POST data
            try:
                category_id = int(self.data.get('category'))
            except (ValueError, TypeError):
                category_id = None
        elif self.instance and self.instance.pk:
            # Editing existing product - get category from instance
            try:
                category_id = self.instance.category_id
            except:
                category_id = None
        
        # Filter subcategories based on selected category
        # JavaScript will handle the dynamic loading, but we still filter server-side for validation
        if category_id:
            self.fields['subcategory'].queryset = SubCategory.objects.filter(category_id=category_id)
        else:
            # Show all subcategories initially, JavaScript will filter them
            self.fields['subcategory'].queryset = SubCategory.objects.all()

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
