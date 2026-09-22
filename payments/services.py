# payments/services.py

from decimal import Decimal, InvalidOperation
import logging

import requests
from django.conf import settings

from proposals.models import Proposal


logger = logging.getLogger(__name__)


PAYSTACK_BASE_URL = "https://api.paystack.co"
PAYSTACK_INITIALIZE_URL = (
    f"{PAYSTACK_BASE_URL}/transaction/initialize"
)
PAYSTACK_VERIFY_URL = (
    f"{PAYSTACK_BASE_URL}/transaction/verify"
)


# ============================================================
# MONEY
# ============================================================

def amount_to_subunit(amount):
    """
    Convert a normal currency amount into Paystack subunits.

    Example:

        NGN 100,000.00
        -> 10,000,000 kobo
    """

    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Invalid payment amount.") from exc

    if amount <= Decimal("0.00"):
        raise ValueError(
            "Payment amount must be greater than zero."
        )

    return int(
        (amount * Decimal("100")).quantize(
            Decimal("1")
        )
    )


def subunit_to_amount(value):
    """
    Convert Paystack subunits back to normal currency amount.
    """

    try:
        return (
            Decimal(str(value))
            / Decimal("100")
        ).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(
            "Invalid provider amount."
        ) from exc


# ============================================================
# PAYMENT SUMMARY
# ============================================================

def get_payment_summary(proposal):
    """
    Calculate the actual financial state of a proposal.

    The payable total comes from Proposal.payment_total, which
    handles both software proposals and procurement proposals.

    Only successful / partially refunded payments count.

    Refunded amounts are deducted from the retained amount.
    """

    total_price = (
        proposal.payment_total
        or Decimal("0.00")
    )

    payments = proposal.payments.filter(
        status__in=[
            "successful",
            "partially_refunded",
        ]
    )

    total_paid = Decimal("0.00")

    for payment in payments:
        amount = (
            payment.amount
            or Decimal("0.00")
        )

        refunded = (
            payment.refunded_amount
            or Decimal("0.00")
        )

        retained = max(
            Decimal("0.00"),
            amount - refunded,
        )

        total_paid += retained

    total_paid = max(
        Decimal("0.00"),
        total_paid,
    )

    outstanding = max(
        Decimal("0.00"),
        total_price - total_paid,
    )

    if total_price <= Decimal("0.00"):
        payment_status = "not_payable"

    elif total_paid <= Decimal("0.00"):
        payment_status = "unpaid"

    elif outstanding <= Decimal("0.00"):
        payment_status = "paid"

    else:
        payment_status = "partially_paid"

    return {
        "proposal_total": total_price,
        "total_paid": total_paid,
        "outstanding_balance": outstanding,
        "currency": proposal.currency,
        "status": payment_status,
    }


# ============================================================
# PAYSTACK HEADERS
# ============================================================

def get_paystack_headers():
    secret_key = getattr(
        settings,
        "PAYSTACK_SECRET_KEY",
        "",
    )

    if not secret_key:
        raise RuntimeError(
            "PAYSTACK_SECRET_KEY is not configured."
        )

    return {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ============================================================
# INITIALIZE PAYSTACK
# ============================================================

def initialize_paystack_payment(
    *,
    payment,
    email,
    callback_url=None,
):
    """
    Initialize a payment on Paystack.

    Returns:

        {
            "authorization_url": "...",
            "access_code": "...",
            "reference": "...",
            "response": {...}
        }

    The Paystack secret key is used only on the backend.
    """

    if not email:
        raise ValueError(
            "A customer email address is required."
        )

    email = str(email).strip().lower()

    currency = (
        str(payment.currency or "")
        .strip()
        .upper()
    )

    if not currency:
        raise ValueError(
            "Payment currency is required."
        )

    amount_subunit = amount_to_subunit(
        payment.amount
    )

    proposal = payment.proposal

    payload = {
        "email": email,
        "amount": str(amount_subunit),
        "currency": currency,
        "reference": payment.transaction_reference,

        "metadata": {
            "payment_id": str(payment.id),
            "proposal_id": str(payment.proposal_id),
            "proposal_public_token": str(
                proposal.public_token
            ),
            "payment_type": payment.payment_type,
            "milestone_id": (
                str(payment.milestone_id)
                if payment.milestone_id
                else None
            ),
            "milestone_title": (
                payment.milestone.title
                if payment.milestone
                else None
            ),
            "company": "AB Technologies",
        },
    }

    if callback_url:
        payload["callback_url"] = callback_url

    headers = get_paystack_headers()

    logger.info(
        "Initializing Paystack payment %s | amount=%s %s",
        payment.transaction_reference,
        payment.amount,
        currency,
    )

    try:
        response = requests.post(
            PAYSTACK_INITIALIZE_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

    except requests.RequestException as exc:
        logger.exception(
            "Paystack initialization request failed "
            "for payment %s",
            payment.id,
        )

        raise RuntimeError(
            "Unable to connect to Paystack."
        ) from exc

    try:
        response_data = response.json()

    except ValueError as exc:
        logger.error(
            "Paystack returned non-JSON response. "
            "HTTP %s",
            response.status_code,
        )

        raise RuntimeError(
            "Paystack returned an invalid response."
        ) from exc

    if (
        not response.ok
        or not response_data.get("status")
    ):
        message = response_data.get(
            "message",
            "Paystack could not initialize the payment.",
        )

        logger.error(
            "Paystack initialization failed "
            "for payment %s: %s",
            payment.id,
            response_data,
        )

        raise RuntimeError(message)

    data = response_data.get("data") or {}

    authorization_url = data.get(
        "authorization_url"
    )

    access_code = data.get(
        "access_code"
    )

    provider_reference = data.get(
        "reference"
    )

    if not authorization_url:
        logger.error(
            "Paystack response missing authorization_url: %s",
            response_data,
        )

        raise RuntimeError(
            "Paystack did not return a checkout URL."
        )

    if not provider_reference:
        raise RuntimeError(
            "Paystack did not return a transaction reference."
        )

    return {
        "authorization_url": authorization_url,
        "access_code": access_code,
        "reference": provider_reference,
        "response": response_data,
    }


# ============================================================
# VERIFY PAYSTACK TRANSACTION
# ============================================================

def verify_paystack_transaction(reference):
    """
    Ask Paystack directly for the current state of a transaction.

    This is a fallback / reconciliation mechanism.

    The webhook remains the primary automatic notification mechanism.
    """

    if not reference:
        raise ValueError(
            "A transaction reference is required."
        )

    headers = get_paystack_headers()

    url = (
        f"{PAYSTACK_VERIFY_URL}/"
        f"{reference}"
    )

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=30,
        )

    except requests.RequestException as exc:
        logger.exception(
            "Paystack verification request failed "
            "for reference %s",
            reference,
        )

        raise RuntimeError(
            "Unable to connect to Paystack."
        ) from exc

    try:
        response_data = response.json()

    except ValueError as exc:
        raise RuntimeError(
            "Paystack returned an invalid verification response."
        ) from exc

    if (
        not response.ok
        or not response_data.get("status")
    ):
        raise RuntimeError(
            response_data.get(
                "message",
                "Paystack verification failed.",
            )
        )

    return response_data