from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import (
    PasswordChangeForm,
    PasswordResetForm,
    UserCreationForm,
)

from auroramart.models import Customer

User = get_user_model()


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


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "age",
            "gender",
            "employment_status",
            "occupation",
            "education",
            "household_size",
            "has_children",
            "monthly_income_sgd",
            "preferred_category",
        ]
        widgets = {
            "preferred_category": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_age(self):
        age = self.cleaned_data.get("age")
        if age is not None and not 18 <= age <= 100:
            raise forms.ValidationError("Age must be between 18 and 100.")
        return age

    def clean_household_size(self):
        size = self.cleaned_data.get("household_size")
        if size is not None and size < 1:
            raise forms.ValidationError("Household size must be at least 1.")
        return size

    def clean_monthly_income_sgd(self):
        income = self.cleaned_data.get("monthly_income_sgd")
        if income is not None and income < 0:
            raise forms.ValidationError("Monthly income must be zero or higher.")
        return income


class ProfileCompletionForm(forms.ModelForm):
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


class StorePasswordResetForm(PasswordResetForm):
    """
    Swallows “email not found” errors while still logging the attempt so
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