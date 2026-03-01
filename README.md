# Shikela Backend
Shikela is a scalable multi-vendor e-commerce backend built with Django REST Framework.

This README shows how to integrate with all available backend features (all URLs exposed in `core/core/urls.py`).

**Base URL**
Use your API host, for example:
`http://127.0.0.1:8000/`

**Auth**
JWT Bearer tokens are required for most endpoints.

Example header:
`Authorization: Bearer <access_token>`

## Quick Start
1. Create and activate a virtual environment.
2. Install dependencies from `requirements.txt`.
3. Configure Django settings and run migrations.
4. Start the server and use the examples below.

## Authentication & Users
Base path: `/auth/`

**Register Customer**
Request fields:
- `email` (string, required)
- `password` (string, required)
- `first_name` (string, optional)
- `last_name` (string, optional)
- `phone_number` (string, optional)
- `merchant_id` (string, optional)
- `location` (string, optional)
- `badge` (string, optional)

```bash
curl -X POST http://127.0.0.1:8000/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "StrongPass123!",
    "first_name": "Test",
    "last_name": "User",
    "phone_number": "+251900000000"
  }'
```

**Login (JWT)**
```bash
curl -X POST http://127.0.0.1:8000/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "StrongPass123!"
  }'
```

**Refresh Token**
```bash
curl -X POST http://127.0.0.1:8000/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"<refresh_token>"}'
```

**Get/Update/Delete User**
```bash
curl -X GET http://127.0.0.1:8000/auth/user/1/ \
  -H "Authorization: Bearer <access_token>"
```

**Register Shop Owner**
Request fields:
- `first_name` (string, optional)
- `last_name` (string, optional)
- `email` (string, required)
- `password` (string, required)
- `merchant_id` (string, optional)
- `phone_number` (string, optional)
- `avatar` (file, optional)
- `license_document` (file, optional)

```bash
curl -X POST http://127.0.0.1:8000/auth/register-shop-owner/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner@example.com",
    "password": "StrongPass123!",
    "first_name": "Shop",
    "last_name": "Owner",
    "role": "SHOP_OWNER",
    "merchant_id": "your-santimpay-merchant-id"
  }'
```

**Register Supplier**
Request fields:
- `company_name` (string, optional)
- `email` (string, required)
- `password` (string, required)
- `merchant_id` (string, optional)
- `phone_number` (string, optional)
- `location` (string, optional)
- `avatar` (file, optional)
- `license_document` (file, optional)
- `policy` (file, optional)
- `bank_account` (string enum, optional)
- `bank_account_number` (string, optional)

```bash
curl -X POST http://127.0.0.1:8000/auth/register-supplier/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "supplier@example.com",
    "password": "StrongPass123!",
    "first_name": "Main",
    "last_name": "Supplier",
    "role": "SUPPLIER",
    "company_name": "Supplier Co"
  }'
```

**Register Courier**
Request fields:
- `company_name` (string, optional)
- `email` (string, required)
- `password` (string, required)
- `merchant_id` (string, optional)
- `phone_number` (string, optional)
- `location` (string, optional)
- `avatar` (file, optional)
- `license_document` (file, optional)
- `is_available` (boolean, optional)

```bash
curl -X POST http://127.0.0.1:8000/auth/register-courier/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "courier@example.com",
    "password": "StrongPass123!",
    "first_name": "Fast",
    "last_name": "Courier",
    "role": "COURIER",
    "is_available": true
  }'
```

**Register Marketer**
Request fields:
- `first_name` (string, optional)
- `last_name` (string, optional)
- `company_name` (string, optional)
- `avatar` (file, optional)
- `email` (string, required)
- `merchant_id` (string, optional)
- `phone_number` (string, optional)
- `bio` (string, optional)
- `base_price` (decimal, optional)
- `marketer_commission` (decimal, optional)
- `followers_count` (integer, optional)
- `instagram` (url, optional)
- `marketer_type` (enum: `CREATOR`|`AGENCY`, required)
- `pricing_type` (enum: `PER_POST`|`PER_CAMPAIGN`|`MONTHLY`, optional)
- `services` (enum string, optional)
- `team_size` (integer, optional)
- `tiktok` (url, optional)
- `website` (url, optional)
- `youtube` (url, optional)

