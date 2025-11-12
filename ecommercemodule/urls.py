from django.urls import path

from . import views

app_name = "ecommercemodule"

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/complete/", views.complete_profile, name="complete_profile"),
    path("profile/edit/", views.profile_update, name="profile_edit"),
    path("profile/deactivate/", views.deactivate_account, name="deactivate_account"),
    path("orders/", views.order_history, name="order_history"),
    path("password/reset/", views.PasswordResetRequestView.as_view(), name="password_reset"),
    path("password/reset/confirm/<uidb64>/<token>/", views.PasswordResetConfirmSlim.as_view(), name="password_reset_confirm"),
    path("password/change/", views.PasswordChangeSlim.as_view(), name="password_change"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/<slug:category_slug>/", views.product_list, name="category_products"),
    path(
        "categories/<slug:category_slug>/<slug:subcategory_slug>/",
        views.product_list,
        name="subcategory_products",
    ),
    path("search/", views.product_search, name="product_search"),
    path("product/<int:pk>/", views.product_detail, name="product_detail"),
    path("cart/", views.view_cart, name="view_cart"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/item/<int:cart_item_id>/update/", views.update_cart_item, name="update_cart_item"),
    path("cart/item/<int:cart_item_id>/remove/", views.remove_from_cart, name="remove_from_cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("order/success/<int:order_id>/", views.order_success, name="order_success"),
    path("order/<int:order_id>/", views.order_detail, name="order_detail"),
]