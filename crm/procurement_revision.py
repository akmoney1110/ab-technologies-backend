from decimal import Decimal

from django.db import transaction

from crm.models import (
    QuoteRequest,
    ProcurementClientRevision,
    ProcurementClientRevisionItem,
)


@transaction.atomic
def create_client_revision(quote):
    """
    Create a new client-editable revision from the latest
    quotation/revision.
    """

    previous = (
        quote.client_revisions
        .prefetch_related("items")
        .order_by("-revision_number")
        .first()
    )

    if previous:
        revision_number = (
            previous.revision_number + 1
        )

        revision = ProcurementClientRevision.objects.create(
            quote=quote,
            revision_number=revision_number,
            status="draft",
            discount=previous.discount,
            tax=previous.tax,
            delivery_fee=previous.delivery_fee,
            client_notes="",
        )

        source_items = previous.items.all()

        for item in source_items:
            ProcurementClientRevisionItem.objects.create(
                revision=revision,
                quotation_item=item.quotation_item,

                name=item.name,
                brand=item.brand,
                model=item.model,
                category=item.category,

                description=item.description,
                specifications=item.specifications,

                quantity=item.quantity,

                quoted_unit_price=(
                    item.quoted_unit_price
                ),

                proposed_unit_price=(
                    item.proposed_unit_price
                ),

                approved_unit_price=(
                    item.approved_unit_price
                ),

                total_price=(
                    item.total_price
                ),

                removed=item.removed,

                client_notes="",
                staff_notes=item.staff_notes,
            )

    else:
        revision = ProcurementClientRevision.objects.create(
            quote=quote,
            revision_number=1,
            status="draft",
            discount=quote.discount,
            tax=quote.tax,
            delivery_fee=quote.delivery_fee,
            client_notes="",
        )

        quotation_items = (
            quote.items
            .all()
            .order_by("created_at")
        )

        for item in quotation_items:
            quoted_price = (
                item.unit_price
                if item.unit_price is not None
                else Decimal("0.00")
            )

            total_price = (
                item.total_price
                if item.total_price is not None
                else Decimal("0.00")
            )

            ProcurementClientRevisionItem.objects.create(
                revision=revision,
                quotation_item=item,

                name=item.name,
                brand=item.brand,
                model=item.model,
                category=item.category,

                description=item.description,
                specifications=item.specifications,

                quantity=item.quantity,

                quoted_unit_price=quoted_price,

                proposed_unit_price=None,
                approved_unit_price=None,

                total_price=total_price,

                removed=False,

                client_notes="",
                staff_notes="",
            )

    revision.calculate_totals(save=True)

    return revision


def get_or_create_client_revision(quote):
    existing = (
        quote.client_revisions
        .filter(status="draft")
        .order_by("-revision_number")
        .first()
    )

    if existing:
        return existing

    return create_client_revision(quote)