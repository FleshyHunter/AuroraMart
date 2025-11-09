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
    list_display = ('sku', 'name', 'category', 'subcategory', 'unit_price', 'quantity_on_hand', 'rating', 'is_active')
    list_filter = ('category', 'subcategory', 'is_active')
    search_fields = ('name', 'sku', 'description')
    ordering = ('name',)
    list_editable = ('is_active', 'unit_price', 'quantity_on_hand')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'age', 'gender', 'employment_status', 'occupation', 'preferred_category')
    list_filter = ('gender', 'employment_status', 'has_children', 'preferred_category')
    search_fields = ('user__username', 'user__email', 'occupation')
    raw_id_fields = ('user',)
