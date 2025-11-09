import csv
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from ecommercemodule.models import Category, Customer

User = get_user_model()


class Command(BaseCommand):
    help = 'Update existing customer profiles with data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='data/b2c_customers_100.csv',
            help='Path to the customer CSV file'
        )

    def handle(self, *args, **options):
        csv_file = options['file']
        
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        csv_path = base_dir / csv_file
        
        if not csv_path.exists():
            self.stdout.write(self.style.ERROR(f'CSV file not found: {csv_path}'))
            return
        
        self.stdout.write(f'Reading customer data from: {csv_path}')
        
        updated_count = 0
        skipped_count = 0
        
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for index, row in enumerate(reader, start=1):
                username = f'customer{index:04d}'
                
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'User {username} not found, skipping...')
                    )
                    continue
                
                try:
                    with transaction.atomic():
                        customer, _ = Customer.objects.get_or_create(user=user)
                        
                        # Update customer profile with CSV data
                        customer.age = int(row['age'])
                        customer.gender = row['gender']
                        customer.employment_status = row['employment_status']
                        customer.occupation = row['occupation']
                        customer.education = row['education']
                        customer.household_size = int(row['household_size'])
                        customer.has_children = bool(int(row['has_children']))
                        # Round monthly income to 2 decimal places
                        customer.monthly_income_sgd = Decimal(row['monthly_income_sgd']).quantize(Decimal('0.01'))
                        
                        # Set preferred category if it exists
                        category_name = row.get('preferred_category', '').strip()
                        if category_name:
                            try:
                                category = Category.objects.get(name=category_name)
                                customer.preferred_category = category
                            except Category.DoesNotExist:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'Category not found for {username}: {category_name}'
                                    )
                                )
                        
                        customer.save()
                        updated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Updated {username}: {customer.age}yo {customer.gender}, '
                                f'{customer.occupation} - {category_name}'
                            )
                        )
                
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Error updating {username}: {str(e)}')
                    )
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'Update completed!'))
        self.stdout.write(f'  • Updated: {updated_count} customers')
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'  • Skipped: {skipped_count} (users not found)'))
        self.stdout.write('='*60)
