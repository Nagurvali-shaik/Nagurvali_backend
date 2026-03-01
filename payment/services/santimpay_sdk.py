import time
from typing import Any, Dict, Optional

import jwt
import requests


PRODUCTION_BASE_URL = "https://services.santimpay.com/api/v1/gateway"
TEST_BASE_URL = "https://testnet.santimpay.com/api/v1/gateway"


class SantimpaySDK:
    def __init__(self, merchant_id: str, private_key: str, test_bed: bool = False) -> None:
        self.private_key = private_key
        self.merchant_id = merchant_id
        self.base_url = TEST_BASE_URL if test_bed else PRODUCTION_BASE_URL

    def _sign_es256(self, payload: Dict[str, Any]) -> str:
        # Keep token structure compatible with the Node SDK.
        return jwt.encode(payload, self.private_key, algorithm="ES256")

    def generate_signed_token_for_initiate_payment(self, amount: float, payment_reason: str) -> str:
        payload = {
            "amount": amount,
            "paymentReason": payment_reason,
            "merchantId": self.merchant_id,
            "generated": int(time.time()),
        }
        return self._sign_es256(payload)

    def generate_signed_token_for_direct_payment(
        self, amount: float, payment_reason: str, payment_method: str, phone_number: str
    ) -> str:
        payload = {
            "amount": amount,
            "paymentReason": payment_reason,
            "paymentMethod": payment_method,
            "phoneNumber": phone_number,
            "merchantId": self.merchant_id,
            "generated": int(time.time()),
        }
        return self._sign_es256(payload)

    def generate_signed_token_for_get_transaction(self, tx_id: str) -> str:
        payload = {
            "id": tx_id,
            "merId": self.merchant_id,
            # Some SDK examples use `merId` while others use `merchantId`.
            # Include both to stay compatible across gateway validators.
            "merchantId": self.merchant_id,
            "generated": int(time.time()),
        }
        return self._sign_es256(payload)

    def generate_signed_token_for_direct_payment_or_b2c(
        self, amount: float, payment_reason: str, payment_method: str, phone_number: str
    ) -> str:
        payload = {
            "amount": amount,
            "paymentReason": payment_reason,
            "paymentMethod": payment_method,
            "phoneNumber": phone_number,
            "merchantId": self.merchant_id,
            "generated": int(time.time()),
        }
        return self._sign_es256(payload)

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(f"{self.base_url}/{endpoint}", json=payload, timeout=30)
        if not response.ok:
            try:
                raise Exception(response.json())
            except ValueError as exc:
                raise Exception(response.text) from exc
        return response.json()

    def generate_payment_url(
        self,
        tx_id: str,
        amount: float,
        payment_reason: str,
        success_redirect_url: str,
        failure_redirect_url: str,
        notify_url: str,
        phone_number: str = "",
        cancel_redirect_url: str = "",
    ) -> str:
        token = self.generate_signed_token_for_initiate_payment(amount, payment_reason)
        payload: Dict[str, Any] = {
            "id": tx_id,
            "amount": amount,
            "reason": payment_reason,
            "merchantId": self.merchant_id,
            "signedToken": token,
            "successRedirectUrl": success_redirect_url,
            "failureRedirectUrl": failure_redirect_url,
            "notifyUrl": notify_url,
            "cancelRedirectUrl": cancel_redirect_url,
        }
        if phone_number:
            payload["phoneNumber"] = phone_number
        data = self._post("initiate-payment", payload)
        return data["url"]

    def direct_payment(
        self,
        tx_id: str,
        amount: float,
        payment_reason: str,
        notify_url: str,
        phone_number: str,
        payment_method: str,
    ) -> Dict[str, Any]:
        token = self.generate_signed_token_for_direct_payment(
            amount, payment_reason, payment_method, phone_number
        )
        payload = {
            "id": tx_id,
            "amount": amount,
            "reason": payment_reason,
            "merchantId": self.merchant_id,
            "signedToken": token,
            "phoneNumber": phone_number,
            "paymentMethod": payment_method,
            "notifyUrl": notify_url,
        }
        return self._post("direct-payment", payload)

    def send_to_customer(
        self,
        tx_id: str,
        amount: float,
        payment_reason: str,
        phone_number: str,
        payment_method: str,
        notify_url: str,
    ) -> Dict[str, Any]:
        token = self.generate_signed_token_for_direct_payment_or_b2c(
            amount, payment_reason, payment_method, phone_number
        )
        payload = {
            "id": tx_id,
            "clientReference": tx_id,
            "amount": amount,
            "reason": payment_reason,
            "merchantId": self.merchant_id,
            "signedToken": token,
            "receiverAccountNumber": phone_number,
            "notifyUrl": notify_url,
            "paymentMethod": payment_method,
        }
        return self._post("payout-transfer", payload)

    def check_transaction_status(self, tx_id: str) -> Dict[str, Any]:
        token = self.generate_signed_token_for_get_transaction(tx_id)
        payload = {
            "id": tx_id,
            "merchantId": self.merchant_id, 
            "signedToken": token,
        }
        return self._post("fetch-transaction-status", payload)
