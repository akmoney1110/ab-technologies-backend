# payments/views.py

import hashlib
import hmac
import logging
import hashlib
import hmac
import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from proposals.models import (
    Proposal,
    ProposalMilestone,
    ProposalPayment,
)

from .serializers import (
    ProposalPaymentSerializer,
    ProposalMilestoneSerializer,
)

from .services import (
    get_payment_summary,
    initialize_paystack_payment,
    verify_paystack_transaction,
)




from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse
from django.utils import timezone
from decimal import Decimal
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from proposals.models import (
    Proposal,
    ProposalMilestone,
    ProposalPayment,
)

from .serializers import (
    ProposalPaymentSerializer,
    ProposalMilestoneSerializer,
)

from .services import (
    get_payment_summary,
    initialize_paystack_payment,
    verify_paystack_transaction,
)


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

ALLOWED_PROPOSAL_STATUSES = {
    "accepted",
    "completed",
}


ACTIVE_PAYMENT_STATUSES = {
    "pending",
    "processing",
}


SUCCESSFUL_PAYMENT_STATUSES = {
    "successful",
    "partially_refunded",
}


# ============================================================
# AUTH / PROPOSAL HELPERS
# ============================================================

def get_request_email(request):
    return (
        str(
            getattr(
                request.user,
                "email",
                "",
            )
            or ""
        )
        .strip()
        .lower()
    )


def get_client_proposal(
    request,
    public_token,
    *,
    for_update=False,
):
    """
    Return the proposal belonging to the authenticated client.

    Access is based on:

        authenticated user email
        ==
        proposal lead email
    """

    email = get_request_email(request)

    if not email:
        logger.warning(
            "Payment access denied: authenticated user "
            "has no email. user=%s",
            request.user,
        )
        return None

    qs = (
        Proposal.objects
        .select_related(
            "lead",
            "organization",
        )
        .filter(
            public_token=public_token,
        )
    )

    if for_update:
        qs = qs.select_for_update()

    proposal = qs.first()

    if not proposal:
        logger.warning(
            "Payment proposal not found: token=%s",
            public_token,
        )
        return None

    lead_email = (
        str(
            getattr(
                proposal.lead,
                "email",
                "",
            )
            or ""
        )
        .strip()
        .lower()
    )

    if lead_email != email:
        logger.warning(
            "Payment access denied: email mismatch "
            "proposal=%s user=%s",
            proposal.id,
            request.user,
        )
        return None

    if proposal.status not in ALLOWED_PROPOSAL_STATUSES:
        logger.warning(
            "Payment access denied: proposal %s "
            "has status=%s",
            proposal.id,
            proposal.status,
        )
        return None

    return proposal


# ============================================================
# PAYMENT SUMMARY
# ============================================================

def serialize_summary(
    proposal,
    summary,
):
    return {
        "proposal_total": str(
            summary["proposal_total"]
        ),
        "total_paid": str(
            summary["total_paid"]
        ),
        "outstanding_balance": str(
            summary["outstanding_balance"]
        ),

        "currency": summary["currency"],

        "status": summary["status"],

        "proposal_total_formatted": (
            f"{proposal.currency} "
            f"{summary['proposal_total']:,.2f}"
        ),

        "total_paid_formatted": (
            f"{proposal.currency} "
            f"{summary['total_paid']:,.2f}"
        ),

        "outstanding_balance_formatted": (
            f"{proposal.currency} "
            f"{summary['outstanding_balance']:,.2f}"
        ),
    }


# ============================================================
# MILESTONE HELPERS
# ============================================================

def sync_milestone_payment_status(
    milestone,
    *,
    save=True,
):
    """
    Recalculate milestone payment_status from actual
    successful payments.
    """

    if not milestone.payment_required:
        new_status = "not_required"

    else:
        total_paid = milestone.total_paid

        if total_paid >= milestone.amount:
            new_status = "paid"

        elif total_paid > Decimal("0.00"):
            new_status = "partially_paid"

        else:
            new_status = "unpaid"

    changed = (
        milestone.payment_status
        != new_status
    )

    if changed:
        milestone.payment_status = new_status

        if save:
            milestone.save(
                update_fields=[
                    "payment_status",
                    "updated_at",
                ]
            )

    return new_status


def unlock_next_milestone(proposal, completed_milestone):
    """
    Unlock the next payment-required milestone after the
    supplied milestone has been completely paid.
    """

    next_milestone = (
        proposal.milestone_records
        .filter(
            payment_required=True,
            order__gt=completed_milestone.order,
        )
        .exclude(
            status="cancelled",
        )
        .order_by("order")
        .first()
    )

    if not next_milestone:
        return

    if next_milestone.payment_status == "paid":
        return

    if next_milestone.status == "locked":
        next_milestone.status = "pending"

        next_milestone.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

def mark_all_milestones_paid(proposal):
    """
    Mark every payment-required milestone on the proposal as paid
    and completed. Used after a full-balance payment succeeds.

    Returns the number of milestones updated.
    """

    milestones = (
        proposal.milestone_records
        .filter(payment_required=True)
        .exclude(status="cancelled")
    )

    now = timezone.now()
    updated = 0

    for milestone in milestones:
        changed_fields = []

        if milestone.payment_status != "paid":
            milestone.payment_status = "paid"
            changed_fields.append("payment_status")

        if milestone.status != "completed":
            milestone.status = "completed"
            changed_fields.append("status")

        if milestone.completed_at is None:
            milestone.completed_at = now
            changed_fields.append("completed_at")

        if changed_fields:
            changed_fields.append("updated_at")
            milestone.save(update_fields=changed_fields)
            updated += 1

    logger.info(
        "Full-balance payment: marked %s milestones paid on proposal %s",
        updated,
        proposal.id,
    )

    return updated


