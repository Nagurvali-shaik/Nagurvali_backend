from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from account.models import User
from shop.models import Shop, ShopThemeSettings, Theme


class ShopModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner-shop@example.com",
            password="Pass123!",
            role="SHOP_OWNER",
            marketer_type="CREATOR",
        )
        self.marketer = User.objects.create_user(
            email="marketer@example.com",
            password="Pass123!",
            role="MARKETER",
            marketer_type="CREATOR",
        )
        self.theme = Theme.objects.create(
            name="Modern",
            slug="modern",
            description="Modern layout",
            preview_image=SimpleUploadedFile(
                "preview.jpg", b"filecontent", content_type="image/jpeg"
            ),
            version="1.0.0",
            is_active=True,
        )

    def test_theme_str_returns_name(self):
        self.assertEqual(str(self.theme), "Modern")

    def test_theme_slug_is_auto_generated(self):
        theme = Theme.objects.create(
            name="Clean Commerce",
            description="Another theme",
            preview_image=SimpleUploadedFile(
                "preview2.jpg", b"filecontent", content_type="image/jpeg"
            ),
            version="1.0.1",
            is_active=True,
        )
        self.assertEqual(theme.slug, "clean-commerce")

    def test_shop_str_returns_name(self):
        shop = Shop.objects.create(
            name="Downtown Store",
            description="Main branch",
            owner=self.owner,
            theme=self.theme,
        )
        self.assertEqual(str(shop), "Downtown Store")

    def test_shop_can_assign_marketer(self):
        shop = Shop.objects.create(name="Growth Store", owner=self.owner, theme=self.theme)
        shop.marketers.add(self.marketer)

        self.assertEqual(shop.marketers.count(), 1)
        self.assertEqual(shop.marketers.first().id, self.marketer.id)

    def test_theme_settings_defaults(self):
        shop = Shop.objects.create(name="Styled Store", owner=self.owner, theme=self.theme)
        settings = ShopThemeSettings.objects.create(shop=shop)

        self.assertEqual(settings.primary_color, "#000000")
        self.assertEqual(settings.secondary_color, "#ffffff")
        self.assertEqual(settings.font_family, "Arial")
