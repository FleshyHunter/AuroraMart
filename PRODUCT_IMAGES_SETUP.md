# Product Images Setup Guide

## Overview
This implementation adds image support to the Product model with two options:
1. **External URLs** (e.g., from Google Images) - stored in `image_url` field
2. **Uploaded files** - stored in `image` field

**Priority**: Uploaded images take precedence over external URLs.

---

## What Was Changed

### 1. Product Model (`auroramart/models.py`)
Added two new fields:
- `image_url` - URLField for external image URLs (max 500 chars)
- `image` - ImageField for uploaded images (stored in `media/products/`)
- `get_image_url` property - Returns the appropriate image URL (uploaded > external)

### 2. Settings (`auroramart/settings.py`)
Added media file configuration:
```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

### 3. URLs (`auroramart/urls.py`)
Added media file serving for development:
```python
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

### 4. Admin Interface (`auroramart/admin.py`)
Enhanced ProductAdmin with:
- Thumbnail preview in list view (50x50px)
- Large image preview in form view (max 300x300px)
- Organized fieldsets with dedicated "Images" section
- Both `image` and `image_url` fields editable

### 5. Management Command
Created `populate_product_images` command to fetch Google Images URLs.

---

## Installation Steps

### Step 1: Install Required Packages
```powershell
pip install Pillow requests beautifulsoup4
```

**Package purposes:**
- `Pillow` - Required for Django's ImageField
- `requests` - HTTP library for web scraping
- `beautifulsoup4` - HTML parsing for Google Images

### Step 2: Create and Apply Migrations
```powershell
cd "c:\Users\chanw\Documents\NUS\NUS Y2S1\IS2108 Full-stack Software Engineering for AI Solutions I\Projects\auroramart\auroramart"

python manage.py makemigrations
python manage.py migrate
```

### Step 3: Populate Existing Products with Static Category Images
```powershell
# Populate products without images (safe, recommended)
python manage.py populate_product_images

# Process only first 10 products (for testing)
python manage.py populate_product_images --limit 10

# Force update ALL products (overwrites existing image_url)
python manage.py populate_product_images --force

# Process only specific category
python manage.py populate_product_images --category Electronics
```

**Note**: The command now uses a static `CATEGORY_IMAGE_MAP` that maps (category, subcategory) pairs to high-quality placeholder images. No web scraping is performed.

**Command Options:**
- `--force` - Update all products, even those with existing image_url
- `--limit N` - Process only N products
- `--category NAME` - Only process products in specified category

**How It Works:**
The command uses a predefined `CATEGORY_IMAGE_MAP` dictionary that maps (category, subcategory) pairs to high-quality Unsplash image URLs. To add or update mappings, edit `auroramart/management/commands/populate_product_images.py`.

---

## Using the Admin Interface

### Viewing Products
1. Go to Django Admin → Products
2. You'll see thumbnail previews in the first column
3. Products without images show "No image" text

### Editing Product Images

The product form now includes a dedicated "Product Images" section with image preview.

**Option 1: Upload an Image File** (Recommended)
1. Click "Add Product" or "Edit" on an existing product
2. Scroll to the "Product Images" section (at the bottom)
3. Click "Choose File" under "Image"
4. Upload a JPG/PNG/WebP file
5. Save
6. The uploaded image takes priority over external URLs

**Option 2: Use External URL**
1. In the product form, scroll to "Product Images" section
2. Paste a URL in "Image URL" field
   - Example: `https://example.com/product.jpg`
3. Save
4. This is used only if no uploaded image exists

**Option 3: Auto-populate from Category Mapping**
1. Leave both image fields empty
2. Run the management command (see Step 3 above)
3. The system assigns a category-appropriate placeholder image

### Image Priority
If both fields are set:
- **Uploaded image** is used (preferred)
- External URL is ignored

To switch back to URL:
1. Clear the uploaded image field
2. Keep the URL field populated

---

## Technical Details

### Directory Structure
```
auroramart/
  ├── auroramart/
  │   ├── management/
  │   │   └── commands/
  │   │       └── populate_product_images.py
  │   ├── models.py (updated)
  │   ├── admin.py (updated)
  │   ├── settings.py (updated)
  │   └── urls.py (updated)
  └── media/
      └── products/  (auto-created for uploads)
```

### Google Images Scraping Strategy

**Smart Search with Multiple Fallback Strategies:**

The command tries progressively broader searches until a good image is found:

1. **Strategy 1**: Full product name + category + subcategory
   - Example: "Samsung Galaxy S21 Electronics Smartphones"
   - Most specific, best results

2. **Strategy 2**: Product name without brand (drops first word)
   - Example: "Galaxy S21 Electronics" (removed "Samsung")
   - Useful when brand name causes too-specific results

3. **Strategy 3**: Category + subcategory only
   - Example: "Electronics Smartphones"
   - Generic fallback for difficult products

**Image Quality Filtering:**

The command automatically:
- ✅ Filters out images smaller than specified `--min-size` (default: 200px)
- ✅ Scores images by dimensions (larger = better)
- ✅ Prefers reasonable aspect ratios (rejects extreme panoramas)
- ✅ Prioritizes direct image URLs over cached thumbnails
- ✅ Skips Google's infrastructure images

**Parsing Methods:**
1. **JavaScript data parsing** - Extracts high-res URLs with dimensions
2. **Image metadata extraction** - Finds width/height information
3. **Thumbnail fallback** - Uses Google's cached thumbnails as last resort

