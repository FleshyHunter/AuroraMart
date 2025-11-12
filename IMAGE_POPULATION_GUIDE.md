# Populate Product Images - Quick Reference

## Smart Search Strategies

The command automatically tries multiple search approaches for each product:

### Strategy Progression

```
Product: "Samsung Galaxy S21"
Category: "Electronics"
Subcategory: "Smartphones"

1st Try: "Samsung Galaxy S21 Electronics Smartphones"
         ↓ (if no good image found)
2nd Try: "Galaxy S21 Electronics"  [removed brand name]
         ↓ (if still no good image)
3rd Try: "Electronics Smartphones"  [generic fallback]
```

## Image Quality Filtering

### Automatic Quality Checks
- ✅ **Minimum dimensions**: Configurable via `--min-size` (default: 200px)
- ✅ **Aspect ratio check**: Rejects extreme panoramas (>3:1 ratio)
- ✅ **Size scoring**: Larger images score higher
- ✅ **Source filtering**: Skips Google infrastructure images

### Quality Comparison

| Min Size | Quality Level | Use Case |
|----------|---------------|----------|
| 100px | Low | Testing only |
| 200px | Standard | Default, most products |
| 300px | Good | Recommended for storefront |
| 400px | High | Featured products |
| 500px | Very High | Premium products, hero images |

## Command Examples

### Basic Usage
```powershell
# Standard run (products without images)
python manage.py populate_product_images

# With recommended settings
python manage.py populate_product_images --delay 1.5 --min-size 300
```

### Testing & Development
```powershell
# Test with 5 products
python manage.py populate_product_images --limit 5

# Test specific category
python manage.py populate_product_images --category Electronics --limit 10
```

### Production Usage
```powershell
# High-quality images, respectful rate limiting
python manage.py populate_product_images --min-size 400 --delay 2.0

# Force update all (reprocess existing)
python manage.py populate_product_images --force --delay 2.0
```

### Category-Specific Processing
```powershell
# Process only electronics
python manage.py populate_product_images --category Electronics

# Process only apparel with high quality
python manage.py populate_product_images --category Apparel --min-size 500
```

## Performance Optimization

### Recommended Delays

| Products | Delay (seconds) | Total Time (500 products) |
|----------|-----------------|---------------------------|
| < 50 | 1.0 | ~8 minutes |
| 50-200 | 1.5 | ~12 minutes |
| 200-500 | 2.0 | ~17 minutes |
| 500+ | 2.5 | ~21 minutes |

### Processing Strategy

**For Large Catalogs (500+ products):**
```powershell
# Break into batches by category
python manage.py populate_product_images --category Electronics --delay 2.0
# Wait 30 minutes
python manage.py populate_product_images --category Apparel --delay 2.0
# Wait 30 minutes
python manage.py populate_product_images --category Home --delay 2.0
```

**For Small Catalogs (<100 products):**
```powershell
# Single run with moderate delay
python manage.py populate_product_images --delay 1.5
```

## Troubleshooting

### No Images Found

**If many products return no images:**

1. **Lower quality threshold:**
   ```powershell
   python manage.py populate_product_images --min-size 150
   ```

2. **Check specific product:**
   ```powershell
   python manage.py populate_product_images --limit 1
   # Check console output for search strategies
   ```

3. **Manually verify search terms:**
   - Open Google Images
   - Search: "ProductName Category Subcategory"
   - If no results → product name might be too specific

### Rate Limiting Issues

**If Google blocks requests:**

1. **Increase delay:**
   ```powershell
   python manage.py populate_product_images --delay 3.0
   ```

2. **Process in smaller batches:**
   ```powershell
   python manage.py populate_product_images --limit 50 --delay 2.0
   # Wait 1 hour
   python manage.py populate_product_images --limit 50 --delay 2.0
   ```

3. **Use category filtering:**
   ```powershell
   # Process one category per day
   python manage.py populate_product_images --category Electronics
   ```

### Poor Quality Images

**If images are too small/blurry:**

1. **Increase minimum size:**
   ```powershell
   python manage.py populate_product_images --force --min-size 500
   ```

2. **Re-run for specific category:**
   ```powershell
   python manage.py populate_product_images --category Electronics --force --min-size 400
   ```

## Output Interpretation

### Success Message
```
[1/500] Processing: Samsung Galaxy S21
  Category: Electronics, Subcategory: Smartphones
    Strategy 1: "Samsung Galaxy S21 Electronics Smartphones"
      Found 15 candidates, using best: 800x600px
    ✓ Found image with strategy 1
  ✓ Updated: https://example.com/image.jpg...
```

### Fallback to Strategy 2
```
[2/500] Processing: Apple MacBook Pro
  Category: Electronics, Subcategory: Laptops
    Strategy 1: "Apple MacBook Pro Electronics Laptops"
      Found 3 candidates, all too small
    Strategy 2: "MacBook Pro Electronics"
      Found 8 candidates, using best: 1024x768px
    ✓ Found image with strategy 2
  ✓ Updated: https://example.com/image.jpg...
```

### No Image Found
```
[3/500] Processing: Generic USB Cable
  Category: Electronics, Subcategory: Accessories
    Strategy 1: "Generic USB Cable Electronics Accessories"
      Request error: No suitable images
    Strategy 2: "USB Cable Electronics"
      Found 2 candidates, all too small
    Strategy 3: "Electronics Accessories"
      Found 1 candidate, extreme aspect ratio
  ✗ No suitable image found with any strategy
```

## Best Practices

### ✅ Do's
- ✅ Start with `--limit 5` to test
- ✅ Use `--min-size 300` or higher for production
- ✅ Set `--delay 1.5` minimum for respectful scraping
- ✅ Process by category for better control
- ✅ Review results in admin after processing
- ✅ Manually upload images for key products

### ❌ Don'ts
- ❌ Don't use `--delay 0.5` or lower (risk blocking)
- ❌ Don't process 500+ products without batching
- ❌ Don't run multiple instances simultaneously
- ❌ Don't set `--min-size` too high (>600px) - many products won't find images
- ❌ Don't rely 100% on automated results - review and curate

## Integration with Admin

After running the command:

1. **Go to Django Admin → Products**
2. **Sort by "Image" column** (shows thumbnails)
3. **Products without images** → Manual upload or retry with lower `--min-size`
4. **Products with poor images** → Use `--force --min-size 400` for those categories
5. **Featured products** → Replace automated images with professional uploads

## Quick Decision Tree

```
Need to populate images?
│
├─ Small catalog (<100 products)
│  └─> python manage.py populate_product_images --delay 1.5 --min-size 300
│
├─ Medium catalog (100-500 products)  
│  └─> Process by category with delays
│      python manage.py populate_product_images --category X --delay 2.0
│
└─ Large catalog (500+ products)
   └─> Batch processing over multiple days
       python manage.py populate_product_images --limit 100 --delay 2.0
```

## Success Metrics

After running the command, check:

```
========================================
✓ Successfully updated: 450
✗ Failed: 50
========================================
```

**Good Results:** 80-90% success rate
**Need Review:** 50-70% success rate (lower min-size or manual uploads needed)
**Problem:** <50% success rate (check product names, categories, delays)
