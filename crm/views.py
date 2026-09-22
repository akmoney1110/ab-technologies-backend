from django.shortcuts import render

# Create your views here.
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    QuoteRequest,
    ProcurementClientRevision,
)

from .serializers import (
    ProcurementClientRevisionSerializer,
    ProcurementClientRevisionUpdateSerializer,
)

from .procurement_revision import (
    get_or_create_client_revision,
)


class ClientProcurementQuotationView(
    generics.GenericAPIView
):
    permission_classes = [IsAuthenticated]

    def get(self, request, quote_id):
        quote = get_object_or_404(
            QuoteRequest.objects
            .select_related("lead")
            .prefetch_related("items"),
            id=quote_id,
            lead__email=request.user.email,
            status__in=[
                "priced",
                "sent",
                "negotiation",
                "accepted",
            ],
        )

        serializer = ProcurementClientRevisionSerializer(
            get_or_create_client_revision(quote)
        )

        return Response(serializer.data)
    
class ClientProcurementRevisionView(
    generics.GenericAPIView
):
    permission_classes = [IsAuthenticated]

    def get_revision(
        self,
        request,
        revision_id,
    ):
        return get_object_or_404(
            ProcurementClientRevision.objects
            .select_related(
                "quote",
                "quote__lead",
            )
            .prefetch_related("items"),
            id=revision_id,
            quote__lead__email=request.user.email,
        )

    def get(self, request, revision_id):
        revision = self.get_revision(
            request,
            revision_id,
        )

        serializer = ProcurementClientRevisionSerializer(
            revision
        )

        return Response(serializer.data)

    def patch(self, request, revision_id):
        revision = self.get_revision(
            request,
            revision_id,
        )

        serializer = (
            ProcurementClientRevisionUpdateSerializer(
                revision,
                data=request.data,
                partial=True,
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        revision = serializer.save()

        return Response(
            ProcurementClientRevisionSerializer(
                revision
            ).data
        )



class ClientProcurementRevisionSubmitView(
    generics.GenericAPIView
):
    permission_classes = [IsAuthenticated]

    def post(self, request, revision_id):
        revision = get_object_or_404(
            ProcurementClientRevision.objects
            .select_related(
                "quote",
                "quote__lead",
            ),
            id=revision_id,
            quote__lead__email=request.user.email,
        )

        if revision.status != "draft":
            return Response(
                {
                    "detail": (
                        "This revision has already been submitted."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        active_items = revision.items.filter(
            removed=False
        )

        if not active_items.exists():
            return Response(
                {
                    "detail": (
                        "At least one item must remain "
                        "in the order."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        revision.calculate_totals(save=True)

        revision.status = "submitted"

        revision.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        # Move quotation into negotiation.
        quote = revision.quote

        if quote.status not in {
            "accepted",
            "rejected",
            "expired",
        }:
            quote.status = "negotiation"

            quote.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        return Response(
            ProcurementClientRevisionSerializer(
                revision
            ).data
        )        