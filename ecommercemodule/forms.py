from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import (
    PasswordChangeForm,
    PasswordResetForm,
    UserCreationForm,
)

from auroramart.models import Customer
from .models import Review

User = get_user_model()


class CustomerForm(forms.ModelForm):
    """Form for customer profile management (both creation and updates)"""
    
    GENDER_CHOICES = [
        ('', 'Select your gender'),
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]
    
    EMPLOYMENT_CHOICES = [
        ('', 'Select employment status'),
        ('Full-time', 'Full-time'),
        ('Part-time', 'Part-time'),
        ('Self-employed', 'Self-employed'),
        ('Student', 'Student'),
        ('Retired', 'Retired'),
    ]
    
    OCCUPATION_CHOICES = [
        ('', 'Select your occupation'),
        ('Admin', 'Admin'),
        ('Education', 'Education'),
        ('Sales', 'Sales'),
        ('Service', 'Service'),
        ('Skilled Trades', 'Skilled Trades'),
        ('Tech', 'Tech'),
    ]
    
    EDUCATION_CHOICES = [
        ('', 'Select your education level'),
        ('Secondary', 'Secondary'),
        ('Diploma', 'Diploma'),
        ('Bachelor', 'Bachelor'),
        ('Master', 'Master'),
        ('Doctorate', 'Doctorate'),
    ]
    
    gender = forms.ChoiceField(
        choices=GENDER_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    employment_status = forms.ChoiceField(
        choices=EMPLOYMENT_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    occupation = forms.ChoiceField(
        choices=OCCUPATION_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    education = forms.ChoiceField(
        choices=EDUCATION_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    age = forms.IntegerField(
        required=True,
        min_value=18,
        max_value=100,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter your age'})
    )
    
    household_size = forms.IntegerField(
        required=True,
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Number of people in household'})
    )
    
    has_children = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    monthly_income_sgd = forms.DecimalField(
        required=True,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter monthly income in SGD', 'step': '0.01'})
    )
    
    class Meta:
        model = Customer
        fields = [
            'age',
            'gender',
            'employment_status',
            'occupation',
            'education',
            'household_size',
            'has_children',
            'monthly_income_sgd',
        ]
    
    def clean_age(self):
        age = self.cleaned_data.get('age')
        if age and not 18 <= age <= 100:
            raise forms.ValidationError('Age must be between 18 and 100.')
        return age
    
    def clean_household_size(self):
        size = self.cleaned_data.get('household_size')
        if size and size < 1:
            raise forms.ValidationError('Household size must be at least 1.')
        return size
    
    def clean_monthly_income_sgd(self):
        income = self.cleaned_data.get('monthly_income_sgd')
        if income and income < 0:
            raise forms.ValidationError('Monthly income cannot be negative.')
        return income


class RegistrationForm(UserCreationForm):
    username = forms.CharField(
        min_length=4,
        max_length=30,
        help_text="Use 4-30 characters.",
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "username"}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "username"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "current-password"}
        )
    )

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get("username")
        password = cleaned.get("password")
        if username and password:
            user = authenticate(username=username, password=password)
            if not user or not user.is_active:
                raise forms.ValidationError("Invalid username or password.")
            self.user = user
        return cleaned

    def get_user(self):
        return getattr(self, "user", None)


class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
    )


class CartItemUpdateForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
        help_text="Set to 0 to remove the item.",
    )


class CheckoutConfirmForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        initial=True,
        label="I confirm the above order summary is correct.",
    )


