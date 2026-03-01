from django.urls import path
from .views import *

urlpatterns = [
    path('products/', CreateProductView.as_view(), name='create-product'),
    path('products/<uuid:pk>/', ProductDetailView.as_view(), name='product-detail'),
    path('products/<uuid:pk>/import/', ImportSupplierProductView.as_view(), name='import-supplier-product'),
    path('products/<uuid:pk>/reviews/', ProductReviewListCreateView.as_view(), name='product-review-list-create'),
    path('reviews/<uuid:pk>/', ProductReviewDetailView.as_view(), name='product-review-detail'),
    path('categories/', CreateCategoryView.as_view(), name='create-category'),
  
]
