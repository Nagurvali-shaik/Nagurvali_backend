from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.test import APIRequestFactory

from account.models import User
from catalog.models import Category, Product, ProductReview, ProductVariant
from catalog.serializers import ProductSerializer
from shop.models import Shop


class CatalogModelTests(TestCase):
    def test_category_str_returns_name(self):
        category = Category.objects.create(name="Gadgets", slug="gadgets")
        self.assertEqual(str(category), "Gadgets")

    def test_category_slug_is_auto_generated(self):
        category = Category.objects.create(name="Home Audio")
        self.assertEqual(category.slug, "home-audio")

    def test_product_sku_is_auto_generated(self):
        owner = User.objects.create_user(
            email="owner-sku@example.com",
            password="Pass123!",
            role="SHOP_OWNER",
            marketer_type="CREATOR",
        )
        shop = Shop.objects.create(name="SKU Shop", owner=owner)
        category = Category.objects.create(name="Accessories")
        product = Product.objects.create(
            name="Wireless Earbuds",
            description="Demo",
            shop=shop,
            price="79.99",
            category=category,
        )
        self.assertIsNotNone(product.sku)
        self.assertRegex(product.sku, r"^WIRELESSEARB-")


class ProductSerializerTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.owner = User.objects.create_user(
            email="shopowner@example.com",
            password="Pass123!",
            role="SHOP_OWNER",
            marketer_type="CREATOR",
        )
        self.shop = Shop.objects.create(name="My Shop", owner=self.owner)
        self.category = Category.objects.create(name="Phones", slug="phones")

    def test_create_product_with_variants_assigns_owner_shop(self):
        request = self.factory.post("/catalog/products/")
        request.user = self.owner
        serializer = ProductSerializer(
            data={
                "name": "Smartphone X",
                "description": "Flagship phone",
                "sku": "PHONE-X",
                "price": "999.99",
                "category_id": str(self.category.id),
                "variants": [
                    {
                        "variant_name": "Black / 128GB",
                        "price": "999.99",
                        "attributes": {"color": "black", "storage": "128GB"},
                    },
                    {
                        "variant_name": "Silver / 256GB",
                        "price": "1099.99",
                        "attributes": {"color": "silver", "storage": "256GB"},
                    },
                ],
            },
            context={"request": request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        product = serializer.save()

        self.assertEqual(product.shop_id, self.shop.id)
        self.assertEqual(product.category_id, self.category.id)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(ProductVariant.objects.filter(product=product).count(), 2)

    def test_create_product_without_variants_creates_default_variant(self):
        request = self.factory.post("/catalog/products/")
        request.user = self.owner
        serializer = ProductSerializer(
            data={
                "name": "No Variant Product",
                "description": "auto default variant",
                "price": "49.99",
                "category_id": str(self.category.id),
            },
            context={"request": request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        product = serializer.save()
        variants = ProductVariant.objects.filter(product=product)
        self.assertEqual(variants.count(), 1)
        self.assertEqual(variants.first().variant_name, "Default")


class ProductReviewAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email="owner-review@example.com",
            password="Pass123!",
            role="SHOP_OWNER",
            marketer_type="CREATOR",
        )
        self.user1 = User.objects.create_user(
            email="user1-review@example.com",
            password="Pass123!",
            role="CUSTOMER",
            marketer_type="CREATOR",
        )
        self.user2 = User.objects.create_user(
            email="user2-review@example.com",
            password="Pass123!",
            role="CUSTOMER",
            marketer_type="CREATOR",
        )
        self.shop = Shop.objects.create(name="Review Shop", owner=self.owner)
        self.category = Category.objects.create(name="Review Cat")
        self.product = Product.objects.create(
            name="Review Product",
            shop=self.shop,
            category=self.category,
            price="49.99",
        )

    def test_user_can_create_review(self):
        self.client.force_authenticate(self.user1)
        response = self.client.post(
            f"/catalog/products/{self.product.id}/reviews/",
            {"rating": 5, "title": "Great", "comment": "Loved it"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(ProductReview.objects.count(), 1)
        self.assertEqual(ProductReview.objects.first().user_id, self.user1.id)

    def test_user_cannot_review_same_product_twice(self):
        ProductReview.objects.create(product=self.product, user=self.user1, rating=4, title="Nice", comment="Good")
        self.client.force_authenticate(self.user1)
        response = self.client.post(
            f"/catalog/products/{self.product.id}/reviews/",
            {"rating": 5, "title": "Again", "comment": "Second review"},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.data)

    def test_only_owner_of_review_can_update(self):
        review = ProductReview.objects.create(product=self.product, user=self.user1, rating=4, title="Nice", comment="Good")
        self.client.force_authenticate(self.user2)
        response = self.client.patch(
            f"/catalog/reviews/{review.id}/",
            {"rating": 1, "comment": "Changed"},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.data)

    def test_product_serializer_returns_review_summary(self):
        ProductReview.objects.create(product=self.product, user=self.user1, rating=4, title="A", comment="B")
        ProductReview.objects.create(product=self.product, user=self.user2, rating=5, title="C", comment="D")
        request = APIRequestFactory().get("/catalog/products/")
        request.user = self.owner
        data = ProductSerializer(instance=self.product, context={"request": request}).data
        self.assertEqual(data["reviews_count"], 2)
        self.assertEqual(data["average_rating"], 4.5)
