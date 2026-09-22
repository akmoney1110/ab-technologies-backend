# payments/serializers.py

from decimal import Decimal

from rest_framework import serializers

from proposals.models import (
    ProposalMilestone,
    ProposalPayment,
)


SUCCESSFUL_PAYMENT_STATUSES = {
    "successful",
    "partially_refunded",
}


# ============================================================
# PAYMENT
# ============================================================


class ProposalPaymentSerializer(
    serializers.ModelSerializer
):
    amount_formatted = serializers.SerializerMethodField()

    status_label = serializers.SerializerMethodField()
    payment_type_label = serializers.SerializerMethodField()
    provider_label = serializers.SerializerMethodField()

    # NEW — so the frontend can build the correct URL
    proposal_id = serializers.SerializerMethodField()
    proposal_title = serializers.SerializerMethodField()

    milestone_id = serializers.SerializerMethodField()
    milestone_title = serializers.SerializerMethodField()
    milestone_order = serializers.SerializerMethodField()

    class Meta:
        model = ProposalPayment

        fields = [
            "id",

            # NEW
            "proposal_id",
            "proposal_title",

            "transaction_reference",
            "provider_reference",

            "payment_type",
            "payment_type_label",

            "provider",
            "provider_label",

            "amount",
            "amount_formatted",
            "currency",

            "status",
            "status_label",

            "refund_status",
            "refunded_amount",

            "milestone_id",
            "milestone_title",
            "milestone_order",

            "paid_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields

    def get_amount_formatted(self, obj):
        return obj.formatted_amount

    def get_status_label(self, obj):
        return obj.get_status_display()

    def get_payment_type_label(self, obj):
        return obj.get_payment_type_display()

    def get_provider_label(self, obj):
        return obj.get_provider_display()

    # --------------------------------------------------------
    # NEW — proposal fields
    # --------------------------------------------------------

    def get_proposal_id(self, obj):
        if not obj.proposal_id:
            return None

        return str(obj.proposal_id)

    def get_proposal_title(self, obj):
        if not obj.proposal:
            return None

        return obj.proposal.title

    # --------------------------------------------------------
    # Milestone fields
    # --------------------------------------------------------

    def get_milestone_id(self, obj):
        if not obj.milestone_id:
            return None

        return str(obj.milestone_id)

    def get_milestone_title(self, obj):
        if not obj.milestone:
            return None

        return obj.milestone.title

    def get_milestone_order(self, obj):
        if not obj.milestone:
            return None

        return obj.milestone.order



# ============================================================
# MILESTONE
# ============================================================

class ProposalMilestoneSerializer(
    serializers.ModelSerializer
):
    amount_formatted = serializers.SerializerMethodField()

    total_paid = serializers.SerializerMethodField()

    outstanding_balance = serializers.SerializerMethodField()

    payment_status = serializers.SerializerMethodField()

    is_paid = serializers.SerializerMethodField()

    can_pay = serializers.SerializerMethodField()

    class Meta:
        model = ProposalMilestone

        fields = [
            "id",

            "order",

            "title",
            "description",

            "amount",
            "amount_formatted",
            "percentage",

            "payment_required",

            "status",
            "payment_status",

            "total_paid",
            "outstanding_balance",

            "is_paid",
            "can_pay",

            "due_date",

            "deliverables",

            "started_at",
            "completed_at",

            "created_at",
            "updated_at",
        ]

        read_only_fields = fields

    # --------------------------------------------------------
    # INTERNAL HELPERS
    # --------------------------------------------------------

    def _payments(self, obj):
        """
        Use the prefetched payment list when available.
        """

        prefetched = getattr(
            obj,
            "_payment_objects",
            None,
        )

        if prefetched is not None:
            return prefetched

        return list(
            obj.payments.all()
        )

    def _direct_paid_total(self, obj):
        """
        Sum of successful payments that are DIRECTLY linked to
        this milestone.

        A full-balance payment (milestone=None) is NOT counted here.
        """

        total = Decimal("0.00")

        for payment in self._payments(obj):

            if payment.status not in SUCCESSFUL_PAYMENT_STATUSES:
                continue

            amount = (
                payment.amount
                or Decimal("0.00")
            )

            refunded = (
                payment.refunded_amount
                or Decimal("0.00")
            )

            total += max(
                Decimal("0.00"),
                amount - refunded,
            )

        return total

    def _effective_paid_total(self, obj):
        """
        Amount considered paid for this milestone.

        Priority:

        1. Direct payments linked to this milestone.
        2. If the milestone was explicitly marked 'paid' by the
           backend (e.g. after a full-balance payment), trust that
           and treat the milestone as fully covered.
        """

        amount = (
            obj.amount
            or Decimal("0.00")
        )

        direct = self._direct_paid_total(obj)

        if direct >= amount and amount > 0:
            return direct

        # Full-balance sync path: the milestone was marked paid
        # even though no direct payment is linked to it.
        if obj.payment_status == "paid":
            return amount if amount > 0 else direct

        return direct

    # --------------------------------------------------------
    # SERIALIZER FIELDS
    # --------------------------------------------------------

    def get_total_paid(self, obj):
        return str(
            self._effective_paid_total(obj)
        )

    def get_outstanding_balance(self, obj):
        amount = (
            obj.amount
            or Decimal("0.00")
        )

        paid = self._effective_paid_total(obj)

        outstanding = max(
            Decimal("0.00"),
            amount - paid,
        )

        return str(outstanding)

    def get_payment_status(self, obj):
        if not obj.payment_required:
            return "not_required"

        amount = (
            obj.amount
            or Decimal("0.00")
        )

        direct = self._direct_paid_total(obj)

        # Direct payments win.
        if direct >= amount and amount > 0:
            return "paid"

        if direct > Decimal("0.00"):
            return "partially_paid"

        # No direct payment. Trust the stored field if the backend
        # explicitly marked this milestone as paid/partially_paid.
        stored = (
            obj.payment_status or "unpaid"
        ).lower()

        if stored == "paid":
            return "paid"

        if stored == "partially_paid":
            return "partially_paid"

        if stored == "not_required":
            return "not_required"

        return "unpaid"

    def get_is_paid(self, obj):
        if not obj.payment_required:
            return False

        if obj.payment_status == "paid":
            return True

        amount = (
            obj.amount
            or Decimal("0.00")
        )

        return self._direct_paid_total(obj) >= amount

    def get_can_pay(self, obj):
        if not obj.payment_required:
            return False

        if obj.status in {
            "locked",
            "cancelled",
        }:
            return False

        if self.get_is_paid(obj):
            return False

        return True

    def get_amount_formatted(self, obj):
        return (
            f"{obj.proposal.currency} "
            f"{obj.amount:,.2f}"
        )


# ============================================================
# PAYMENT SUMMARY
# ============================================================

class ProposalPaymentSummarySerializer(
    serializers.Serializer
):
    proposal_total = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    total_paid = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    outstanding_balance = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    currency = serializers.CharField()

    status = serializers.CharField()

    proposal_total_formatted = (
        serializers.SerializerMethodField()
    )

    total_paid_formatted = (
        serializers.SerializerMethodField()
    )

    outstanding_balance_formatted = (
        serializers.SerializerMethodField()
    )

    def get_proposal_total_formatted(self, obj):
        return (
            f"{obj['currency']} "
            f"{obj['proposal_total']:,.2f}"
        )

    def get_total_paid_formatted(self, obj):
        return (
            f"{obj['currency']} "
            f"{obj['total_paid']:,.2f}"
        )

    def get_outstanding_balance_formatted(self, obj):
        return (
            f"{obj['currency']} "
            f"{obj['outstanding_balance']:,.2f}"
        )