class CheckoutForm(forms.Form):
    """
    Comprehensive checkout form with delivery and payment information.
    Includes server-side validation for Singapore postal codes, mobile numbers,
    card details (Luhn check), expiry dates, and CVV.
    """
    
    # ========================================
    # Customer / Delivery Information
    # ========================================
    recipient_name = forms.CharField(
        max_length=255,
        required=True,
        label="Recipient Name",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Full name of recipient",
            "autocomplete": "name"
        })
    )
    
    mobile_number = forms.CharField(
        max_length=20,
        required=True,
        label="Mobile Number",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g., +65 9123 4567 or 91234567",
            "autocomplete": "tel"
        })
    )
    
    email = forms.EmailField(
        required=False,
        label="Email Address (Optional)",
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "your.email@example.com",
            "autocomplete": "email"
        })
    )
    
    postal_code = forms.CharField(
        max_length=6,
        required=True,
        label="Postal Code",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "6-digit Singapore postal code",
            "autocomplete": "postal-code"
        })
    )
    
    address_line1 = forms.CharField(
        max_length=255,
        required=True,
        label="Street / Address Line 1",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Will auto-fill from postal code",
            "autocomplete": "address-line1"
        })
    )
    
    address_line2 = forms.CharField(
        max_length=255,
        required=False,
        label="Unit / Address Line 2 (Optional)",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Unit number, floor, etc.",
            "autocomplete": "address-line2"
        })
    )
    
    delivery_notes = forms.CharField(
        required=False,
        label="Delivery Notes (Optional)",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "placeholder": "Any special instructions for delivery...",
            "rows": 3
        })
    )
    
    # ========================================
    # Save Address Option
    # ========================================
    save_address = forms.BooleanField(
        required=False,
        initial=False,
        label="Save this address for future orders",
        widget=forms.CheckboxInput(attrs={
            "class": "form-check-input"
        })
    )
    
    address_label = forms.CharField(
        max_length=50,
        required=False,
        label="Address Label (e.g., Home, Work)",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Optional: Give this address a label"
        })
    )
    
    set_as_default = forms.BooleanField(
        required=False,
        initial=False,
        label="Set as my default address",
        widget=forms.CheckboxInput(attrs={
            "class": "form-check-input"
        })
    )
    
    # ========================================
    # Payment Information
    # ========================================
    cardholder_name = forms.CharField(
        max_length=255,
        required=True,
        label="Cardholder Name",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Name as shown on card",
            "autocomplete": "cc-name"
        })
    )
    
    card_number = forms.CharField(
        max_length=19,  # 16 digits + 3 spaces
        required=True,
        label="Card Number",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "1234 5678 9012 3456",
            "autocomplete": "cc-number"
        })
    )
    
    expiry = forms.CharField(
        max_length=5,
        required=True,
        label="Expiry Date (MM/YY)",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "MM/YY",
            "autocomplete": "cc-exp"
        })
    )
    
    cvv = forms.CharField(
        max_length=3,
        required=True,
        label="CVV",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "123",
            "autocomplete": "cc-csc"
        })
    )
    
    # ========================================
    # Validation Methods
    # ========================================
    
    def clean_postal_code(self):
        """Validate Singapore postal code (exactly 6 digits)."""
        postal_code = self.cleaned_data.get("postal_code", "").strip()
        
        # Remove any spaces or dashes
        postal_code = postal_code.replace(" ", "").replace("-", "")
        
        # Check if exactly 6 digits
        import re
        if not re.match(r'^\d{6}$', postal_code):
            raise forms.ValidationError(
                "Please enter a valid 6-digit Singapore postal code."
            )
        
        return postal_code
    
    def clean_mobile_number(self):
        """Validate mobile number (at least 8 digits, allow +65 prefix)."""
        mobile = self.cleaned_data.get("mobile_number", "").strip()
        
        # Remove common formatting characters
        cleaned = mobile.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Remove +65 country code if present
        if cleaned.startswith("+65"):
            cleaned = cleaned[3:]
        elif cleaned.startswith("65") and len(cleaned) > 8:
            cleaned = cleaned[2:]
        
        # Check if at least 8 digits remain
        import re
        if not re.match(r'^\d{8,}$', cleaned):
            raise forms.ValidationError(
                "Please enter a valid mobile number (at least 8 digits)."
            )
        
        # Return formatted version with +65 prefix
        return f"+65{cleaned}"
    
    def clean_card_number(self):
        """Validate card number (16 digits with Luhn check)."""
        card_number = self.cleaned_data.get("card_number", "").strip()
        
        # Remove spaces
        card_number = card_number.replace(" ", "").replace("-", "")
        
        # Check if exactly 16 digits
        import re
        if not re.match(r'^\d{16}$', card_number):
            raise forms.ValidationError(
                "Card number must be exactly 16 digits."
            )
        
        # Perform Luhn check
        if not self._luhn_check(card_number):
            raise forms.ValidationError(
                "Card number is invalid. Please check and try again."
            )
        
        return card_number
    
    def clean_expiry(self):
        """Validate expiry date (MM/YY format and must be in the future)."""
        expiry = self.cleaned_data.get("expiry", "").strip()
        
        # Check format
        import re
        if not re.match(r'^\d{2}/\d{2}$', expiry):
            raise forms.ValidationError(
                "Expiry date must be in MM/YY format."
            )
        
        # Parse month and year
        try:
            month_str, year_str = expiry.split("/")
            month = int(month_str)
            year = int(year_str) + 2000  # Convert YY to YYYY
            
            # Validate month range
            if not 1 <= month <= 12:
                raise forms.ValidationError(
                    "Invalid month. Please enter a value between 01 and 12."
                )
            
            # Check if date is in the future
            from datetime import datetime
            now = datetime.now()
            
            # Card expires at end of the month
            if year < now.year or (year == now.year and month < now.month):
                raise forms.ValidationError(
                    "Expiry date must be in the future."
                )
            
        except (ValueError, AttributeError):
            raise forms.ValidationError(
                "Invalid expiry date format."
            )
        
        return expiry
    
    def clean_cvv(self):
        """Validate CVV (exactly 3 digits)."""
        cvv = self.cleaned_data.get("cvv", "").strip()
        
        # Check if exactly 3 digits
        import re
        if not re.match(r'^\d{3}$', cvv):
            raise forms.ValidationError(
                "CVV must be exactly 3 digits."
            )
        
        return cvv
    
    @staticmethod
    def _luhn_check(card_number: str) -> bool:
        """
        Implement Luhn algorithm to validate card number.
        
        The Luhn algorithm:
        1. From rightmost digit (excluding check digit), double every second digit
        2. If doubled value > 9, subtract 9
        3. Sum all digits
        4. If sum % 10 == 0, card number is valid
        """
        def digits_of(n):
            return [int(d) for d in str(n)]
        
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        
        checksum = sum(odd_digits)
        for digit in even_digits:
            checksum += sum(digits_of(digit * 2))
        
        return checksum % 10 == 0