```bash
curl -X POST http://127.0.0.1:8000/auth/register-marketer/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "marketer@example.com",
    "password": "StrongPass123!",
    "first_name": "Growth",
    "last_name": "Lead",
    "role": "MARKETER",
    "marketer_type": "CREATOR",
    "instagram": "https://instagram.com/creator",
    "marketer_commission": "10.00"
  }'
```

**Create Payment Method (Shop Owner)**
Request fields:
- `payment_type` (enum: `BANK`|`TELEBIRR`|`MPESA`, required)
- `account_number` (string, required if `payment_type=BANK`)
- `phone_number` (string, required if `payment_type=TELEBIRR` or `MPESA`)

```bash
curl -X POST http://127.0.0.1:8000/auth/create-payment-method/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_type": "TELEBIRR",
    "phone_number": "+251900000000"
  }'
```

## Shops & Themes
Base path: `/shops/`

**Create Shop**
Request fields:
- `name` (string, required)
- `description` (string, optional)
- `domain` (string, optional)
- `theme_id` (uuid, optional)
- `marketer_ids` (list of marketer UUIDs, optional)

```bash
curl -X POST http://127.0.0.1:8000/shops/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Store",
    "description": "Quality products",
    "domain": "mystore.example.com"
  }'
```

**List Shops**
```bash
curl -X GET http://127.0.0.1:8000/shops/ \
  -H "Authorization: Bearer <access_token>"
```

**Shop Detail**
```bash
curl -X GET http://127.0.0.1:8000/shops/shops/<shop_id>/ \
  -H "Authorization: Bearer <access_token>"
```

**Create Theme**
Request fields:
- `name` (string, required)
- `slug` (string, required)
- `description` (string, optional)
- `preview_image` (file, optional)
- `version` (string, required)
- `is_active` (boolean, optional)

```bash
curl -X POST http://127.0.0.1:8000/shops/themes/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Classic",
    "slug": "classic",
    "description": "Classic layout",
    "version": "1.0.0",
    "is_active": true
  }'
```

**Create Theme Settings**
Request fields:
- `primary_color` (string, optional)
- `secondary_color` (string, optional)
- `logo` (file, optional)
- `banner_image` (file, optional)
- `font_family` (string, optional)

```bash
curl -X POST http://127.0.0.1:8000/shops/theme-settings/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "shop": "<shop_id>",
    "primary_color": "#111111",
    "secondary_color": "#ffffff",
    "font_family": "Arial"
  }'
```

## Catalog
Base path: `/catalog/`

**Create Category**
Request fields:
- `name` (string, required)
- `description` (string, optional)
- `parent` (uuid, optional)
- `slug` (string, optional, auto-generated if omitted)

```bash
curl -X POST http://127.0.0.1:8000/catalog/categories/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Electronics",
    "description": "Devices and gadgets"
  }'
```

**Create Product**
Request fields:
- `name` (string, required)
- `description` (string, optional)
- `price` (decimal, required)
- `supplier_price` (decimal, optional)
- `minimum_wholesale_quantity` (integer, optional)
- `shop_owner_price` (decimal, optional)
- `category_id` (uuid, optional)
- `is_active` (boolean, optional)
- `weight` (float, optional)
- `dimensions` (json, optional)
- `tags` (list of strings, optional)
- `supplier_id` (uuid, optional)
- `variants` (list, optional)
- `media` (list, optional)
- `stock` (integer >= 0, optional) if provided, sets default stock for variants without stock.
  If no variants are provided, a `Default` variant is created with this stock (or `1` if omitted).

`variants` item fields:
- `variant_name` (string, required)
- `price` (decimal, optional)
- `attributes` (json, optional)
- `stock` (integer, optional)

`media` item fields:
- `media_type` (enum: `IMAGE`|`VIDEO`|`DOCUMENT`, required)
- `file` (file path or upload, required)
- `caption` (string, optional)
- `is_primary` (boolean, optional)
- `order` (integer, optional)

```bash
curl -X POST http://127.0.0.1:8000/catalog/products/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Wireless Headphones",
    "description": "Noise cancelling",
    "price": "129.99",
    "category": "<category_id>",
    "is_active": true,
    "tags": ["audio","wireless"]
  }'
```

