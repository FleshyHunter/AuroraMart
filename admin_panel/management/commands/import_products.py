import pandas as pd
from django.core.management.base import BaseCommand
from auroramart.models import Product, Category, SubCategory

class Command(BaseCommand):
    help = 'Import products from CSV'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the products CSV file')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        df = pd.read_csv(csv_file, encoding='latin1')

        # Map your CSV columns to your model fields
        for _, row in df.iterrows():
            # Get or create category
            category_name = row['Product Category']
            category, _ = Category.objects.get_or_create(
                name=category_name,
                defaults={'slug': category_name.lower().replace(' ', '-')}
            )
            
            # Get or create subcategory
            subcategory_name = row['Product Subcategory']
            subcategory, _ = SubCategory.objects.get_or_create(
                category=category,
                name=subcategory_name,
                defaults={'slug': subcategory_name.lower().replace(' ', '-')}
            )
            
            Product.objects.update_or_create(
                sku=row['SKU code'],
                defaults={
                    'name': row['Product name'],
                    'description': row['Product description'],
                    'category': category,
                    'subcategory': subcategory,
                    'quantity_on_hand': row['Quantity on hand'],
                    'reorder_quantity': row['Reorder Quantity'],
                    'unit_price': row['Unit price'],
                    'rating': row['Product rating']  # Fixed: changed from 'product_rating' to 'rating'
                }
            )
        self.stdout.write(self.style.SUCCESS(f'Successfully imported products from {csv_file}'))
