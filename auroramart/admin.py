from django.contrib import admin
from .models import Category, SubCategory, Product, Customer


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'slug')
    list_filter = ('category',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'category__name')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'thumbnail_preview', 'sku', 'name', 'category', 'subcategory', 
        'unit_price', 'quantity_on_hand', 'rating', 'is_active'
    )
    list_filter = ('category', 'subcategory', 'is_active')
    search_fields = ('name', 'sku', 'description')
    ordering = ('name',)
    list_editable = ('is_active', 'unit_price', 'quantity_on_hand')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('sku', 'name', 'description')
        }),
        ('Categorization', {
            'fields': ('category', 'subcategory')
        }),
        ('Inventory & Pricing', {
            'fields': ('quantity_on_hand', 'reorder_quantity', 'unit_price', 'rating')
        }),
        ('Images', {
            'fields': ('image', 'image_preview', 'image_url'),
            'description': 'Upload an image file OR provide an external URL. Uploaded images take priority.'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    readonly_fields = ('image_preview',)
    
    def thumbnail_preview(self, obj):
        """Display thumbnail in list view"""
        from django.utils.html import format_html
        
        image_url = obj.get_image_url
        if image_url:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />',
                image_url
            )
        return format_html('<span style="color: #999;">No image</span>')
    
    thumbnail_preview.short_description = 'Image'
    
    def image_preview(self, obj):
        """Display larger preview in form view"""
        from django.utils.html import format_html
        
        image_url = obj.get_image_url
        if image_url:
            return format_html(
                '<div style="margin: 10px 0;">'
                '<img src="{}" style="max-width: 300px; max-height: 300px; border: 1px solid #ddd; border-radius: 4px;" />'
                '<p style="color: #666; font-size: 12px; margin-top: 5px;">Current image preview</p>'
                '</div>',
                image_url
            )
        return format_html('<p style="color: #999;">No image available</p>')
    
    image_preview.short_description = 'Current Image'


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'age', 'gender', 'employment_status', 'occupation', 'preferred_category')
    list_filter = ('gender', 'employment_status', 'has_children', 'preferred_category')
    search_fields = ('user__username', 'user__email', 'occupation')
    raw_id_fields = ('user',)