**Product Detail**
```bash
curl -X GET http://127.0.0.1:8000/catalog/products/<product_id>/ \
  -H "Authorization: Bearer <access_token>"
```

**Import Supplier Product to Shop**
```bash
curl -X POST http://127.0.0.1:8000/catalog/products/<supplier_product_id>/import/ \
  -H "Authorization: Bearer <access_token>"
```

**Create Review**
Request fields:
- `rating` (integer 1-5, required)
- `title` (string, optional)
- `comment` (string, optional)

```bash
curl -X POST http://127.0.0.1:8000/catalog/products/<product_id>/reviews/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "rating": 5,
    "title": "Great",
    "comment": "Loved it!"
  }'
```

**Update/Delete Review**
```bash
curl -X PATCH http://127.0.0.1:8000/catalog/reviews/<review_id>/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"comment":"Updated review"}'
```

## Orders & Cart
Base path: `/order/`

**Add to Cart**
Request fields:
- `shop_id` (uuid, required)
- `product_id` (uuid, required)
- `variant_id` (uuid, optional)
- `marketer_contract_id` (uuid, optional)
- `quantity` (integer >= 1, required)

```bash
curl -X POST http://127.0.0.1:8000/order/cart/add/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "<shop_id>",
    "product_id": "<product_id>",
    "variant_id": "<variant_id>",
    "quantity": 2
  }'
```

**List Cart Items**
```bash
curl -X GET http://127.0.0.1:8000/order/cart/items/ \
  -H "Authorization: Bearer <access_token>"
```

**Checkout Cart**
Request fields:
- `delivery_address` (string, required)
- `payment_method` (string, required)
- `delivery_method` (enum: `courier`|`seller`, optional, default `courier`)

```bash
curl -X POST http://127.0.0.1:8000/order/cart/checkout/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "delivery_address": "123 Main St",
    "payment_method": "santimpay",
    "delivery_method": "courier"
  }'
```

**Buy Now (Create Order)**
Request fields:
- `shop_id` (uuid, required)
- `product_id` (uuid, required)
- `variant_id` (uuid, optional)
- `marketer_contract_id` (uuid, optional)
- `quantity` (integer, optional, default 1)
- `delivery_address` (string, required)
- `payment_method` (string, required)
- `delivery_method` (enum: `courier`|`seller`, optional, default `courier`)

```bash
curl -X POST http://127.0.0.1:8000/order/create/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "<shop_id>",
    "product_id": "<product_id>",
    "variant_id": "<variant_id>",
    "quantity": 1,
    "delivery_address": "123 Main St",
    "payment_method": "santimpay",
    "delivery_method": "seller"
  }'
```

**List User Orders**
```bash
curl -X GET http://127.0.0.1:8000/order/orders/ \
  -H "Authorization: Bearer <access_token>"
```

**Shop Owner: Update Delivery Method**
`PATCH /order/orders/<order_id>/delivery-method/`

Request fields:
- `delivery_method` (enum: `courier`|`seller`, required)

Notes:
- Only the shop owner of that order can update it.
- It cannot be changed after shipment creation or terminal statuses.

Example:
```bash
curl -X PATCH http://127.0.0.1:8000/order/orders/<order_id>/delivery-method/ \
  -H "Authorization: Bearer <shop_owner_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "delivery_method": "seller"
  }'
```

## Payments (SantimPay)
Base path: `/payment/`

**Required Settings**
Set these in Django `settings.py` or environment variables:
`SANTIMPAY_MERCHANT_ID`, `SANTIMPAY_PRIVATE_KEY`, `SANTIMPAY_TEST_BED`,
`SANTIMPAY_SUCCESS_REDIRECT_URL`, `SANTIMPAY_FAILURE_REDIRECT_URL`,
`SANTIMPAY_NOTIFY_URL`

**Direct Payment**
Request fields:
- `order_id` (uuid, required)
- `payment_method` (string, required)
- `phone_number` (string, required)
- `notify_url` (url, optional)