**Note**: Google may block frequent requests. Use `--delay` option for rate limiting (recommended: 1.5-2.0 seconds).

### Database Fields
```python
# Product model fields
image_url = URLField(max_length=500, blank=True, null=True)
image = ImageField(upload_to='products/', blank=True, null=True)

# Helper property
@property
def get_image_url(self):
    if self.image:
        return self.image.url  # e.g., /media/products/shoe.jpg
    return self.image_url or ''  # e.g., https://...
```

---

## Usage in Templates

### Display Product Image
```django
{% if product.get_image_url %}
    <img src="{{ product.get_image_url }}" alt="{{ product.name }}">
{% else %}
    <img src="{% static 'img/no-image.png' %}" alt="No image">
{% endif %}
```

### Check Image Type
```django
{% if product.image %}
    <!-- Uploaded image -->
    <span class="badge">Uploaded</span>
{% elif product.image_url %}
    <!-- External URL -->
    <span class="badge">External</span>
{% endif %}
```

---

## Production Considerations

### 1. Google Images Alternative
For production, consider using:
- **Google Custom Search API** (official, requires API key)
- **Unsplash API** (free, high-quality stock photos)
- **Pexels API** (free, curated images)

Replace the scraping logic in `populate_product_images.py` with API calls.

### 2. Image Storage
For production:
- Use cloud storage (AWS S3, Cloudinary, etc.)
- Configure Django to use django-storages
- Update `MEDIA_ROOT` and `MEDIA_URL` accordingly

### 3. Image Optimization
Consider adding:
- Image resizing on upload
- Thumbnail generation
- WebP format conversion
- CDN integration

### 4. Rate Limiting
The current scraper includes basic rate limiting. For production:
- Use proper API with authentication
- Implement exponential backoff
- Add retry logic with delays

---

## Troubleshooting

### Issue: "No module named 'PIL'"
**Solution**: Install Pillow
```powershell
pip install Pillow
```

### Issue: "No module named 'bs4'"
**Solution**: Install beautifulsoup4
```powershell
pip install beautifulsoup4
```

### Issue: Images not appearing in admin
**Check:**
1. Migrations applied? → `python manage.py migrate`
2. MEDIA_URL configured in settings?
3. URLs updated to serve media files?
4. DEBUG = True in settings?

### Issue: Management command not found
**Check:**
1. `__init__.py` exists in management/ and commands/ directories?
2. Command file named correctly? → `populate_product_images.py`
3. Command class inherits from `BaseCommand`?

### Issue: Google Images returns no results
**Possible causes:**
- Google is blocking requests (use --delay)
- Product name is too generic
- Network connectivity issues
- Google changed their HTML structure

**Solutions:**
- Increase delay: `--delay 3.0`
- Manually set image_url in admin
- Upload image file instead
- Use official API (see Production Considerations)

---

## Example Workflows

### Workflow 1: Bulk Import with Google Images (Recommended)
```powershell
# 1. Create products via admin or import command
# 2. Run image population with quality settings
python manage.py populate_product_images --delay 1.5 --min-size 300

# 3. Review in admin, manually fix any missing images
```

### Workflow 2: Category-by-Category Processing
```powershell
# Process one category at a time for better control
python manage.py populate_product_images --category Electronics --delay 2.0
python manage.py populate_product_images --category Apparel --delay 2.0
python manage.py populate_product_images --category Home --delay 2.0

# Review each category in admin before moving to next
```

### Workflow 3: Test First, Then Scale
```powershell
# 1. Test with small sample
python manage.py populate_product_images --limit 5 --min-size 400

# 2. Review results in admin
# 3. If satisfied, process all
python manage.py populate_product_images --delay 1.5 --min-size 400
```

### Workflow 4: Manual Upload for Featured Products
```powershell
# 1. Identify featured products
# 2. In admin, upload high-quality images for those products
# 3. Run command for remaining products
python manage.py populate_product_images
# (skips products with uploaded images)
```

### Workflow 5: High-Quality Images Only
```powershell
# Strict quality requirements
python manage.py populate_product_images --min-size 500 --delay 2.0

# Products without suitable high-res images will be skipped
# Upload manually for those products
```

---

## Next Steps

### Recommended Enhancements
1. **Add image alt text field** for accessibility
2. **Multiple images per product** (ProductImage model with ForeignKey)
3. **Image validation** (size, format, dimensions)
4. **Automatic thumbnail generation** using Pillow
5. **Image CDN integration** for faster loading

### Template Integration
Update your product templates to use `product.get_image_url`:
- `product_list.html`
- `product_detail.html`
- `category_list.html`
- `cart.html`
- `order_success.html`

---

## Summary

✅ **Completed:**
- ✓ Added `image_url` and `image` fields to Product model
- ✓ Configured MEDIA settings for file uploads
- ✓ Created management command for Google Images URLs
- ✓ Updated admin with thumbnail previews
- ✓ Organized admin form with fieldsets

📝 **To Do:**
- [ ] Run `pip install Pillow requests beautifulsoup4`
- [ ] Run `python manage.py makemigrations`
- [ ] Run `python manage.py migrate`
- [ ] Run `python manage.py populate_product_images`
- [ ] Update storefront templates to display images
- [ ] Test image uploads in admin

🎯 **Result:**
Your products now support both external URLs (auto-fetched from Google) and manual file uploads, with priority given to uploaded images. The admin interface displays thumbnails for easy visual identification.
