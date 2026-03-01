import uuid
import base64
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    MERCHANT_ID_PREFIX = "enc:"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    ROLE_CHOICES = [
        ("CUSTOMER", "Customer"),
        ("SHOP_OWNER", "Shop Owner"),
        ("SUPPLIER", "Supplier"),
        ("COURIER", "Courier"),
        ("MARKETER", "Marketer"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="CUSTOMER")

    # Basic fields
    email = models.EmailField(unique=True)
    merchant_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    password = models.CharField(max_length=128)

    # Verification / badges
    is_verified = models.BooleanField(default=False)
    license_document = models.FileField(upload_to="licenses/", blank=True, null=True)
    badge = models.CharField(
        max_length=50,
        choices=[("none","None"),("verified","Verified"),("vip","VIP"),("trusted","Trusted")],
        default="none"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional avatar
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    
    # Auth
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    #suppliers fields
    location = models.CharField(max_length=255, blank=True, null=True)

    company_name = models.CharField(max_length=30, blank=True, null=True)
    policy = models.FileField(upload_to="policy/", blank=True, null=True)

    #bank account fields
    BANK_ACCOUNT_CHOICES = [
    ("COMMERCIAL_BANK_OF_ETHIOPIA", "Commercial Bank of Ethiopia"),
    ("COOPERATIVE_BANK_OF_OROMIA", "Cooperative Bank of Oromia"),
    ("AWASH_INTERNATIONAL_BANK", "Awash International Bank"),
    ("BANK_OF_ABYSSINIA", "Bank of Abyssinia"),
    ("DASHEN_BANK", "Dashen Bank"),
    ("ENAT_BANK", "Enat Bank"),
    ("BUNNA_INTERNATIONAL_BANK", "Bunna International Bank"),
    ("NIB_INTERNATIONAL_BANK", "Nib International Bank"),
    ("ADDIS_INTERNATIONAL_BANK", "Addis International Bank"),
    ("AMHARA_BANK", "Amhara Bank"),
    ("LION_INTERNATIONAL_BANK", "Lion International Bank"),
    ("DEVELOPMENT_BANK_OF_ETHIOPIA", "Development Bank of Ethiopia"),
    ("SIDAMA_BANK", "Sidama Bank"),
    ("SIINQEE_BANK", "Siinqee Bank"),
    ("TSDEY_BANK", "Tsedey Bank"),
    ("TSHAY_BANK", "Tsehay Bank"),
    ("HIBRET_BANK", "Hibret Bank"),
    ("HIJRA_BANK", "Hijra Bank"),
    ("RAMMIS_BANK", "Rammis Bank"),
    ("GADAA_BANK", "Gadaa Bank"),
    ("NATIONAL_BANK_OF_ETHIOPIA", "National Bank of Ethiopia"),
    ]
    bank_account = models.CharField(
    max_length=50,
    blank=True,
    null=True,
    choices=BANK_ACCOUNT_CHOICES
    )
    bank_account_number = models.CharField(max_length=50, blank=True, null=True)
    #couiers fields
    is_available = models.BooleanField(default=True)
    #marketer fields 
     #marketer fields
    marketer_type = models.CharField(
        max_length=20,
        choices=[
            ("CREATOR", "Content Creator"),
            ("AGENCY", "Marketing Agency"),
        ]
    )
    bio = models.TextField(blank=True)
    # Social proof (important for creators)
    instagram = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)
    youtube = models.URLField(blank=True)

    followers_count = models.PositiveIntegerField(default=0)

    # Agency-specific
    team_size = models.PositiveIntegerField(null=True, blank=True)
    website = models.URLField(blank=True)

    SERVICES_CHOICES = [
        ("ADS", "Paid Ads"),
        ("CONTENT", "Content Creation"),
        ("INFLUENCER", "Influencer Promotion"),
        ("SEO", "SEO Marketing"),
        ("BRANDING", "Branding"),
    ]

    services = models.CharField(max_length=255, default="ADS", blank=True, choices=SERVICES_CHOICES)  # Comma-separated list of services offered

    # Pricing model
    pricing_type = models.CharField(
        max_length=20,
        choices=[
            ("PER_POST", "Per Post"),
            ("PER_CAMPAIGN", "Per Campaign"),
            ("MONTHLY", "Monthly Contract"),
        ],
        default="PER_CAMPAIGN"
    )
    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    marketer_commission = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
        help_text="Commission percent for marketer, e.g. 10.00 means 10%",
    )

    # Trust system
    rating = models.FloatField(default=0.0)
    total_jobs = models.PositiveIntegerField(default=0)


    objects = UserManager()

    USERNAME_FIELD = "email"
    # REQUIRED_FIELDS = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @classmethod
    def encode_merchant_id(cls, value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return ""
        if raw.startswith(cls.MERCHANT_ID_PREFIX):
            return raw
        encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
        return f"{cls.MERCHANT_ID_PREFIX}{encoded}"

    @classmethod
    def decode_merchant_id(cls, value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return ""
        if not raw.startswith(cls.MERCHANT_ID_PREFIX):
            return raw
        payload = raw[len(cls.MERCHANT_ID_PREFIX):]
        try:
            return base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
        except Exception:
            return ""

    def get_decoded_merchant_id(self) -> str:
        return self.decode_merchant_id(self.merchant_id or "")

    def save(self, *args, **kwargs):
        if self.merchant_id:
            self.merchant_id = self.encode_merchant_id(self.merchant_id)
        super().save(*args, **kwargs)


class PaymentMethod(models.Model):
    PAYMENT_CHOICES = [
        ("BANK", "Bank"),
        ("TELEBIRR", "Telebirr"),
        ("MPESA", "M-Pesa"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop_owner = models.ForeignKey(
        'account.User',  # assuming shop_owner is a User with role=SHOP_OWNER
        on_delete=models.CASCADE,
        related_name="payment_methods"
    )
    payment_type = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
   
    # Conditional fields
    account_number = models.CharField(max_length=50, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("shop_owner", "payment_type")  # each owner can have 1 of each type

    def __str__(self):
        return f"{self.shop_owner.full_name} - {self.payment_type}"

    # Optional helper method
    def get_identifier(self):
        """
        Returns the correct identifier based on the payment type
        """
        if self.payment_type == "BANK":
            return self.account_number
        else:
            return self.phone_number