```bash
curl -X POST http://127.0.0.1:8000/payment/direct/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "<order_id>",
    "payment_method": "TELEBIRR",
    "phone_number": "+251900000000",
    "notify_url": "https://example.com/webhook"
  }'
```

**Webhook (SantimPay calls this)**
```bash
curl -X POST http://127.0.0.1:8000/payment/webhook/santimpay/ \
  -H "Content-Type: application/json" \
  -d '{"id":"<transaction_id>"}'
```

**Request Payout**
Request fields:
- `confirm` (boolean, optional, default true)

```bash
curl -X POST http://127.0.0.1:8000/payment/payouts/request/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Payout History**
```bash
curl -X GET http://127.0.0.1:8000/payment/payouts/history/ \
  -H "Authorization: Bearer <access_token>"
```

**Request Refund**
Request fields:
- `payment_id` (uuid, required)
- `amount` (decimal, required)
- `reason` (string, optional)

```bash
curl -X POST http://127.0.0.1:8000/payment/refunds/request/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "payment": "<payment_id>",
    "amount": "10.00",
    "reason": "Customer returned item"
  }'
```

**Approve Refund (Admin)**
```bash
curl -X POST http://127.0.0.1:8000/payment/refunds/<refund_id>/approve/ \
  -H "Authorization: Bearer <admin_access_token>"
```

**Execute Refund (Admin)**
```bash
curl -X POST http://127.0.0.1:8000/payment/refunds/<refund_id>/execute/ \
  -H "Authorization: Bearer <admin_access_token>"
```

## Logistics (Courier)
Base path: `/logistics/`

Shipment records are created automatically after successful payment webhook sync only for orders with `delivery_method = courier`.
Orders with `delivery_method = seller` are fulfilled by the seller and do not create courier shipments.

**Courier Webhook**
Endpoint used by courier partner systems to update shipment tracking state.

```bash
curl -X POST http://127.0.0.1:8000/logistics/webhook/hudhud/ \
  -H "Content-Type: application/json" \
  -d '{
    "tracking_id": "HD12345",
    "status": "IN_TRANSIT"
  }'
```

Supported status inputs include:
- `CREATED`
- `PICKED_UP`
- `IN_TRANSIT`
- `OUT_FOR_DELIVERY`
- `DELIVERED`
- `FAILED`
- `CANCELLED`

Order status mapping:
- `PICKED_UP` -> `confirmed`
- `IN_TRANSIT` -> `processing`
- `OUT_FOR_DELIVERY` -> `shipped`
- `DELIVERED` -> `delivered`
- `FAILED` / `CANCELLED` -> `cancelled` (if not delivered)

**Shipment Detail**
```bash
curl -X GET http://127.0.0.1:8000/logistics/shipments/<shipment_id>/ \
  -H "Authorization: Bearer <access_token>"
```

## Suppliers Portal
Base path: `/supliers/`

**Supplier Dashboard**
```bash
curl -X GET http://127.0.0.1:8000/supliers/dashboard/ \
  -H "Authorization: Bearer <access_token>"
```

**List/Create Supplier Products**
Request fields (create):
- `name` (string, required)
- `description` (string, optional)
- `price` (decimal, required)
- `supplier_price` (decimal, optional)
- `minimum_wholesale_quantity` (integer, optional)
- `shop_owner_price` (decimal, optional)
- `category_id` (uuid, optional)
- `is_active` (boolean, optional)
- `weight` (float, optional)
- `dimensions` (json, optional)
- `tags` (list of strings, optional)
- `variants` (list, optional)
- `media` (list, optional)
- `stock` (integer >= 0, optional) if provided, sets default stock for variants without stock.
  If no variants are provided, a `Default` variant is created with this stock (or `1` if omitted).

```bash
curl -X GET http://127.0.0.1:8000/supliers/products/ \
  -H "Authorization: Bearer <access_token>"
```

**Supplier Product Detail**
```bash
curl -X GET http://127.0.0.1:8000/supliers/products/<product_id>/ \
  -H "Authorization: Bearer <access_token>"