class StorePasswordResetForm(PasswordResetForm):
    """
    Swallows "email not found" errors while still logging the attempt so
    we can show a generic success message.
    """

    def clean_email(self):
        email = super(forms.Form, self).clean().get("email") or self.data.get("email", "")
        email = email.strip()
        self._users_cache = list(self.get_users(email))
        self.cleaned_data["email"] = email
        return email

    def save(self, *args, **kwargs):
        if not getattr(self, "_users_cache", []):
            return None
        return super().save(*args, **kwargs)


class ReviewForm(forms.ModelForm):
    """Form for creating/editing product reviews with interactive star rating"""
    
    rating = forms.IntegerField(
        min_value=1,
        max_value=5,
        widget=forms.HiddenInput(attrs={'id': 'rating-value'}),
        label="Rate this product"
    )
    
    body = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Share your thoughts about this product...',
            'rows': 4
        }),
        label="Your Review"
    )
    
    class Meta:
        model = Review
        fields = ['rating', 'body']
    
    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if not rating or not 1 <= rating <= 5:
            raise forms.ValidationError('Please select a star rating between 1 and 5.')
        return rating
    
    def clean_body(self):
        body = self.cleaned_data.get('body', '').strip()
        if not body:
            raise forms.ValidationError('Review cannot be empty.')
        if len(body) < 10:
            raise forms.ValidationError('Review must be at least 10 characters long.')
        return body