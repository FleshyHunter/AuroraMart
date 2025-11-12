"""
Template examples for displaying product images in your storefront templates.

Use these code snippets to integrate product images into your ecommercemodule templates.
"""

# ============================================================================
# Example 1: Product List / Category View
# ============================================================================
"""
{% for product in products %}
<div class="card">
    <div class="card-img-top" style="height: 200px; overflow: hidden; background: #f8f9fa;">
        {% if product.get_image_url %}
            <img src="{{ product.get_image_url }}" 
                 alt="{{ product.name }}"
                 style="width: 100%; height: 100%; object-fit: cover;">
        {% else %}
            <div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #999;">
                <i class="bi bi-image" style="font-size: 3rem;"></i>
            </div>
        {% endif %}
    </div>
    <div class="card-body">
        <h5 class="card-title">{{ product.name }}</h5>
        <p class="card-text">${{ product.unit_price }}</p>
        <a href="{% url 'ecommercemodule:product_detail' product.pk %}" class="btn btn-primary">
            View Details
        </a>
    </div>
</div>
{% endfor %}
"""

# ============================================================================
# Example 2: Product Detail Page
# ============================================================================
"""
<div class="row">
    <div class="col-md-6">
        <!-- Large product image -->
        <div style="border: 1px solid #ddd; border-radius: 8px; padding: 20px; background: #fff;">
            {% if product.get_image_url %}
                <img src="{{ product.get_image_url }}" 
                     alt="{{ product.name }}"
                     class="img-fluid"
                     style="max-height: 500px; width: 100%; object-fit: contain;">
            {% else %}
                <div style="height: 500px; display: flex; align-items: center; justify-content: center; background: #f8f9fa;">
                    <div class="text-center text-muted">
                        <i class="bi bi-image" style="font-size: 5rem;"></i>
                        <p>No image available</p>
                    </div>
                </div>
            {% endif %}
        </div>
        
        <!-- Optional: Image source badge -->
        <div class="mt-2">
            {% if product.image %}
                <span class="badge bg-success">
                    <i class="bi bi-upload"></i> Uploaded Image
                </span>
            {% elif product.image_url %}
                <span class="badge bg-info">
                    <i class="bi bi-link-45deg"></i> External URL
                </span>
            {% endif %}
        </div>
    </div>
    
    <div class="col-md-6">
        <h1>{{ product.name }}</h1>
        <p class="text-muted">{{ product.sku }}</p>
        <h3 class="text-success">${{ product.unit_price }}</h3>
        <p>{{ product.description }}</p>
        <!-- Add to cart form here -->
    </div>
</div>
"""

# ============================================================================
# Example 3: Shopping Cart
# ============================================================================
"""
{% for item in cart_items %}
<div class="cart-item d-flex align-items-center mb-3 p-3 border rounded">
    <!-- Thumbnail -->
    <div style="width: 80px; height: 80px; flex-shrink: 0; margin-right: 15px;">
        {% if item.product.get_image_url %}
            <img src="{{ item.product.get_image_url }}" 
                 alt="{{ item.product.name }}"
                 style="width: 100%; height: 100%; object-fit: cover; border-radius: 4px;">
        {% else %}
            <div style="width: 100%; height: 100%; background: #f8f9fa; display: flex; align-items: center; justify-content: center; border-radius: 4px;">
                <i class="bi bi-box" style="font-size: 2rem; color: #999;"></i>
            </div>
        {% endif %}
    </div>
    
    <!-- Product info -->
    <div class="flex-grow-1">
        <h6>{{ item.product.name }}</h6>
        <p class="text-muted mb-0">${{ item.product.unit_price }} × {{ item.quantity }}</p>
    </div>
    
    <!-- Price -->
    <div class="fw-bold">
        ${{ item.line_total }}
    </div>
</div>
{% endfor %}
"""

# ============================================================================
# Example 4: Order Success / Order History
# ============================================================================
"""
{% for item in order.items.all %}
<tr>
    <td>
        <div class="d-flex align-items-center">
            <!-- Small thumbnail -->
            <div style="width: 50px; height: 50px; margin-right: 10px;">
                {% if item.product.get_image_url %}
                    <img src="{{ item.product.get_image_url }}" 
                         alt="{{ item.product.name }}"
                         style="width: 100%; height: 100%; object-fit: cover; border-radius: 4px;">
                {% else %}
                    <div style="width: 100%; height: 100%; background: #f8f9fa; display: flex; align-items: center; justify-content: center; border-radius: 4px;">
                        <i class="bi bi-box" style="font-size: 1.5rem; color: #999;"></i>
                    </div>
                {% endif %}
            </div>
            <span>{{ item.product.name }}</span>
        </div>
    </td>
    <td>{{ item.quantity }}</td>
    <td>${{ item.unit_price }}</td>
    <td>${{ item.line_total }}</td>
</tr>
{% endfor %}
"""