```

**Add Variant to Supplier Product**
Request fields:
- `variant_name` (string, required)
- `price` (decimal, optional)
- `attributes` (json, optional)
- `stock` (integer, required)

```bash
curl -X POST http://127.0.0.1:8000/supliers/products/<product_id>/variants/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "variant_name": "Red / Large",
    "price": "39.99",
    "attributes": {"color":"red","size":"L"},
    "stock": 10
  }'
```

**Add Media to Supplier Product**
Request fields:
- `media_type` (enum: `IMAGE`|`VIDEO`|`DOCUMENT`, required)
- `file` (file path or upload, required)
- `caption` (string, optional)
- `is_primary` (boolean, optional)
- `order` (integer, optional)

```bash
curl -X POST http://127.0.0.1:8000/supliers/products/<product_id>/media/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "media_type": "IMAGE",
    "file": "products/media/example.jpg",
    "caption": "Front view",
    "is_primary": true,
    "order": 1
  }'
```

**Update Variant Stock**
Request fields:
- `stock` (integer >= 0, required)

```bash
curl -X PATCH http://127.0.0.1:8000/supliers/variants/<variant_id>/stock/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"stock": 25}'
```

**Low Stock Alerts**
```bash
curl -X GET "http://127.0.0.1:8000/supliers/alerts/low-stock/?threshold=5" \
  -H "Authorization: Bearer <access_token>"
```

## Inventory
Inventory models and services exist, but no API endpoints are currently exposed (`core/inventory/urls.py` is empty).

## Notifications (FCM + In-App)
Base path: `/api/notifications/`

### Configuration
Set these in environment:
- `FCM_PROJECT_ID`
- `FCM_SERVICE_ACCOUNT_FILE` (path to Firebase service account JSON) or `FCM_SERVICE_ACCOUNT_JSON` (raw JSON string)

Install dependency:
`firebase-admin`

### Device Token APIs
**Register or update token (JWT required)**
`POST /api/notifications/device-token/`

Request fields:
- `token` (string, required, globally unique)
- `device_type` (enum: `web` | `android`, required)

**Deactivate token(s) (JWT required)**
`DELETE /api/notifications/device-token/`

Request fields:
- `token` (string, optional). If omitted, all active tokens of current user are deactivated.

### Notification Read APIs
**List notifications (paginated)**
`GET /api/notifications/`

**Mark one read**
`PATCH /api/notifications/{id}/read/`

**Mark all read**
`POST /api/notifications/mark-all-read/`

### Trigger Events Implemented
- Customer:
  - `payment_success`
  - `order_shipped`
  - `order_delivered`
- Shop Owner:
  - `new_order`
  - `payment_confirmed`
- Supplier:
  - `product_sold`
- Marketer:
  - `commission_created`
  - `commission_approved`

### Payload Standard
All notifications include payload with:
- `type`
- `entity_id`
- `entity_type` (`order` or `commission`)

Optional:
- `order_id`
- `commission_id`
- `product_id`

## Marketer System
Base path: `/marketer/`

### New Features Added
- Contract-based marketer relationships with shop owners.
- Product-scoped contracts (marketers can only earn on assigned products).
- Commission lifecycle: `PENDING` on payment, `APPROVED` on delivery.
- Marketer dashboard with earnings, pending commissions, orders influenced, units sold, active contracts.
- Shop owner control to activate, pause, resume, or end contracts.
- Order/cart support for `marketer_contract_id` to attribute sales.

### How It Works (Flow)
1. **Create contract**: shop owner or marketer creates a contract for a shop + marketer + product list.
2. **Activate contract**: shop owner activates it (only active contracts earn).
3. **Customer purchase**: frontend sends `marketer_contract_id` when adding to cart or buying now.
4. **Payment confirmed**: when order status becomes `PAID`, commission rows are created as `PENDING`.
5. **Delivery confirmed**: when order status becomes `DELIVERED`, commissions become `APPROVED`.
6. **Dashboards**: marketers and shop owners see totals, pending, and performance.

### Contracts
**Create Contract**
Request fields:
- `shop_id` (uuid, required)
- `marketer_id` (uuid, required)
- `commission_rate` (decimal percent, optional)
- `start_date` (date, optional)
- `end_date` (date, optional)
- `product_ids` (list of product UUIDs, optional)

```bash
curl -X POST http://127.0.0.1:8000/marketer/contracts/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "<shop_id>",
    "marketer_id": "<marketer_id>",
    "commission_rate": "10.00",
    "product_ids": ["<product_id_1>", "<product_id_2>"]
  }'
