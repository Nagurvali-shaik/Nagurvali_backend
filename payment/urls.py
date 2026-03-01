# payments/urls.py
from django.urls import path
from .views import *

urlpatterns = [
    path("direct/", DirectPaymentView.as_view(), name="direct-payment"),
    path("webhook/santimpay/", SantimPayWebhookView.as_view(), name="santimpay-webhook"),
    path("payouts/request/", PayoutRequestView.as_view(), name="payout-request"),
    path("payouts/history/", PayoutHistoryView.as_view(), name="payout-history"),
    # Refunds
    path("refunds/", RefundListCreateView.as_view(), name="refund-list-create"),
    path("refunds/request/", RefundListCreateView.as_view(), name="refund-request"),
    path("refunds/<uuid:pk>/approve/", RefundApproveView.as_view(), name="refund-approve"),
    path("refunds/<uuid:pk>/execute/", RefundExecuteView.as_view(), name="refund-execute"),
]