# ============================================================================
# Example 5: Responsive Grid Layout (Bootstrap 5)
# ============================================================================
"""
<div class="row g-4">
    {% for product in products %}
    <div class="col-12 col-sm-6 col-md-4 col-lg-3">
        <div class="card h-100 shadow-sm hover-shadow">
            <!-- Image with fixed aspect ratio -->
            <div class="position-relative" style="padding-top: 100%; overflow: hidden;">
                {% if product.get_image_url %}
                    <img src="{{ product.get_image_url }}" 
                         alt="{{ product.name }}"
                         class="position-absolute top-0 start-0 w-100 h-100"
                         style="object-fit: cover;">
                {% else %}
                    <div class="position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center bg-light">
                        <i class="bi bi-image text-muted" style="font-size: 3rem;"></i>
                    </div>
                {% endif %}
                
                <!-- Optional: Stock badge overlay -->
                {% if product.quantity_on_hand < 10 %}
                <span class="position-absolute top-0 end-0 m-2 badge bg-warning">
                    Low Stock
                </span>
                {% endif %}
            </div>
            
            <div class="card-body">
                <h6 class="card-title text-truncate">{{ product.name }}</h6>
                <div class="d-flex justify-content-between align-items-center">
                    <span class="fw-bold text-success">${{ product.unit_price }}</span>
                    {% if product.rating %}
                    <span class="text-warning">
                        <i class="bi bi-star-fill"></i> {{ product.rating }}
                    </span>
                    {% endif %}
                </div>
            </div>
            
            <div class="card-footer bg-transparent">
                <a href="{% url 'ecommercemodule:product_detail' product.pk %}" 
                   class="btn btn-primary btn-sm w-100">
                    View Details
                </a>
            </div>
        </div>
    </div>
    {% endfor %}
</div>

<style>
.hover-shadow {
    transition: box-shadow 0.3s ease;
}
.hover-shadow:hover {
    box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15) !important;
}
</style>
"""

# ============================================================================
# Example 6: Lazy Loading (Performance Optimization)
# ============================================================================
"""
<!-- Add loading="lazy" for images below the fold -->
<img src="{{ product.get_image_url }}" 
     alt="{{ product.name }}"
     loading="lazy"
     style="width: 100%; height: 200px; object-fit: cover;">
"""

# ============================================================================
# Example 7: With Fallback to Static Default Image
# ============================================================================
"""
{% load static %}

<img src="{% if product.get_image_url %}{{ product.get_image_url }}{% else %}{% static 'img/no-product-image.png' %}{% endif %}" 
     alt="{{ product.name }}"
     style="width: 100%; height: 200px; object-fit: cover;">
"""

# ============================================================================
# Example 8: Image Gallery Slider (Multiple Views)
# ============================================================================
"""
<!-- If you later add multiple images per product -->
<div id="productCarousel" class="carousel slide">
    <div class="carousel-inner">
        {% if product.get_image_url %}
        <div class="carousel-item active">
            <img src="{{ product.get_image_url }}" 
                 class="d-block w-100" 
                 alt="{{ product.name }}"
                 style="max-height: 500px; object-fit: contain;">
        </div>
        {% else %}
        <div class="carousel-item active">
            <div style="height: 500px; display: flex; align-items: center; justify-content: center; background: #f8f9fa;">
                <i class="bi bi-image text-muted" style="font-size: 5rem;"></i>
            </div>
        </div>
        {% endif %}
    </div>
</div>
"""

# ============================================================================
# Notes:
# ============================================================================
"""
1. Always use product.get_image_url property (not product.image or product.image_url directly)
   - This ensures uploaded images take priority over URLs

2. Add alt attributes for accessibility

3. Use object-fit: cover for thumbnails (fills space, may crop)
   Use object-fit: contain for detail views (shows full image, may have whitespace)

4. Consider lazy loading for performance on long product lists

5. Add loading states or skeleton screens while images load

6. For production, consider:
   - CDN for image delivery
   - Responsive images with srcset
   - WebP format with fallbacks
   - Image compression/optimization
"""