def sync_after_successful_payment(payment):
    """
    Synchronize proposal and milestone payment state after a payment
    has been successfully completed.

    Handles both:

    1. Normal milestone payments
       payment.milestone != None

    2. Full proposal payments
       payment.milestone == None
    """

    proposal = payment.proposal

    # ========================================================
    # FULL BALANCE PAYMENT
    #
    # A full payment is not attached to a milestone.
    # Therefore, once the proposal outstanding balance is
    # zero, ALL payable milestones must be marked as
    # paid/completed.
    # ========================================================

    if payment.milestone_id is None:

        # Refresh financial state after payment.mark_successful()
        proposal.refresh_from_db()

        # Force a fresh read of the aggregate. If outstanding_balance
        # is a property that aggregates payments, this returns the
        # correct value now that the payment row is saved as successful.
        outstanding = proposal.outstanding_balance

        logger.info(
            "Full-balance sync check | proposal=%s | outstanding=%s",
            proposal.id,
            outstanding,
        )

        if Decimal(outstanding or 0) <= Decimal("0.00"):
            mark_all_milestones_paid(proposal)

        return

    # ========================================================
    # NORMAL MILESTONE PAYMENT
    # ========================================================

    milestone = (
        ProposalMilestone.objects
        .select_for_update()
        .get(pk=payment.milestone_id)
    )

    # Recalculate the actual amount paid against this particular
    # milestone.
    sync_milestone_payment_status(milestone)

    # ========================================================
    # IF MILESTONE IS NOW FULLY PAID
    # ========================================================

    if milestone.is_paid:

        if milestone.status != "completed":
            milestone.status = "completed"

            if milestone.completed_at is None:
                milestone.completed_at = timezone.now()

            milestone.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "updated_at",
                ]
            )

        # Unlock the next payment-required milestone.
        unlock_next_milestone(proposal, milestone)


# ============================================================
# GET CLIENT PAYMENTS
# ============================================================


# ============================================================
# GET CLIENT PAYMENTS
# ============================================================