```

**Update Contract (dates, rate, products)**
```bash
curl -X PATCH http://127.0.0.1:8000/marketer/contracts/<contract_id>/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "commission_rate": "12.50",
    "product_ids": ["<product_id_1>"]
  }'
```

**Contract Status Actions (Shop Owner)**
```bash
curl -X POST http://127.0.0.1:8000/marketer/contracts/<contract_id>/activate/ \
  -H "Authorization: Bearer <access_token>"

curl -X POST http://127.0.0.1:8000/marketer/contracts/<contract_id>/pause/ \
  -H "Authorization: Bearer <access_token>"

curl -X POST http://127.0.0.1:8000/marketer/contracts/<contract_id>/resume/ \
  -H "Authorization: Bearer <access_token>"

curl -X POST http://127.0.0.1:8000/marketer/contracts/<contract_id>/end/ \
  -H "Authorization: Bearer <access_token>"
```

### Commissions
**List Commissions**
```bash
curl -X GET http://127.0.0.1:8000/marketer/commissions/ \
  -H "Authorization: Bearer <access_token>"
```

Filter by status:
`/marketer/commissions/?status=pending` or `approved`.

### Dashboard
**Marketer/Shop Owner Dashboard**
```bash
curl -X GET http://127.0.0.1:8000/marketer/dashboard/ \
  -H "Authorization: Bearer <access_token>"
```

### Commission Flow Summary
- Contract status must be `ACTIVE`.
- Commissions are created when payment is confirmed (order status becomes `PAID`).
- Commissions are approved when order status becomes `DELIVERED`.
- Marketers only earn on products listed in the contract.

## Notes
Some behavior depends on serializers and model constraints in the app code.
If you want examples tailored to your exact serializers or required fields, tell me which app to refine.

## Frontend Integration Quick Guide
This section shows a minimal, practical flow for a web or mobile frontend.

**1) Auth**
1. Register a user (or role-specific endpoint).
2. Login to get `access` and `refresh`.
3. Store `access` in memory and refresh when it expires.

Example login:
```bash
curl -X POST http://127.0.0.1:8000/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"StrongPass123!"}'
```

Attach JWT:
`Authorization: Bearer <access_token>`

**2) Core Marketplace Flow**
1. Shop owner creates a shop.
2. Supplier creates products (in `/supliers/`).
3. Shop owner imports supplier product into their shop (`/catalog/products/<id>/import/`).
4. Customer adds to cart and checks out to create an order.
5. Customer initiates payment (`/payment/direct/`).
6. SantimPay webhook updates order/payment status and creates shipment for orders using `delivery_method = courier`.
7. Courier webhook updates shipment and order delivery status (`/logistics/webhook/<courier>/`).

**3) Basic Frontend Data Screens**
Use these endpoints as your first screens:
1. Shop list: `GET /shops/`
2. Product list: `GET /catalog/products/` (your frontend can filter client-side)
3. Product detail: `GET /catalog/products/<id>/`
4. Cart: `GET /order/cart/items/`
5. Orders: `GET /order/orders/`

**4) Typical Customer Checkout Example**
```bash
# add item
curl -X POST http://127.0.0.1:8000/order/cart/add/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "<shop_id>",
    "product_id": "<product_id>",
    "variant_id": "<variant_id>",
    "quantity": 1
  }'

# checkout cart
curl -X POST http://127.0.0.1:8000/order/cart/checkout/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "delivery_address": "123 Main St",
    "payment_method": "santimpay",
    "delivery_method": "courier"
  }'

# pay order
curl -X POST http://127.0.0.1:8000/payment/direct/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "<order_id>",
    "payment_method": "TELEBIRR",
    "phone_number": "+251900000000",
    "notify_url": "https://example.com/webhook"
  }'
```

**5) Admin/Backoffice Pages**
1. Refund approvals: `POST /payment/refunds/<id>/approve/`
2. Refund execute: `POST /payment/refunds/<id>/execute/`
3. Payout history: `GET /payment/payouts/history/`


