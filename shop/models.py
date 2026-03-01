from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
import uuid
User = get_user_model()


class Theme(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    description = models.TextField(blank=True)
    preview_image = models.ImageField(upload_to="theme_previews/")

    version = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            base_slug = slugify(self.name) or f"theme-{uuid.uuid4().hex[:8]}"
            candidate = base_slug
            counter = 1
            while Theme.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Shop(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    owner = models.OneToOneField(
        "account.User",
        on_delete=models.CASCADE,
        related_name="owned_shop"
    )

    theme = models.ForeignKey(
        Theme,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shops"
    )
    marketers = models.ManyToManyField(
    User,
    blank=True,
    related_name="marketing_shops",
    limit_choices_to={"role": "MARKETER"}
)

    domain = models.CharField(max_length=255, unique=True, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class ShopThemeSettings(models.Model):
    shop = models.OneToOneField(Shop, on_delete=models.CASCADE, related_name='theme_settings')

    primary_color = models.CharField(max_length=7, default="#000000")
    secondary_color = models.CharField(max_length=7, default="#ffffff")

    logo = models.ImageField(upload_to="store_logos/", null=True, blank=True)
    banner_image = models.ImageField(upload_to="store_banners/", null=True, blank=True)

    font_family = models.CharField(max_length=100, default="Arial")
