"""
Minimal Razorpay TEST MODE client using the Orders API.
Docs: https://razorpay.com/docs/api/orders/
Auth: Basic Auth with your TEST key_id / key_secret (get these from
Razorpay Dashboard -> Account & Settings -> API Keys -> Test Mode).

Set these as environment variables before running the server:
    export RAZORPAY_KEY_ID="rzp_test_xxxxxxxx"
    export RAZORPAY_KEY_SECRET="xxxxxxxxxxxxxxxx"

If the keys are not set, this module runs in MOCK MODE so you can
keep building/demoing the rest of the agent without a Razorpay account.
"""
import os
import requests
from requests.auth import HTTPBasicAuth

RAZORPAY_BASE_URL = "https://api.razorpay.com/v1"
KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")

MOCK_MODE = not (KEY_ID and KEY_SECRET)


def create_order(amount_rupees: int, receipt: str, notes: dict | None = None):
    """
    Creates a Razorpay order in test mode.
    amount_rupees: order amount in RUPEES (we convert to paise as Razorpay requires).
    Returns a dict with at least: id, status, amount, currency, mock (bool)
    """
    amount_paise = int(amount_rupees * 100)

    if MOCK_MODE:
        # Mock response shaped like a real Razorpay order object,
        # so the rest of the app doesn't need to know the difference.
        import uuid
        return {
            "id": f"order_MOCK{uuid.uuid4().hex[:14]}",
            "entity": "order",
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "status": "created",
            "notes": notes or {},
            "mock": True,
        }

    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "notes": notes or {},
    }
    try:
        resp = requests.post(
            f"{RAZORPAY_BASE_URL}/orders",
            json=payload,
            auth=HTTPBasicAuth(KEY_ID, KEY_SECRET),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        data["mock"] = False
        return data
    except requests.exceptions.RequestException as e:
        # Real, honest failure - never fake a success here.
        return {
            "id": None,
            "status": "failed",
            "error": str(e),
            "mock": False,
        }
