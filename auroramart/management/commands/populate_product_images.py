"""
Management command to populate product image URLs using a static mapping.

This command uses a
CATEGORY_IMAGE_MAP dict that maps (category, subcategory) to a
high-quality static image URL. For any product with no image_url, the
command will set it using this map. Products without a mapping are
reported in the summary.

Usage:
    python manage.py populate_product_images
    python manage.py populate_product_images --force  # Update all products
    python manage.py populate_product_images --limit 10  # Process only 10 products
    python manage.py populate_product_images --category Electronics  # Only a subset
"""

from django.core.management.base import BaseCommand
from auroramart.models import Product
from django.db.models import Q

# Map of (category, subcategory) -> high-quality image URL
# Keys are matched case-insensitively. If no exact (category, subcategory)
# match is found, we fall back to a category-only entry: (category, None).
#
# NOTE: Update these URLs to suit your catalog. Use stable, high-res images.
# The below examples use generic product images from Unsplash (free license).
CATEGORY_IMAGE_MAP = {
    # Technology / Electronics
    ("technology", "smartphones"): "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=1200&auto=format&fit=crop&q=80",
    ("technology", "laptops"): "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=1200&auto=format&fit=crop&q=80",
    ("technology", "tablets"): "https://images.unsplash.com/photo-1561154464-82e9adf32764?w=1200&auto=format&fit=crop&q=80",
    ("technology", "cameras"): "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=1200&auto=format&fit=crop&q=80",
    ("technology", "audio"): "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=1200&auto=format&fit=crop&q=80",
    ("technology", "wearables"): "https://images.unsplash.com/photo-1579586337278-3befd40fd17a?w=1200&auto=format&fit=crop&q=80",
    ("technology", "accessories"): "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=1200&auto=format&fit=crop&q=80",
    ("technology", None): "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200&auto=format&fit=crop&q=80",
    
    # Electronics (alternate naming)
    ("electronics", "smartphones"): "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=1200&auto=format&fit=crop&q=80",
    ("electronics", "laptops"): "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=1200&auto=format&fit=crop&q=80",
    ("electronics", "tablets"): "https://images.unsplash.com/photo-1561154464-82e9adf32764?w=1200&auto=format&fit=crop&q=80",
    ("electronics", "cameras"): "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=1200&auto=format&fit=crop&q=80",
    ("electronics", None): "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200&auto=format&fit=crop&q=80",

    # Office & Computers
    ("office products", "keyboards"): "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=1200&auto=format&fit=crop&q=80",
    ("office products", "mice"): "https://images.unsplash.com/photo-1527814050087-3793815479db?w=1200&auto=format&fit=crop&q=80",
    ("office products", "monitors"): "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=1200&auto=format&fit=crop&q=80",
    ("office products", "storage"): "https://images.unsplash.com/photo-1589395937772-1f23c47a4b05?w=1200&auto=format&fit=crop&q=80",
    ("office products", "supplies"): "https://images.unsplash.com/photo-1589395937772-1f23c47a4b05?w=1200&auto=format&fit=crop&q=80",
    ("office products", None): "https://images.unsplash.com/photo-1547082299-de196ea013d6?w=1200&auto=format&fit=crop&q=80",

    # Home & Kitchen
    ("home & kitchen", "furniture"): "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=1200&auto=format&fit=crop&q=80",
    ("home & kitchen", "decor"): "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=1200&auto=format&fit=crop&q=80",
    ("home & kitchen", "home decor"): "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=1200&auto=format&fit=crop&q=80",
    ("home & kitchen", "lighting"): "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=1200&auto=format&fit=crop&q=80",
    ("home & kitchen", "kitchen"): "https://images.unsplash.com/photo-1556911220-bff31c812dba?w=1200&auto=format&fit=crop&q=80",
    ("home & kitchen", "appliances"): "https://images.unsplash.com/photo-1556911220-bff31c812dba?w=1200&auto=format&fit=crop&q=80",
    ("home & kitchen", "cleaning"): "https://images.unsplash.com/photo-1563453392212-326f5e854473?w=1200&auto=format&fit=crop&q=80",
    ("home & kitchen", "vacuum & cleaning"): "https://images.unsplash.com/photo-1563453392212-326f5e854473?w=1200&auto=format&fit=crop&q=80",
    ("home & kitchen", "bedding"): "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=1200&auto=format&fit=crop&q=80",
    ("home & kitchen", "storage"): "https://images.unsplash.com/photo-1566140967404-b8b3932483f5?w=1200&auto=format&fit=crop&q=80",
    ("home & kitchen", None): "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=1200&auto=format&fit=crop&q=80",

    # Clothing / Fashion
    ("clothing", "tops"): "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=1200&auto=format&fit=crop&q=80",
    ("clothing", "shirts"): "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=1200&auto=format&fit=crop&q=80",
    ("clothing", "dresses"): "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=1200&auto=format&fit=crop&q=80",
    ("clothing", "pants"): "https://images.unsplash.com/photo-1506629082955-511b1aa562c8?w=1200&auto=format&fit=crop&q=80",
    ("clothing", "shoes"): "https://images.unsplash.com/photo-1460353581641-37baddab0fa2?w=1200&auto=format&fit=crop&q=80",
    ("clothing", "accessories"): "https://images.unsplash.com/photo-1492707892479-7bc8d5a4ee93?w=1200&auto=format&fit=crop&q=80",
    ("clothing", "jewelry"): "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=1200&auto=format&fit=crop&q=80",
    ("clothing", None): "https://images.unsplash.com/photo-1445205170230-053b83016050?w=1200&auto=format&fit=crop&q=80",

    # Fashion - Men
    ("fashion - men", "tops"): "https://images.unsplash.com/photo-1622445275463-afa2ab738c34?w=1200&auto=format&fit=crop&q=80",
    ("fashion - men", "shirts"): "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=1200&auto=format&fit=crop&q=80",
    ("fashion - men", "bottoms"): "https://images.unsplash.com/photo-1624378515195-6bbdb73dff1a?w=1200&auto=format&fit=crop&q=80",
    ("fashion - men", "pants"): "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=1200&auto=format&fit=crop&q=80",
    ("fashion - men", "shoes"): "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=1200&auto=format&fit=crop&q=80",
    ("fashion - men", "accessories"): "https://images.unsplash.com/photo-1523170335258-f5ed11844a49?w=1200&auto=format&fit=crop&q=80",
    ("fashion - men", None): "https://images.unsplash.com/photo-1490578474895-699cd4e2cf59?w=1200&auto=format&fit=crop&q=80",

    # Fashion - Women
    ("fashion - women", "tops"): "https://images.unsplash.com/photo-1618932260643-eee4a2f652a6?w=1200&auto=format&fit=crop&q=80",
    ("fashion - women", "shirts"): "https://images.unsplash.com/photo-1618932260643-eee4a2f652a6?w=1200&auto=format&fit=crop&q=80",
    ("fashion - women", "bottoms"): "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?w=1200&auto=format&fit=crop&q=80",
    ("fashion - women", "pants"): "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?w=1200&auto=format&fit=crop&q=80",
    ("fashion - women", "dresses"): "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=1200&auto=format&fit=crop&q=80",
    ("fashion - women", "shoes"): "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=1200&auto=format&fit=crop&q=80",
    ("fashion - women", "accessories"): "https://images.unsplash.com/photo-1611591437281-460bfbe1220a?w=1200&auto=format&fit=crop&q=80",
    ("fashion - women", "jewelry"): "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=1200&auto=format&fit=crop&q=80",
    ("fashion - women", None): "https://images.unsplash.com/photo-1483985988355-763728e1935b?w=1200&auto=format&fit=crop&q=80",

    # Beauty & Personal Care
    ("beauty & personal care", "makeup"): "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=1200&auto=format&fit=crop&q=80",
    ("beauty & personal care", "skincare"): "https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=1200&auto=format&fit=crop&q=80",
    ("beauty & personal care", "skin care"): "https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=1200&auto=format&fit=crop&q=80",
    ("beauty & personal care", "fragrance"): "https://images.unsplash.com/photo-1541643600914-78b084683601?w=1200&auto=format&fit=crop&q=80",
    ("beauty & personal care", "hair care"): "https://images.unsplash.com/photo-1527799820374-dcf8d9d4a388?w=1200&auto=format&fit=crop&q=80",
    ("beauty & personal care", "bath & body"): "https://images.unsplash.com/photo-1608571423902-eed4a5ad8108?w=1200&auto=format&fit=crop&q=80",
    ("beauty & personal care", None): "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?w=1200&auto=format&fit=crop&q=80",

    # Books & Media
    ("books", "fiction"): "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=1200&auto=format&fit=crop&q=80",
    ("books", "non-fiction"): "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=1200&auto=format&fit=crop&q=80",
    ("books", "children"): "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=1200&auto=format&fit=crop&q=80",
    ("books", None): "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=1200&auto=format&fit=crop&q=80",
    
    # Sports & Outdoors
    ("sports & outdoors", "fitness"): "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=1200&auto=format&fit=crop&q=80",
    ("sports & outdoors", "outdoor"): "https://images.unsplash.com/photo-1501555088652-021faa106b9b?w=1200&auto=format&fit=crop&q=80",
    ("sports & outdoors", "camping"): "https://images.unsplash.com/photo-1504280390367-361c6d9f38f4?w=1200&auto=format&fit=crop&q=80",
    ("sports & outdoors", "cycling"): "https://images.unsplash.com/photo-1507035895480-2b3156c31fc8?w=1200&auto=format&fit=crop&q=80",
    ("sports & outdoors", None): "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=1200&auto=format&fit=crop&q=80",

    # Toys & Games
    ("toys & games", "building"): "https://images.unsplash.com/photo-1558060370-d644479cb6f7?w=1200&auto=format&fit=crop&q=80",
    ("toys & games", "building sets"): "https://images.unsplash.com/photo-1558060370-d644479cb6f7?w=1200&auto=format&fit=crop&q=80",
    ("toys & games", "puzzles"): "https://images.unsplash.com/photo-1587731556938-38755b4803a6?w=1200&auto=format&fit=crop&q=80",
    ("toys & games", "board games"): "https://images.unsplash.com/photo-1610890716171-6b1bb98ffd09?w=1200&auto=format&fit=crop&q=80",
    ("toys & games", "family"): "https://images.unsplash.com/photo-1629197520535-ee1574dd2d32?w=1200&auto=format&fit=crop&q=80",
    ("toys & games", None): "https://images.unsplash.com/photo-1558060370-d644479cb6f7?w=1200&auto=format&fit=crop&q=80",

    # Automotive
    ("automotive", "parts"): "https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=1200&auto=format&fit=crop&q=80",
    ("automotive", "accessories"): "https://images.unsplash.com/photo-1513064558155-e3c9dd937d8d?w=1200&auto=format&fit=crop&q=80",
    ("automotive", None): "https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=1200&auto=format&fit=crop&q=80",

    # Pet Supplies
    ("pet supplies", "accessories"): "https://images.unsplash.com/photo-1568640347023-a616a30bc3bd?w=1200&auto=format&fit=crop&q=80",
    ("pet supplies", "aquatic"): "https://images.unsplash.com/photo-1522069169874-c58ec4b76be5?w=1200&auto=format&fit=crop&q=80",
    ("pet supplies", "cat"): "https://images.unsplash.com/photo-1545249390-6bdfa286032f?w=1200&auto=format&fit=crop&q=80",
    ("pet supplies", "dog"): "https://images.unsplash.com/photo-1601758228041-f3b2795255f1?w=1200&auto=format&fit=crop&q=80",
    ("pet supplies", "small pets"): "https://images.unsplash.com/photo-1425082661705-1834bfd09dca?w=1200&auto=format&fit=crop&q=80",
    ("pet supplies", None): "https://images.unsplash.com/photo-1601758228041-f3b2795255f1?w=1200&auto=format&fit=crop&q=80",

    # Health & Household
    ("health & household", "vitamins"): "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=1200&auto=format&fit=crop&q=80",
    ("health & household", "personal care"): "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=1200&auto=format&fit=crop&q=80",
    ("health & household", None): "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?w=1200&auto=format&fit=crop&q=80",

    # Baby Products
    ("baby", "toys"): "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?w=1200&auto=format&fit=crop&q=80",
    ("baby", "clothing"): "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=1200&auto=format&fit=crop&q=80",
    ("baby", None): "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?w=1200&auto=format&fit=crop&q=80",

    # Food & Grocery
    ("grocery", None): "https://images.unsplash.com/photo-1543168256-8133cc8e3ee4?w=1200&auto=format&fit=crop&q=80",
    ("food", None): "https://images.unsplash.com/photo-1543168256-8133cc8e3ee4?w=1200&auto=format&fit=crop&q=80",

    # Groceries & Gourmet
    ("groceries & gourmet", "beverages"): "https://images.unsplash.com/photo-1437418747212-8d9709afab22?w=1200&auto=format&fit=crop&q=80",
    ("groceries & gourmet", "breakfast"): "https://images.unsplash.com/photo-1533089860892-a7c6f0a88666?w=1200&auto=format&fit=crop&q=80",
    ("groceries & gourmet", "health foods"): "https://images.unsplash.com/photo-1490645935967-10de6ba17061?w=1200&auto=format&fit=crop&q=80",
    ("groceries & gourmet", "pantry staples"): "https://images.unsplash.com/photo-1588964895597-cfccd6e2dbf9?w=1200&auto=format&fit=crop&q=80",
    ("groceries & gourmet", "snacks"): "https://images.unsplash.com/photo-1599490659213-e2b9527bd087?w=1200&auto=format&fit=crop&q=80",
    ("groceries & gourmet", None): "https://images.unsplash.com/photo-1543168256-8133cc8e3ee4?w=1200&auto=format&fit=crop&q=80",

    # Health
    ("health", "first aid"): "https://images.unsplash.com/photo-1603398938378-e54eab446dde?w=1200&auto=format&fit=crop&q=80",
    ("health", "medical devices"): "https://images.unsplash.com/photo-1584362917165-526a968579e8?w=1200&auto=format&fit=crop&q=80",
    ("health", "personal care"): "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=1200&auto=format&fit=crop&q=80",
    ("health", "supplements"): "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=1200&auto=format&fit=crop&q=80",
    ("health", None): "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?w=1200&auto=format&fit=crop&q=80",
}


