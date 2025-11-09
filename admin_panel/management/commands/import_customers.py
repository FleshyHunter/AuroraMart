import pandas as pd
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from auroramart.models import Customer, Category

User = get_user_model()

class Command(BaseCommand):
    help = 'Import customers from CSV'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the customers CSV file')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        df = pd.read_csv(csv_file, encoding='latin1')

        for i, row in df.iterrows():
            # Create a user for each customer
            username = f"customer{i+1:04d}"
            email = f"{username}@example.com"
            
            # Check if user already exists
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': email}
            )
            if created:
                user.set_unusable_password()
                user.save()
            
            # Get or create preferred category if it exists
            preferred_category = None
            if pd.notna(row.get('preferred_category')) and row['preferred_category']:
                category_name = row['preferred_category']
                preferred_category, _ = Category.objects.get_or_create(
                    name=category_name,
                    defaults={'slug': category_name.lower().replace(' ', '-')}
                )
            
            # Create or update customer profile
            Customer.objects.update_or_create(
                user=user,
                defaults={
                    'age': int(row['age']) if pd.notna(row.get('age')) else None,
                    'gender': row.get('gender', ''),
                    'employment_status': row.get('employment_status', ''),
                    'occupation': row.get('occupation', ''),
                    'education': row.get('education', ''),
                    'household_size': int(row['household_size']) if pd.notna(row.get('household_size')) else None,
                    'has_children': bool(row.get('has_children', False)),
                    'monthly_income_sgd': float(row['monthly_income_sgd']) if pd.notna(row.get('monthly_income_sgd')) else None,
                    'preferred_category': preferred_category,
                }
            )

        self.stdout.write(self.style.SUCCESS(f'Successfully imported {len(df)} customers from {csv_file}'))