class ClientProposalPaymentsView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        public_token,
    ):
        proposal = get_client_proposal(
            request,
            public_token,
        )

        if not proposal:
            return Response(
                {
                    "success": False,
                    "error": (
                        "Proposal not found or "
                        "you don't have access to it."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        summary = get_payment_summary(
            proposal
        )

        # --------------------------------------------------------
        # MILESTONES
        # --------------------------------------------------------

        payment_qs = (
            ProposalPayment.objects
            .filter(
                status__in=SUCCESSFUL_PAYMENT_STATUSES,
            )
            .only(
                "id",
                "milestone_id",
                "amount",
                "refunded_amount",
                "status",
            )
        )

        milestone_qs = (
            ProposalMilestone.objects
            .filter(
                proposal=proposal,
            )
            .order_by(
                "order",
                "created_at",
            )
            .prefetch_related(
                Prefetch(
                    "payments",
                    queryset=payment_qs,
                    to_attr="_payment_objects",
                )
            )
        )

        # --------------------------------------------------------
        # ALL PAYMENTS
        # --------------------------------------------------------

        payments_qs = (
            ProposalPayment.objects
            .filter(
                proposal=proposal,
            )
            .select_related(
                "milestone",
            )
            .order_by(
                "-created_at",
            )
        )

        return Response(
            {
                "success": True,

                "proposal": {
                    "id": str(
                        proposal.id
                    ),

                    "public_token": str(
                        proposal.public_token
                    ),

                    "title": proposal.title,

                    "currency": proposal.currency,

                    "status": proposal.status,

                    "total_price": str(
                        proposal.total_price
                    ),
                },

                "summary": serialize_summary(
                    proposal,
                    summary,
                ),

                # Backwards compatibility
                "payment_summary": (
                    serialize_summary(
                        proposal,
                        summary,
                    )
                ),

                "milestones": (
                    ProposalMilestoneSerializer(
                        milestone_qs,
                        many=True,
                    ).data
                ),

                "payments": (
                    ProposalPaymentSerializer(
                        payments_qs,
                        many=True,
                    ).data
                ),
            }
        )


# ============================================================
# INITIATE MILESTONE PAYMENT
# ============================================================

class InitiateProposalMilestonePaymentView(
    APIView
):

    permission_classes = [
        IsAuthenticated,
    ]

    @transaction.atomic
    def post(
        self,
        request,
        public_token,
    ):
        proposal = get_client_proposal(
            request,
            public_token,
            for_update=True,
        )

        if not proposal:
            return Response(
                {
                    "success": False,
                    "error": "Proposal not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        milestone_id = request.data.get(
            "milestone_id"
        )

        if not milestone_id:
            return Response(
                {
                    "success": False,
                    "error": (
                        "milestone_id is required."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------------
        # LOCK MILESTONE
        # --------------------------------------------------------

        milestone = (
            ProposalMilestone.objects
            .select_for_update()
            .filter(
                id=milestone_id,
                proposal=proposal,
            )
            .first()
        )

        if not milestone:
            return Response(
                {
                    "success": False,
                    "error": (
                        "Milestone not found on "
                        "this proposal."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # --------------------------------------------------------
        # BASIC GUARDS
        # --------------------------------------------------------

        if not milestone.payment_required:
            return Response(
                {
                    "success": False,
                    "error": (
                        "This milestone does not "
                        "require payment."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if milestone.status == "cancelled":
            return Response(
                {
                    "success": False,
                    "error": (
                        "This milestone has "
                        "been cancelled."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if milestone.status == "locked":
            return Response(
                {
                    "success": False,
                    "error": (
                        "This milestone is not "
                        "available for payment yet."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------------
        # SYNC CURRENT PAYMENT STATE
        # --------------------------------------------------------

        sync_milestone_payment_status(
            milestone,
            save=True,
        )

        if milestone.is_paid:
            return Response(
                {
                    "success": False,
                    "error": (
                        "This milestone has "
                        "already been paid."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------------
        # PREVIOUS MILESTONE MUST BE PAID
        # --------------------------------------------------------

        previous = (
            ProposalMilestone.objects
            .filter(
                proposal=proposal,
                payment_required=True,
                order__lt=milestone.order,
            )
            .exclude(
                status="cancelled",
            )
            .order_by(
                "-order",
            )
            .first()
        )

        if previous:
            sync_milestone_payment_status(
                previous,
                save=True,
            )

            if not previous.is_paid:
                return Response(
                    {
                        "success": False,

                        "error": (
                            f"Please complete payment "
                            f"for '{previous.title}' first."
                        ),

                        "blocking_milestone": {
                            "id": str(
                                previous.id
                            ),

                            "title": (
                                previous.title
                            ),

                            "order": (
                                previous.order
                            ),
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # --------------------------------------------------------
        # OUTSTANDING AMOUNT
        # --------------------------------------------------------

        amount = (
            milestone.outstanding_balance
        )

        if amount <= Decimal("0.00"):
            sync_milestone_payment_status(
                milestone,
                save=True,
            )

            return Response(
                {
                    "success": False,
                    "error": (
                        "There is no outstanding "
                        "amount for this milestone."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------------
        # PREVENT DUPLICATE CHECKOUTS
        # --------------------------------------------------------

        existing_payment = (
            ProposalPayment.objects
            .filter(
                proposal=proposal,
                milestone=milestone,
                status__in=ACTIVE_PAYMENT_STATUSES,
            )
            .order_by(
                "-created_at",
            )
            .first()
        )

        if existing_payment:
            provider_response = (
                existing_payment.provider_response
                or {}
            )

            checkout_url = (
                provider_response
                .get("data", {})
                .get("authorization_url")
            )

            access_code = (
                provider_response
                .get("data", {})
                .get("access_code")
            )

            if checkout_url:
                return Response(
                    {
                        "success": True,
                        "existing": True,

                        "message": (
                            "A payment session already "
                            "exists for this milestone."
                        ),

                        "payment": {
                            "id": str(
                                existing_payment.id
                            ),

                            "transaction_reference": (
                                existing_payment
                                .transaction_reference
                            ),

                            "provider_reference": (
                                existing_payment
                                .provider_reference
                            ),

                            "amount": str(
                                existing_payment.amount
                            ),

                            "currency": (
                                existing_payment.currency
                            ),

                            "status": (
                                existing_payment.status
                            ),
                        },

                        "checkout_url": checkout_url,

                        "access_code": access_code,
                    },
                    status=status.HTTP_200_OK,
                )

            # Paystack initialization may have failed
            # before a checkout URL was stored.
            existing_payment.mark_failed(
                provider_response={
                    **provider_response,
                    "reason": (
                        "Previous payment session "
                        "did not contain a checkout URL."
                    ),
                }
            )

        # --------------------------------------------------------
        # PAYMENT TYPE
        # --------------------------------------------------------

        if (
            milestone.total_paid
            <= Decimal("0.00")
        ):
            if amount == milestone.amount:
                payment_type = "full"
            else:
                payment_type = "deposit"

        else:
            payment_type = "balance"

        # --------------------------------------------------------
        # CREATE LOCAL PAYMENT
        # --------------------------------------------------------

        payment = ProposalPayment.objects.create(
            proposal=proposal,

            milestone=milestone,

            payment_type=payment_type,

            provider="paystack",

            amount=amount,

            currency=proposal.currency,

            status="pending",

            initiated_by=request.user,
        )

        # --------------------------------------------------------
        # INITIALIZE PAYSTACK
        # --------------------------------------------------------

        callback_url = getattr(
        settings,
    "PAYSTACK_CALLBACK_URL",
    "",
        )

        if callback_url:
            parts = urlsplit(callback_url)

            query = dict(
                parse_qsl(
            parts.query,
            keep_blank_values=True,
                )
            )

            query["public_token"] = str(
                proposal.public_token
            )

            callback_url = urlunsplit(
                (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )

        try:
            gateway = (
                initialize_paystack_payment(
                    payment=payment,
                    email=proposal.lead.email,
                    callback_url=callback_url,
                )
            )

        except Exception as exc:
            logger.exception(
                "Paystack initialization failed "
                "for payment=%s",
                payment.id,
            )

            payment.mark_failed(
                provider_response={
                    "error": str(exc),
                    "stage": "initialization",
                }
            )

            return Response(
                {
                    "success": False,
                    "error": (
                        "We could not start the "
                        "payment. Please try again."
                    ),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # --------------------------------------------------------
        # STORE PAYSTACK RESPONSE
        # --------------------------------------------------------

        payment.provider_reference = (
            gateway.get("reference")
            or ""
        )

        payment.provider_response = (
            gateway.get("response")
            or {}
        )

        payment.status = "processing"

        payment.save(
            update_fields=[
                "provider_reference",
                "provider_response",
                "status",
                "updated_at",
            ]
        )

        # --------------------------------------------------------
        # RESPONSE
        # --------------------------------------------------------

        return Response(
            {
                "success": True,
                   "public_token": str(

                    proposal.public_token

                    ),

     

                "payment": {
                    "id": str(
                        payment.id
                    ),

                    "transaction_reference": (
                        payment.transaction_reference
                    ),

                    "provider_reference": (
                        payment.provider_reference
                    ),

                    "amount": str(
                        payment.amount
                    ),

                    "currency": (
                        payment.currency
                    ),

                    "status": (
                        payment.status
                    ),

                    "payment_type": (
                        payment.payment_type
                    ),
                },

                "milestone": {
                    "id": str(
                        milestone.id
                    ),

                    "order": (
                        milestone.order
                    ),

                    "title": (
                        milestone.title
                    ),

                    "amount": str(
                        milestone.amount
                    ),

                    "total_paid": str(
                        milestone.total_paid
                    ),

                    "outstanding": str(
                        milestone.outstanding_balance
                    ),
                },

                "checkout_url": (
                    gateway["authorization_url"]
                ),

                "access_code": (
                    gateway.get("access_code")
                ),
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# PAYMENT DETAIL
# ============================================================

class ClientProposalPaymentDetailView(
    APIView
):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        public_token,
        payment_id,
    ):
        proposal = get_client_proposal(
            request,
            public_token,
        )

        if not proposal:
            return Response(
                {
                    "success": False,
                    "error": "Proposal not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        payment = (
            ProposalPayment.objects
            .select_related(
                "milestone",
            )
            .filter(
                id=payment_id,
                proposal=proposal,
            )
            .first()
        )

        if not payment:
            return Response(
                {
                    "success": False,
                    "error": "Payment not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,

                "payment": (
                    ProposalPaymentSerializer(
                        payment
                    ).data
                ),
            }
        )


# ============================================================
# VERIFY PAYMENT
# ============================================================

class VerifyProposalPaymentView(
    APIView
):
    """
    Client-facing fallback verification endpoint.

    The client provides the AB Technologies transaction reference.

    We then ask Paystack directly.

    This does NOT trust the frontend's claim that payment succeeded.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    @transaction.atomic
    def get(
        self,
        request,
        public_token,
    ):
        proposal = get_client_proposal(
            request,
            public_token,
            for_update=True,
        )

        if not proposal:
            return Response(
                {
                    "success": False,
                    "error": "Proposal not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        reference = (
            request.query_params.get(
                "reference"
            )
            or request.query_params.get(
                "trxref"
            )
        )

        if not reference:
            return Response(
                {
                    "success": False,
                    "error": (
                        "Payment reference is required."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = (
            ProposalPayment.objects
            .select_for_update()
            .select_related(
                "proposal",
                "milestone",
            )
            .filter(
                proposal=proposal,
                transaction_reference=reference,
            )
            .first()
        )

        if not payment:
            return Response(
                {
                    "success": False,
                    "error": "Payment not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Already processed.
        if payment.status == "successful":
            return Response(
                {
                    "success": True,
                    "status": "successful",

                    "payment": (
                        ProposalPaymentSerializer(
                            payment
                        ).data
                    ),
                }
            )

        # --------------------------------------------------------
        # ASK PAYSTACK
        # --------------------------------------------------------

        try:
            verification = (
                verify_paystack_transaction(
                    reference
                )
            )

        except Exception as exc:
            logger.exception(
                "Paystack verification failed "
                "for payment=%s",
                payment.id,
            )

            return Response(
                {
                    "success": False,
                    "error": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = (
            verification.get("data")
            or {}
        )

        provider_reference = str(
            data.get("reference")
            or ""
        )

        provider_status = str(
            data.get("status")
            or ""
        ).lower()

        if (
            provider_reference
            != payment.transaction_reference
        ):
            return Response(
                {
                    "success": False,
                    "error": (
                        "Payment reference mismatch."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if provider_status != "success":
            return Response(
                {
                    "success": True,

                    "status": provider_status
                    or "pending",

                    "payment": (
                        ProposalPaymentSerializer(
                            payment
                        ).data
                    ),
                }
            )

        # --------------------------------------------------------
        # VERIFY AMOUNT
        # --------------------------------------------------------

        try:
            provider_amount = (
                Decimal(
                    str(
                        data.get(
                            "amount",
                            "0",
                        )
                    )
                )
                / Decimal("100")
            )

            provider_amount = (
                provider_amount.quantize(
                    Decimal("0.01")
                )
            )

        except (
            InvalidOperation,
            ValueError,
            TypeError,
        ):
            return Response(
                {
                    "success": False,
                    "error": (
                        "Invalid amount returned "
                        "by Paystack."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if provider_amount != payment.amount:
            payment.mark_failed(
                provider_response={
                    "error": (
                        "Paystack verification "
                        "amount mismatch."
                    ),

                    "expected_amount": str(
                        payment.amount
                    ),

                    "received_amount": str(
                        provider_amount
                    ),

                    "paystack_response": data,
                }
            )

            return Response(
                {
                    "success": False,
                    "error": (
                        "Payment amount does not "
                        "match the expected amount."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------------
        # VERIFY CURRENCY
        # --------------------------------------------------------

        provider_currency = str(
            data.get("currency")
            or ""
        ).upper()

        local_currency = str(
            payment.currency
            or ""
        ).upper()

        if provider_currency != local_currency:
            payment.mark_failed(
                provider_response={
                    "error": (
                        "Paystack verification "
                        "currency mismatch."
                    ),

                    "expected_currency": (
                        local_currency
                    ),

                    "received_currency": (
                        provider_currency
                    ),

                    "paystack_response": data,
                }
            )

            return Response(
                {
                    "success": False,
                    "error": (
                        "Payment currency does not "
                        "match the expected currency."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------------
        # SUCCESS
        # --------------------------------------------------------

        payment.mark_successful(
            provider_reference=str(
                data.get("id")
                or ""
            ),

            provider_response=data,
        )

        sync_after_successful_payment(
            payment
        )

        return Response(
            {
                "success": True,

                "status": "successful",

                "payment": (
                    ProposalPaymentSerializer(
                        payment
                    ).data
                ),
            }
        )


# ============================================================
# PAYSTACK WEBHOOK
# ============================================================

class PaystackWebhookView(
    APIView
):
    """
    Paystack webhook.

    This endpoint is unauthenticated because Paystack calls it.

    Security:
        HMAC SHA512 signature verification.

    Only a verified Paystack transaction can become successful.
    """

    authentication_classes = []

    permission_classes = []

    @transaction.atomic
    def post(
        self,
        request,
    ):
        signature = (
            request.headers.get(
                "X-Paystack-Signature"
            )
        )

        if not signature:
            logger.warning(
                "Paystack webhook missing signature."
            )

            return HttpResponse(
                status=400
            )

        secret_key = getattr(
            settings,
            "PAYSTACK_SECRET_KEY",
            "",
        )

        if not secret_key:
            logger.error(
                "PAYSTACK_SECRET_KEY is not configured."
            )

            return HttpResponse(
                status=500
            )

        # IMPORTANT:
        # Use the raw request body.
        expected_signature = hmac.new(
            secret_key.encode(),
            request.body,
            hashlib.sha512,
        ).hexdigest()

        if not hmac.compare_digest(
            signature,
            expected_signature,
        ):
            logger.warning(
                "Paystack webhook signature mismatch."
            )

            return HttpResponse(
                status=400
            )

        event = request.data.get(
            "event"
        )

        if event != "charge.success":
            return HttpResponse(
                status=200
            )

        data = (
            request.data.get("data")
            or {}
        )

        reference = data.get(
            "reference"
        )

        if not reference:
            return HttpResponse(
                status=200
            )

        # --------------------------------------------------------
        # FIND PAYMENT
        # --------------------------------------------------------

        payment = (
            ProposalPayment.objects
            .select_for_update()
            .select_related(
                "proposal",
                "milestone",
            )
            .filter(
                transaction_reference=reference
            )
            .first()
        )

        if not payment:
            logger.warning(
                "Paystack webhook for unknown "
                "reference=%s",
                reference,
            )

            # Return 200 so Paystack doesn't keep retrying
            # a transaction that belongs to another system.
            return HttpResponse(
                status=200
            )

        # --------------------------------------------------------
        # IDEMPOTENCY
        # --------------------------------------------------------

        if payment.status == "successful":
            return HttpResponse(
                status=200
            )

        # --------------------------------------------------------
        # VERIFY REFERENCE
        # --------------------------------------------------------

        provider_reference = str(
            data.get("reference")
            or ""
        )

        if (
            provider_reference
            != payment.transaction_reference
        ):
            logger.error(
                "Reference mismatch for payment=%s",
                payment.id,
            )

            return HttpResponse(
                status=400
            )

        # --------------------------------------------------------
        # VERIFY STATUS
        # --------------------------------------------------------

        provider_status = str(
            data.get("status")
            or ""
        ).lower()

        if provider_status != "success":
            return HttpResponse(
                status=200
            )

        # --------------------------------------------------------
        # VERIFY AMOUNT
        # --------------------------------------------------------

        try:
            provider_amount = (
                Decimal(
                    str(
                        data.get(
                            "amount",
                            "0",
                        )
                    )
                )
                / Decimal("100")
            )

            provider_amount = (
                provider_amount.quantize(
                    Decimal("0.01")
                )
            )

        except (
            InvalidOperation,
            ValueError,
            TypeError,
        ):
            logger.error(
                "Invalid amount in Paystack webhook "
                "for payment=%s",
                payment.id,
            )

            return HttpResponse(
                status=400
            )

        if provider_amount != payment.amount:
            payment.mark_failed(
                provider_response={
                    "error": (
                        "Paystack amount mismatch."
                    ),

                    "expected_amount": str(
                        payment.amount
                    ),

                    "received_amount": str(
                        provider_amount
                    ),

                    "paystack_response": data,
                }
            )

            return HttpResponse(
                status=400
            )

        # --------------------------------------------------------
        # VERIFY CURRENCY
        # --------------------------------------------------------

        provider_currency = str(
            data.get("currency")
            or ""
        ).upper()

        local_currency = str(
            payment.currency
            or ""
        ).upper()

        if provider_currency != local_currency:
            payment.mark_failed(
                provider_response={
                    "error": (
                        "Paystack currency mismatch."
                    ),

                    "expected_currency": (
                        local_currency
                    ),

                    "received_currency": (
                        provider_currency
                    ),

                    "paystack_response": data,
                }
            )

            return HttpResponse(
                status=400
            )

        # --------------------------------------------------------
        # SUCCESS
        # --------------------------------------------------------

        payment.mark_successful(
            provider_reference=str(
                data.get("id")
                or ""
            ),

            provider_response=data,
        )

        # --------------------------------------------------------
        # UPDATE MILESTONE
        # --------------------------------------------------------

        sync_after_successful_payment(
            payment
        )

        logger.info(
            "Payment successfully processed | "
            "payment=%s | reference=%s | amount=%s",
            payment.id,
            payment.transaction_reference,
            payment.amount,
        )

        return HttpResponse(
            status=200
        )
    



# payments/views.py

from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from proposals.models import Proposal, ProposalMilestone
from proposals.models import ProposalPayment

# Keep your existing Paystack import/helper.
# Example:
# from .paystack import initialize_transaction, verify_transaction


# ============================================================
# CONSTANTS
# ============================================================

ALLOWED_PROPOSAL_STATUSES = {
    "accepted",
    "completed",
}

ACTIVE_PAYMENT_STATUSES = {
    "pending",
    "processing",
}

SUCCESSFUL_PAYMENT_STATUSES = {
    "successful",
    "partially_refunded",
}


# ============================================================
# HELPERS
# ============================================================


def get_full_balance_amount(proposal):
    """
    Always calculate the amount that remains unpaid.

    This is important because procurement proposals may use
    quote_request.total rather than proposal.total_price.
    """

    amount = proposal.outstanding_balance

    if amount is None:
        return Decimal("0.00")

    amount = Decimal(amount)

    if amount < Decimal("0.00"):
        amount = Decimal("0.00")

    return amount.quantize(Decimal("0.01"))




def sync_full_payment_milestones(proposal):
    """
    Recalculate milestone payment status after a full-balance
    payment.

    We intentionally calculate each milestone from its actual
    payments rather than assuming that a full-balance payment
    belongs to one particular milestone.
    """

    milestones = list(
        proposal.milestone_records
        .filter(
            payment_required=True,
        )
        .exclude(
            status="cancelled",
        )
        .order_by(
            "order",
            "created_at",
        )
    )

    remaining_payment = proposal.total_paid

    for milestone in milestones:

        amount = Decimal(
            milestone.amount or Decimal("0.00")
        )

        milestone_paid = milestone.total_paid

        # ----------------------------------------------------
        # The milestone already has enough directly-linked
        # payment.
        # ----------------------------------------------------

        if milestone_paid >= amount and amount > 0:
            if milestone.payment_status != "paid":
                milestone.payment_status = "paid"

            if milestone.status != "completed":
                milestone.status = "completed"

            if not milestone.completed_at:
                from django.utils import timezone

                milestone.completed_at = timezone.now()

            milestone.save(
                update_fields=[
                    "payment_status",
                    "status",
                    "completed_at",
                    "updated_at",
                ]
            )

            continue

        # ----------------------------------------------------
        # If this milestone does not have a direct payment,
        # use the proposal-level paid amount to determine
        # how much of the overall milestone sequence has
        # been financially covered.
        #
        # This is particularly useful for Pay Full Balance,
        # where milestone=None.
        # ----------------------------------------------------

        directly_paid = milestone_paid

        if directly_paid >= amount and amount > 0:
            continue

        if remaining_payment <= 0:
            break

        covered = min(
            amount,
            remaining_payment,
        )

        if covered >= amount and amount > 0:
            milestone.payment_status = "paid"
            milestone.status = "completed"

            if not milestone.completed_at:
                from django.utils import timezone

                milestone.completed_at = timezone.now()

            milestone.save(
                update_fields=[
                    "payment_status",
                    "status",
                    "completed_at",
                    "updated_at",
                ]
            )

        elif covered > 0:
            milestone.payment_status = "partially_paid"

            if milestone.status == "locked":
                milestone.status = "pending"

            milestone.save(
                update_fields=[
                    "payment_status",
                    "status",
                    "updated_at",
                ]
            )

        remaining_payment -= covered

    # --------------------------------------------------------
    # Unlock next unpaid milestone.
    # --------------------------------------------------------

    unlock_next_milestone(proposal)


# ============================================================
# PAY FULL BALANCE
# ============================================================
class InitiatePrsalFullBalancePaymentView(APIView):
    """
    Initiate one Paystack payment for the entire outstanding
    proposal balance.

    This payment is proposal-level, so:

        milestone = None

    Example:

        POST
        /api/payments/client/<public_token>/payments/pay-full/

    The amount charged is ONLY the current outstanding balance.

    Example:

        Proposal total:       ₦1,000,000
        Already paid:         ₦300,000
        Outstanding:          ₦700,000

        Pay Full Balance -> ₦700,000
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, public_token):

        # ====================================================
        # GET CLIENT PROPOSAL
        # ====================================================

        proposal = get_client_proposal(
            request,
            public_token,
            for_update=True,
        )

        if proposal is None:
            return Response(
                {
                    "success": False,
                    "detail": (
                        "Proposal not found or you are not "
                        "authorized to access it."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ====================================================
        # LOCK PAYMENT STATE
        #
        # We lock the proposal while calculating the balance
        # and creating the payment so two requests cannot
        # create two full-balance payments simultaneously.
        # ====================================================

        with transaction.atomic():

            proposal = (
                Proposal.objects
                .select_for_update()
                .select_related(
                    "lead",
                    "quote_request",
                    "project_request",
                )
                .get(
                    id=proposal.id
                )
            )

            # =================================================
            # CURRENT PAYMENT TOTAL
            # =================================================

            payment_total = (
                proposal.payment_total
                or Decimal("0.00")
            )

            total_paid = (
                proposal.total_paid
                or Decimal("0.00")
            )

            outstanding_balance = (
                proposal.outstanding_balance
                or Decimal("0.00")
            )

            # =================================================
            # NOTHING TO PAY
            # =================================================

            if outstanding_balance <= Decimal("0.00"):

                return Response(
                    {
                        "success": False,
                        "detail": (
                            "This proposal is already fully paid "
                            "or has no payable balance."
                        ),
                        "payment_status": (
                            proposal.payment_status
                        ),
                        "payment_total": str(
                            payment_total
                        ),
                        "total_paid": str(
                            total_paid
                        ),
                        "outstanding_balance": "0.00",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # =================================================
            # CHECK FOR EXISTING ACTIVE FULL-BALANCE PAYMENT
            #
            # Full-balance payments have:
            #
            #     milestone = NULL
            #
            # Therefore we only search milestone=None here.
            # =================================================

            existing_payment = (
                ProposalPayment.objects
                .filter(
                    proposal=proposal,
                    milestone__isnull=True,
                    payment_type="full",
                    status__in=ACTIVE_PAYMENT_STATUSES,
                )
                .order_by("-created_at")
                .first()
            )

            if existing_payment:

                return Response(
                    {
                        "success": True,
                        "message": (
                            "A full-balance payment is already "
                            "being processed."
                        ),
                        "payment": {
                            "id": str(
                                existing_payment.id
                            ),
                            "reference": (
                                existing_payment
                                .transaction_reference
                            ),
                            "amount": str(
                                existing_payment.amount
                            ),
                            "currency": (
                                existing_payment.currency
                            ),
                            "status": (
                                existing_payment.status
                            ),
                            "payment_type": (
                                existing_payment.payment_type
                            ),
                        },
                    },
                    status=status.HTTP_200_OK,
                )

            # =================================================
            # CREATE PAYMENT RECORD
            #
            # IMPORTANT:
            #
            # milestone=None
            #
            # because this payment covers the entire remaining
            # proposal balance rather than one milestone.
            # =================================================

            payment = ProposalPayment.objects.create(
                proposal=proposal,
                milestone=None,
                payment_type="full",
                provider="paystack",
                amount=outstanding_balance,
                currency=proposal.currency,
                status="pending",
                initiated_by=request.user,
            )

            # =================================================
            # PAYSTACK CALLBACK URL
            # =================================================

            callback_url = getattr(
                settings,
                "PAYSTACK_CALLBACK_URL",
                "",
            )

            if callback_url:

                separator = (
                    "&"
                    if "?" in callback_url
                    else "?"
                )

                callback_url = (
                    f"{callback_url}"
                    f"{separator}"
                    f"public_token={proposal.public_token}"
                )

            # =================================================
            # INITIALIZE PAYSTACK
            #
            # Use the SAME helper as milestone payments.
            #
            # Do NOT use:
            #
            #     initialize_paystack_transaction()
            #
            # Your services.py defines:
            #
            #     initialize_paystack_payment()
            # =================================================

            try:

                paystack_response = (
                    initialize_paystack_payment(
                        payment=payment,
                        email=proposal.lead.email,
                        callback_url=callback_url,
                    )
                )

            except Exception as exc:

                logger.exception(
                    "Failed to initialize full-balance "
                    "Paystack payment %s",
                    payment.id,
                )

                payment.status = "failed"

                payment.provider_response = {
                    "error": str(exc),
                }

                payment.save(
                    update_fields=[
                        "status",
                        "provider_response",
                    ]
                )

                return Response(
                    {
                        "success": False,
                        "detail": (
                            "Unable to initialize payment."
                        ),
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            # =================================================
            # MARK PAYMENT AS PROCESSING
            #
            # initialize_paystack_payment() has already
            # validated Paystack's response.
            # =================================================

            payment.status = "processing"

            payment.provider_response = (
                paystack_response.get(
                    "response",
                    {}
                )
            )

            provider_reference = (
                paystack_response.get(
                    "reference"
                )
            )

            if provider_reference:
                payment.provider_reference = (
                    provider_reference
                )

            payment.save(
                update_fields=[
                    "status",
                    "provider_response",
                    "provider_reference",
                ]
            )

        # ====================================================
        # RETURN CHECKOUT INFORMATION
        # ====================================================

        return Response(
            {
                "success": True,

                "message": (
                    "Full balance payment initialized."
                ),

                "payment": {
                    "id": str(
                        payment.id
                    ),

                    "reference": (
                        payment.transaction_reference
                    ),

                    "provider_reference": (
                        payment.provider_reference
                    ),

                    "amount": str(
                        payment.amount
                    ),

                    "currency": (
                        payment.currency
                    ),

                    "status": (
                        payment.status
                    ),

                    "payment_type": (
                        payment.payment_type
                    ),

                    "milestone_id": None,
                },

                "proposal": {
                    "id": str(
                        proposal.id
                    ),

                    "public_token": str(
                        proposal.public_token
                    ),

                    "payment_total": str(
                        proposal.payment_total
                    ),

                    "total_paid": str(
                        proposal.total_paid
                    ),

                    "outstanding_balance": str(
                        proposal.outstanding_balance
                    ),

                    "payment_status": (
                        proposal.payment_status
                    ),
                },

                "paystack": {
                    "authorization_url": (
                        paystack_response.get(
                            "authorization_url"
                        )
                    ),

                    "access_code": (
                        paystack_response.get(
                            "access_code"
                        )
                    ),

                    "reference": (
                        paystack_response.get(
                            "reference",
                            payment.transaction_reference,
                        )
                    ),
                },
            },

            status=status.HTTP_201_CREATED,
        )
        


class InitiateProposalFullBalancePaymentView(APIView):
    """
    Initiate one Paystack payment for the entire outstanding
    proposal balance.

        POST /api/payments/client/<public_token>/payments/pay-full/

    The amount charged is ONLY the current outstanding balance.

    On success (webhook or verify), ALL payable milestones are
    marked as paid/completed by `sync_after_successful_payment`.
    """

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, public_token):

        # ====================================================
        # GET CLIENT PROPOSAL
        # ====================================================

        proposal = get_client_proposal(
            request, public_token, for_update=True
        )

        if proposal is None:
            return Response(
                {
                    "success": False,
                    "detail": (
                        "Proposal not found or you are not authorized "
                        "to access it."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ====================================================
        # LOCK PAYMENT STATE
        # ====================================================

        proposal = (
            Proposal.objects
            .select_for_update()
            .select_related("lead", "quote_request", "project_request")
            .get(id=proposal.id)
        )

        payment_total = proposal.payment_total or Decimal("0.00")
        total_paid = proposal.total_paid or Decimal("0.00")
        outstanding_balance = (
            proposal.outstanding_balance or Decimal("0.00")
        )

        # ====================================================
        # NOTHING TO PAY
        # ====================================================

        if outstanding_balance <= Decimal("0.00"):
            return Response(
                {
                    "success": False,
                    "detail": (
                        "This proposal is already fully paid or has no "
                        "payable balance."
                    ),
                    "payment_status": proposal.payment_status,
                    "payment_total": str(payment_total),
                    "total_paid": str(total_paid),
                    "outstanding_balance": "0.00",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ====================================================
        # CHECK FOR EXISTING ACTIVE FULL-BALANCE PAYMENT
        # ====================================================

        existing_payment = (
            ProposalPayment.objects
            .filter(
                proposal=proposal,
                milestone__isnull=True,
                payment_type="full",
                status__in=ACTIVE_PAYMENT_STATUSES,
            )
            .order_by("-created_at")
            .first()
        )

        if existing_payment:
            provider_response = existing_payment.provider_response or {}

            checkout_url = (
                provider_response
                .get("data", {})
                .get("authorization_url")
            )

            access_code = (
                provider_response
                .get("data", {})
                .get("access_code")
            )

            if checkout_url:
                return Response(
                    {
                        "success": True,
                        "existing": True,
                        "message": (
                            "A full-balance payment is already being "
                            "processed."
                        ),
                        "payment": {
                            "id": str(existing_payment.id),
                            "reference": (
                                existing_payment.transaction_reference
                            ),
                            "provider_reference": (
                                existing_payment.provider_reference
                            ),
                            "amount": str(existing_payment.amount),
                            "currency": existing_payment.currency,
                            "status": existing_payment.status,
                            "payment_type": existing_payment.payment_type,
                            "milestone_id": None,
                        },
                        "proposal": {
                            "id": str(proposal.id),
                            "public_token": str(proposal.public_token),
                            "payment_total": str(proposal.payment_total),
                            "total_paid": str(proposal.total_paid),
                            "outstanding_balance": str(
                                proposal.outstanding_balance
                            ),
                            "payment_status": proposal.payment_status,
                        },
                        "paystack": {
                            "authorization_url": checkout_url,
                            "access_code": access_code,
                            "reference": (
                                existing_payment.transaction_reference
                            ),
                        },
                        "checkout_url": checkout_url,
                    },
                    status=status.HTTP_200_OK,
                )

            # Stale existing payment — mark it failed and fall through
            # to create a fresh one.
            existing_payment.mark_failed(
                provider_response={
                    **provider_response,
                    "reason": (
                        "Previous full-balance payment session did not "
                        "contain a checkout URL."
                    ),
                }
            )

        # ====================================================
        # CREATE PAYMENT RECORD (milestone=None)
        # ====================================================

        payment = ProposalPayment.objects.create(
            proposal=proposal,
            milestone=None,
            payment_type="full",
            provider="paystack",
            amount=outstanding_balance,
            currency=proposal.currency,
            status="pending",
            initiated_by=request.user,
        )

        # ====================================================
        # PAYSTACK CALLBACK URL
        # ====================================================

        callback_url = getattr(settings, "PAYSTACK_CALLBACK_URL", "")

        if callback_url:
            separator = "&" if "?" in callback_url else "?"
            callback_url = (
                f"{callback_url}"
                f"{separator}"
                f"public_token={proposal.public_token}"
            )

        # ====================================================
        # INITIALIZE PAYSTACK
        # ====================================================

        try:
            paystack_response = initialize_paystack_payment(
                payment=payment,
                email=proposal.lead.email,
                callback_url=callback_url,
            )

        except Exception as exc:
            logger.exception(
                "Failed to initialize full-balance Paystack payment %s",
                payment.id,
            )

            payment.status = "failed"
            payment.provider_response = {"error": str(exc)}
            payment.save(
                update_fields=["status", "provider_response"]
            )

            return Response(
                {
                    "success": False,
                    "detail": "Unable to initialize payment.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # ====================================================
        # MARK PAYMENT AS PROCESSING
        # ====================================================

        payment.status = "processing"
        payment.provider_response = (
            paystack_response.get("response", {})
        )

        provider_reference = paystack_response.get("reference")

        if provider_reference:
            payment.provider_reference = provider_reference

        payment.save(
            update_fields=[
                "status",
                "provider_response",
                "provider_reference",
            ]
        )

        # ====================================================
        # RESPONSE
        # ====================================================

        authorization_url = (
            paystack_response.get("authorization_url")
            or (
                paystack_response
                .get("response", {})
                .get("data", {})
                .get("authorization_url")
            )
        )

        access_code = (
            paystack_response.get("access_code")
            or (
                paystack_response
                .get("response", {})
                .get("data", {})
                .get("access_code")
            )
        )

        return Response(
            {
                "success": True,
                "message": "Full balance payment initialized.",
                "payment": {
                    "id": str(payment.id),
                    "reference": payment.transaction_reference,
                    "provider_reference": payment.provider_reference,
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                    "status": payment.status,
                    "payment_type": payment.payment_type,
                    "milestone_id": None,
                },
                "proposal": {
                    "id": str(proposal.id),
                    "public_token": str(proposal.public_token),
                    "payment_total": str(proposal.payment_total),
                    "total_paid": str(proposal.total_paid),
                    "outstanding_balance": str(
                        proposal.outstanding_balance
                    ),
                    "payment_status": proposal.payment_status,
                },
                "paystack": {
                    "authorization_url": authorization_url,
                    "access_code": access_code,
                    "reference": (
                        paystack_response.get(
                            "reference",
                            payment.transaction_reference,
                        )
                    ),
                },
                # Convenience: some frontends look for checkout_url at
                # the top level.
                "checkout_url": authorization_url,
            },
            status=status.HTTP_201_CREATED,
        )






# ============================================================
# LIST ALL PAYMENTS FOR A PROPOSAL
# ============================================================

class ClientAllPaymentsListView(APIView):
    """
    Return every payment across every proposal the client owns.

        GET /api/payments/client/all/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        email = get_request_email(request)

        if not email:
            return Response(
                {"success": False, "error": "Unauthorized."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # All accepted/completed proposals for this email
        proposals = (
            Proposal.objects
            .filter(
                status__in=ALLOWED_PROPOSAL_STATUSES,
                lead__email__iexact=email,
            )
        )

        payments_qs = (
            ProposalPayment.objects
            .filter(proposal__in=proposals)
            .select_related("proposal", "milestone")
            .order_by("-created_at")
        )

        # Optional status filter
        status_filter = request.query_params.get("status")
        if status_filter:
            payments_qs = payments_qs.filter(status=status_filter)

        serialized = ProposalPaymentSerializer(
            payments_qs, many=True
        ).data

        # Attach proposal info to each payment for the UI
        proposal_map = {
            str(p.id): {
                "id": str(p.id),
                "public_token": str(p.public_token),
                "title": p.title,
                "currency": p.currency,
            }
            for p in proposals
        }

        for item in serialized:
            proposal_id = item.get("proposal_id")
            item["proposal"] = proposal_map.get(str(proposal_id))

        return Response(
            {
                "success": True,
                "count": len(serialized),
                "payments": serialized,
            }
        )


# ============================================================
# PAYMENT DETAIL
# ============================================================

class ClientProposalPaymentDetailView(APIView):
    """
    Return a single payment, including refund information and
    the milestone it belongs to (if any).

        GET /api/payments/client/<public_token>/payments/<payment_id>/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, public_token, payment_id):
        proposal = get_client_proposal(request, public_token)

        if not proposal:
            return Response(
                {"success": False, "error": "Proposal not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment = (
            ProposalPayment.objects
            .select_related("milestone", "proposal")
            .filter(id=payment_id, proposal=proposal)
            .first()
        )

        if not payment:
            return Response(
                {"success": False, "error": "Payment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serialized = ProposalPaymentSerializer(payment).data

        # Extra detail that isn't in the list serializer
        serialized["refundable_amount"] = str(
            payment.refundable_amount
        )
        serialized["refund_status"] = payment.refund_status
        serialized["refunded_at"] = (
            payment.refunded_at.isoformat()
            if payment.refunded_at else None
        )
        serialized["provider_response"] = payment.provider_response or {}

        return Response(
            {
                "success": True,
                "payment": serialized,
            }
        )