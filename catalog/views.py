from rest_framework import permissions
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from .models import *
from .serializers import *
# Create your views here.

class CreateProductView(ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
class ProductDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class CreateCategoryView(ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Category.objects.all()
    serializer_class = CatagorySerializer


class ImportSupplierProductView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _unique_name(base_name: str) -> str:
        candidate = base_name
        suffix = 1
        while Product.objects.filter(name=candidate).exists():
            candidate = f"{base_name} ({suffix})"
            suffix += 1
        return candidate

    def post(self, request, pk):
        user = request.user
        if user.role != "SHOP_OWNER":
            return Response({"detail": "Only shop owners can import supplier products."}, status=status.HTTP_403_FORBIDDEN)

        shop = getattr(user, "owned_shop", None)
        if not shop:
            return Response({"detail": "Create a shop before importing products."}, status=status.HTTP_400_BAD_REQUEST)

        source = Product.objects.filter(pk=pk).prefetch_related("variants", "media").first()
        if not source:
            return Response({"detail": "Supplier product not found."}, status=status.HTTP_404_NOT_FOUND)
        if not source.supplier:
            return Response({"detail": "Only supplier products can be imported."}, status=status.HTTP_400_BAD_REQUEST)

        imported = Product.objects.create(
            name=self._unique_name(source.name),
            description=source.description,
            shop=shop,
            supplier=source.supplier,
            price=source.price,
            supplier_price=source.supplier_price,
            minimum_wholesale_quantity=source.minimum_wholesale_quantity,
            shop_owner_price=source.shop_owner_price,
            category=source.category,
            is_active=source.is_active,
            weight=source.weight,
            dimensions=source.dimensions,
            tags=source.tags,
        )

        for variant in source.variants.all():
            ProductVariant.objects.create(
                product=imported,
                variant_name=variant.variant_name,
                price=variant.price,
                attributes=variant.attributes,
                stock=variant.stock,
            )

        for media in source.media.all():
            ProductMedia.objects.create(
                product=imported,
                media_type=media.media_type,
                file=media.file,
                caption=media.caption,
                is_primary=media.is_primary,
                order=media.order,
            )

        return Response(
            {
                "message": "Product imported successfully.",
                "source_product_id": str(source.id),
                "imported_product_id": str(imported.id),
                "shop_id": str(shop.id),
            },
            status=status.HTTP_201_CREATED,
        )


class ProductReviewListCreateView(ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductReviewSerializer

    def get_queryset(self):
        product_id = self.kwargs["pk"]
        return ProductReview.objects.filter(product_id=product_id).select_related("user", "product").order_by("-created_at")

    def perform_create(self, serializer):
        product = Product.objects.filter(id=self.kwargs["pk"]).first()
        if not product:
            raise PermissionDenied("Product not found.")
        if ProductReview.objects.filter(product=product, user=self.request.user).exists():
            raise PermissionDenied("You have already reviewed this product.")
        serializer.save(product=product, user=self.request.user)


class ProductReviewDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductReviewSerializer
    queryset = ProductReview.objects.select_related("user", "product").all()

    def perform_update(self, serializer):
        if serializer.instance.user_id != self.request.user.id:
            raise PermissionDenied("You can only update your own review.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user_id != self.request.user.id:
            raise PermissionDenied("You can only delete your own review.")
        instance.delete()