class Command(BaseCommand):
    help = 'Populate product image_url fields with Google Images URLs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Update all products, even those with existing image_url',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of products to process',
        )
        parser.add_argument(
            '--category',
            type=str,
            default=None,
            help='Only process products in specified category',
        )

    def handle(self, *args, **options):
        force = options['force']
        limit = options['limit']
        category_filter = options['category']

        self.stdout.write('Using static CATEGORY_IMAGE_MAP (no scraping).')

        # Query products (prefetch relationships for efficiency)
        if force:
            products = Product.objects.select_related('category', 'subcategory').all()
            self.stdout.write('Processing ALL products (force mode)...')
        else:
            products = (Product.objects.select_related('category', 'subcategory')
                                   .filter(Q(image_url__isnull=True) | Q(image_url="")))
            self.stdout.write('Processing products without image_url...')

        # Filter by category if specified
        if category_filter:
            products = products.filter(category__name__icontains=category_filter)
            self.stdout.write(f'Filtering by category: {category_filter}')

        if limit:
            products = products[:limit]
            self.stdout.write(f'Limited to {limit} products')

        total = products.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('No products to process.'))
            return

        self.stdout.write(f'Found {total} product(s) to process\n')

        updated_count = 0
        failed_count = 0

        unmapped_pairs = set()
        for idx, product in enumerate(products, 1):
            self.stdout.write(f'[{idx}/{total}] Processing: {product.name}')
            cat_name = product.category.name if getattr(product, 'category', None) else None
            subcat_name = product.subcategory.name if getattr(product, 'subcategory', None) else None
            self.stdout.write(f'  Category: {cat_name}, Subcategory: {subcat_name}')
            
            try:
                image_url = self.get_mapped_image_url(cat_name, subcat_name)
                
                if image_url:
                    product.image_url = image_url
                    product.save(update_fields=['image_url'])
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Updated: {image_url[:100]}...')
                    )
                else:
                    failed_count += 1
                    unmapped_pairs.add((cat_name or '<none>', subcat_name or '<none>'))
                    self.stdout.write(
                        self.style.WARNING('  ✗ No mapping found for this category/subcategory')
                    )
                    
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error: {str(e)}')
                )

        # Summary
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS(f'✓ Successfully updated: {updated_count}'))
        if failed_count > 0:
            self.stdout.write(self.style.WARNING(f'✗ Unmapped products: {failed_count}'))
            self.stdout.write('Unmapped category/subcategory pairs:')
            for cat, sub in sorted(unmapped_pairs):
                self.stdout.write(f'  - ({cat}, {sub})')
        self.stdout.write('=' * 50)

    def get_mapped_image_url(self, category_name, subcategory_name):
        """Return mapped image URL by (category, subcategory) with fallbacks.

        Matching is case-insensitive. Tries exact (category, subcategory)
        first, then (category, None). Returns None if no mapping.
        """
        if not category_name and not subcategory_name:
            return None

        cat_key = (category_name or '').strip().lower() or None
        subcat_key = (subcategory_name or '').strip().lower() or None

        if cat_key is None and subcat_key is None:
            return None

        # Exact pair
        if cat_key is not None and subcat_key is not None:
            url = CATEGORY_IMAGE_MAP.get((cat_key, subcat_key))
            if url:
                return url

        # Category-only fallback
        if cat_key is not None:
            url = CATEGORY_IMAGE_MAP.get((cat_key, None))
            if url:
                return url

        return None
