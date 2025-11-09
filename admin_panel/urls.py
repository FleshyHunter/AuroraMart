from django.urls import path
from . import views

app_name = "admin_panel"

urlpatterns = [
    
    path('', views.dashboard, name='dashboard'),
    
    # Product management (existing)
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.product_add, name="product_add"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),

    # AI settings
    # path("ai-settings/", views.ai_settings, name="ai_settings"),

    # Customer management
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path('customers/<str:pk>/edit/', views.customer_edit, name='customer_edit'),

    # transaction management
    path("transaction/", views.transaction_list, name="transaction_list"),
    path("transaction/<int:pk>/", views.transaction_detail, name="transaction_detail"),
    
    
    path("inventory/", views.inventory_list, name="inventory_list"),
    
    path("order/", views.order_list, name="order_list"),
    path("checkout/", views.checkout_form, name="checkout_form"),
    path("incoming-stock/", views.incoming_stock, name="incoming_stock"),
    path("inventory-history/", views.inventory_history, name="inventory_history"),
    
]
