from django.shortcuts import render

# Create your views here.
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Login successful.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "full_name": user.full_name,
                    "phone": user.phone,
                    "address": user.address,
                    "role": user.role,
                },
            },
            status=status.HTTP_200_OK,
        )
    

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Login successful.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "full_name": user.full_name,
                    "phone": user.phone,
                    "address": user.address,
                    "role": user.role,
                },
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        return Response(
            {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.full_name,
                "phone": user.phone,
                "address": user.address,
                "role": user.role,
                "is_active": user.is_active,
            }
        )


from django.db.models import Sum
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import OrganizationMember
from projects.models import Project
from proposals.models import Proposal
from procurement.models import ProcurementRequest
from invoices.models import Invoice
from support.models import SupportTicket


from django.db.models import Sum, Avg
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import OrganizationMember
from projects.models import Project
from proposals.models import Proposal
from procurement.models import ProcurementRequest
from invoices.models import Invoice
from support.models import SupportTicket

from learning.models import Enrollment

from django.db.models import Sum, Avg
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import OrganizationMember
from proposals.models import Proposal
from invoices.models import Invoice
from support.models import SupportTicket
from learning.models import Enrollment

from django.db.models import Avg, Sum

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from proposals.models import Proposal
from invoices.models import Invoice
from support.models import SupportTicket


from decimal import Decimal

from django.db.models import Avg, Prefetch, Sum
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status



from decimal import Decimal

from django.db.models import Avg, Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from crm.models import Lead, QuoteRequest, ProjectRequest, SupportTicket
from proposals.models import Proposal




class ClientDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    # ================================================================
    # CONSTANTS
    # ================================================================

    PROJECT_STATUSES = {
        "accepted",
        "completed",
    }

    PENDING_PROPOSAL_STATUSES = {
        "sent",
        "negotiation",
        "revision_requested",
        "viewed",
    }

    PROJECT_SOURCE = "project_request"
    PROCUREMENT_SOURCE = "quote_request"
    MANUAL_SOURCE = "manual"

    # ================================================================
    # PROPOSAL CLASSIFICATION
    # ================================================================

    def classify_proposal(self, proposal):
        """
        Determine the business type of a Proposal.

        IMPORTANT:
        Proposal.source is the authoritative classification.

        project_request -> project
        quote_request   -> procurement
        manual           -> manual

        We intentionally DO NOT infer the business type from
        QuoteRequest.request_type.
        """

        source = str(
            getattr(proposal, "source", "") or ""
        ).strip().lower()

        if source == self.PROJECT_SOURCE:
            return "project"

        if source == self.PROCUREMENT_SOURCE:
            return "procurement"

        if source == self.MANUAL_SOURCE:
            return "manual"

        return "manual"

    # ================================================================
    # PROJECT PROGRESS
    # ================================================================

    def calculate_project_progress(self, proposal):
        """
        Calculate project milestone completion percentage.

        Completed project:
            100%

        Accepted project with no milestones:
            0%

        Accepted project with milestones:
            completed / total * 100
        """

        if proposal.status == "completed":
            return 100

        milestones = proposal.milestones or []

        if not isinstance(milestones, list):
            return 0

        if not milestones:
            return 0

        completed_statuses = {
            "completed",
            "complete",
            "done",
        }

        completed_count = 0

        for milestone in milestones:

            if not isinstance(milestone, dict):
                continue

            milestone_status = str(
                milestone.get("status", "") or ""
            ).strip().lower()

            if milestone_status in completed_statuses:
                completed_count += 1

        total = len(milestones)

        if total <= 0:
            return 0

        progress = round(
            (completed_count / total) * 100
        )

        return min(
            max(progress, 0),
            100,
        )

    # ================================================================
    # PROJECT MILESTONES
    # ================================================================

    def serialize_milestones(self, proposal):
        """
        Return client-safe milestone information.
        """

        milestones = proposal.milestones or []

        if not isinstance(milestones, list):
            return []

        result = []

        for index, milestone in enumerate(milestones):

            if not isinstance(milestone, dict):
                continue

            result.append(
                {
                    "id": milestone.get(
                        "id",
                        index + 1,
                    ),

                    "title": milestone.get(
                        "title",
                        milestone.get(
                            "name",
                            f"Milestone {index + 1}",
                        ),
                    ),

                    "description": milestone.get(
                        "description",
                        "",
                    ),

                    "status": str(
                        milestone.get(
                            "status",
                            "pending",
                        )
                    ).lower(),

                    "completed": (
                        str(
                            milestone.get(
                                "status",
                                "",
                            )
                        ).lower()
                        in {
                            "completed",
                            "complete",
                            "done",
                        }
                    ),
                }
            )

        return result

    # ================================================================
    # PROCUREMENT ITEM
    # ================================================================

    def serialize_procurement_item(self, item):
        """
        Serialize a procurement quotation item.
        """

        quantity = int(
            item.quantity or 0
        )

        product_name = " ".join(
            str(part).strip()
            for part in [
                item.brand,
                item.name,
                item.model,
            ]
            if part
        )

        return {
            "id": str(item.id),

            "category": item.category,

            "name": item.name,

            "brand": item.brand,

            "model": item.model,

            "description": item.description,

            "specifications": (
                item.specifications
                if isinstance(
                    item.specifications,
                    dict,
                )
                else {}
            ),

            "quantity": quantity,

            "included": quantity > 0,

            "unit_price": (
                str(item.unit_price)
                if item.unit_price is not None
                else None
            ),

            "total_price": (
                str(item.total_price)
                if item.total_price is not None
                else None
            ),

            "display_name": (
                f"{quantity} × {product_name}"
                if quantity > 0
                else product_name
            ),
        }

    # ================================================================
    # PROCUREMENT SERIALIZATION
    # ================================================================

    def serialize_procurement(self, proposal):
        """
        Serialize a procurement Proposal.

        Procurement proposals are Proposal objects whose source is
        'quote_request'.
        """

        quote = getattr(
            proposal,
            "quote_request",
            None,
        )

        items = []

        if quote:

            items = [
                self.serialize_procurement_item(item)
                for item in quote.items.all().order_by(
                    "created_at"
                )
            ]

        included_items = [
            item
            for item in items
            if item["included"]
        ]

        removed_items = [
            item
            for item in items
            if not item["included"]
        ]

        total_quantity = sum(
            item["quantity"]
            for item in included_items
        )

        return {
            "id": str(proposal.id),

            "code": str(
                proposal.id
            )[:8].upper(),

            "name": proposal.title,

            "title": proposal.title,

            "type": "procurement",

            "business_type": "procurement",

            "source": proposal.source,

            "request_type": (
                quote.request_type
                if quote
                else None
            ),

            "description": (
                quote.description
                if quote
                else ""
            ),

            "purpose": (
                quote.purpose
                if quote
                else ""
            ),

            "notes": (
                quote.notes
                if quote
                else ""
            ),

            "status": proposal.status,

            "version": proposal.version,

            "currency": (
                proposal.currency
                or (
                    quote.currency
                    if quote
                    else "NGN"
                )
            ),

            "total_price": str(
                proposal.total_price
                or Decimal("0.00")
            ),

            "accepted_at": proposal.accepted_at,

            "created_at": proposal.created_at,

            "updated_at": proposal.updated_at,

            "items": items,

            "included_items": included_items,

            "removed_items": removed_items,

            "item_count": len(
                included_items
            ),

            "total_item_count": len(
                items
            ),

            "total_quantity": total_quantity,

            "is_active": (
                proposal.status == "accepted"
            ),

            "is_completed": (
                proposal.status == "completed"
            ),
        }

    # ================================================================
    # PROJECT SERIALIZATION
    # ================================================================

    def serialize_project(self, proposal):
        """
        Serialize a software/service project.

        Project proposals are Proposal objects whose source is
        'project_request'.
        """

        project_request = getattr(
            proposal,
            "project_request",
            None,
        )

        progress = (
            self.calculate_project_progress(
                proposal
            )
        )

        milestones = (
            self.serialize_milestones(
                proposal
            )
        )

        return {
            "id": str(proposal.id),

            "code": str(
                proposal.id
            )[:8].upper(),

            "name": proposal.title,

            "title": proposal.title,

            "type": "project",

            "business_type": "project",

            "source": proposal.source,

            "request_type": (
                project_request.project_type
                if project_request
                else None
            ),

            "project_type": (
                project_request.project_type
                if project_request
                else None
            ),

            "description": (
                project_request.description
                if project_request
                else proposal.client_summary
            ),

            "status": proposal.status,

            "version": proposal.version,

            "currency": proposal.currency,

            "total_price": str(
                proposal.total_price
                or Decimal("0.00")
            ),

            "accepted_at": proposal.accepted_at,

            "created_at": proposal.created_at,

            "updated_at": proposal.updated_at,

            "progress": progress,

            "milestones": milestones,

            "milestone_count": len(
                milestones
            ),

            "completed_milestones": sum(
                1
                for milestone in milestones
                if milestone["completed"]
            ),

            "is_active": (
                proposal.status == "accepted"
            ),

            "is_completed": (
                proposal.status == "completed"
            ),
        }

    # ================================================================
    # PENDING PROPOSAL SERIALIZATION
    # ================================================================

    def serialize_pending_proposal(self, proposal):
        """
        Serialize a proposal that has not yet become active work.
        """

        proposal_type = self.classify_proposal(
            proposal
        )

        quote = getattr(
            proposal,
            "quote_request",
            None,
        )

        project_request = getattr(
            proposal,
            "project_request",
            None,
        )

        if proposal_type == "procurement":

            request_type = (
                quote.request_type
                if quote
                else None
            )

        elif proposal_type == "project":

            request_type = (
                project_request.project_type
                if project_request
                else None
            )

        else:

            request_type = None

        return {
            "id": str(proposal.id),

            "code": str(
                proposal.id
            )[:8].upper(),

            "title": proposal.title,

            "name": proposal.title,

            "type": proposal_type,

            "business_type": proposal_type,

            "source": proposal.source,

            "request_type": request_type,

            "status": proposal.status,

            "version": proposal.version,

            "total_price": str(
                proposal.total_price
                or Decimal("0.00")
            ),

            "currency": proposal.currency,

            "created_at": proposal.created_at,

            "updated_at": proposal.updated_at,

            "expires_at": proposal.expires_at,

            "sent_at": proposal.sent_at,

            "viewed_at": proposal.viewed_at,
        }

    # ================================================================
    # GET
    # ================================================================

    def get(self, request):

        user = request.user

        # ============================================================
        # CLIENT ACCESS
        # ============================================================

        user_role = getattr(
            user,
            "role",
            None,
        )

        client_role = getattr(
            getattr(
                user,
                "Role",
                None,
            ),
            "CLIENT",
            None,
        )

        if client_role is not None:

            if user_role != client_role:
                return Response(
                    {
                        "detail": (
                            "This dashboard is only "
                            "available to clients."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # ============================================================
        # ORGANIZATION
        # ============================================================

        organization = getattr(
            user,
            "organization",
            None,
        )

        # ============================================================
        # PROPOSALS
        # ============================================================
        #
        # IMPORTANT:
        #
        # Do not filter by accepted here.
        #
        # We need pending proposals as well.
        #
        # Classification is based on Proposal.source.
        #
        # ============================================================

        proposals = (
            Proposal.objects
            .filter(
                lead__email=user.email,
            )
            .select_related(
                "lead",
                "organization",
                "project_request",
                "quote_request",
            )
            .prefetch_related(
                "quote_request__items",
            )
            .order_by(
                "-updated_at",
            )
        )

        # ============================================================
        # ACCEPTED / COMPLETED
        # ============================================================

        business_proposals = [
            proposal
            for proposal in proposals
            if proposal.status
            in self.PROJECT_STATUSES
        ]

        # ============================================================
        # SEPARATE BUSINESS TYPES
        # ============================================================

        project_proposals = [
            proposal
            for proposal in business_proposals
            if self.classify_proposal(
                proposal
            ) == "project"
        ]

        procurement_proposals = [
            proposal
            for proposal in business_proposals
            if self.classify_proposal(
                proposal
            ) == "procurement"
        ]

        manual_proposals = [
            proposal
            for proposal in business_proposals
            if self.classify_proposal(
                proposal
            ) == "manual"
        ]

        # ============================================================
        # PROJECT STATUS GROUPS
        # ============================================================

        active_project_proposals = [
            proposal
            for proposal in project_proposals
            if proposal.status == "accepted"
        ]

        completed_project_proposals = [
            proposal
            for proposal in project_proposals
            if proposal.status == "completed"
        ]

        # ============================================================
        # PROCUREMENT STATUS GROUPS
        # ============================================================

        active_procurement_proposals = [
            proposal
            for proposal in procurement_proposals
            if proposal.status == "accepted"
        ]

        completed_procurement_proposals = [
            proposal
            for proposal in procurement_proposals
            if proposal.status == "completed"
        ]

        # ============================================================
        # PENDING PROPOSALS
        # ============================================================

        pending_proposals = [
            proposal
            for proposal in proposals
            if proposal.status
            in self.PENDING_PROPOSAL_STATUSES
        ][:10]

        pending_proposal_list = [
            self.serialize_pending_proposal(
                proposal
            )
            for proposal in pending_proposals
        ]

        # ============================================================
        # PROJECT LIST
        # ============================================================

        project_list = [
            self.serialize_project(
                proposal
            )
            for proposal in project_proposals[:5]
        ]

        # ============================================================
        # PROCUREMENT LIST
        # ============================================================

        procurement_list = [
            self.serialize_procurement(
                proposal
            )
            for proposal in procurement_proposals[:5]
        ]

        # ============================================================
        # MANUAL PROPOSALS
        # ============================================================

        manual_list = [
            self.serialize_pending_proposal(
                proposal
            )
            for proposal in manual_proposals[:5]
        ]

        # ============================================================
        # RECENT WORK
        # ============================================================

        recent_work = (
            project_list
            + procurement_list
        )

        recent_work.sort(
            key=lambda item: (
                item.get("updated_at")
                or ""
            ),
            reverse=True,
        )

        recent_work = recent_work[:8]

        # ============================================================
        # INVOICES
        # ============================================================

        invoices = Invoice.objects.filter(
            organization=organization,
        )

        invoice_totals = invoices.aggregate(
            total=Sum("amount"),
            paid=Sum("amount_paid"),
        )

        invoice_total = (
            invoice_totals["total"]
            or Decimal("0.00")
        )

        invoice_paid = (
            invoice_totals["paid"]
            or Decimal("0.00")
        )

        outstanding = (
            invoice_total
            - invoice_paid
        )

        if outstanding < Decimal("0.00"):
            outstanding = Decimal("0.00")

        # ============================================================
        # SUPPORT
        # ============================================================

        support_tickets = (
            SupportTicket.objects.filter(
                
            )
        )

        open_support = (
            support_tickets.filter(
                status__in=[
                    
                    
                ],
            )
        )

        support_list = [
            {
                "id": ticket.id,

                "title": getattr(
                    ticket,
                    "title",
                    getattr(
                        ticket,
                        "subject",
                        "",
                    ),
                ),

                "status": ticket.status,

                "priority": ticket.priority,

                "updated_at": (
                    ticket.updated_at
                ),
            }
            for ticket in (
                open_support
                .order_by(
                    "-updated_at"
                )[:5]
            )
        ]

        # ============================================================
        # TRAINING
        # ============================================================

        enrollments = (
            Enrollment.objects
            .select_related(
                "course",
                "course__category",
                "course__instructor",
            )
            .filter(
                user=user,
            )
        )

        active_enrollments = (
            enrollments.filter(
                status__in=[
                    Enrollment.Status.ENROLLED,
                    Enrollment.Status.IN_PROGRESS,
                ],
            )
        )

        completed_enrollments = (
            enrollments.filter(
                status=Enrollment.Status.COMPLETED,
            )
        )

        training_average = (
            enrollments.aggregate(
                average=Avg(
                    "progress_percentage"
                ),
            )["average"]
            or 0
        )

        # ============================================================
        # TRAINING LIST
        # ============================================================

        training_courses = []

        for enrollment in (
            enrollments
            .order_by(
                "-enrolled_at"
            )[:6]
        ):

            certificate_data = None

            try:
                certificate = (
                    enrollment.certificate
                )
            except Exception:
                certificate = None

            if certificate:

                certificate_data = {
                    "id": certificate.id,

                    "certificate_number": (
                        certificate.certificate_number
                    ),

                    "verification_code": (
                        certificate.verification_code
                    ),

                    "issued_at": (
                        certificate.issued_at
                    ),

                    "is_valid": (
                        certificate.is_valid
                    ),
                }

            course = enrollment.course

            training_courses.append(
                {
                    "id": course.id,

                    "enrollment_id": (
                        enrollment.id
                    ),

                    "title": course.title,

                    "slug": course.slug,

                    "short_description": (
                        course.short_description
                    ),

                    "category": (
                        course.category.name
                        if course.category
                        else None
                    ),

                    "difficulty": course.difficulty,

                    "course_type": (
                        course.course_type
                    ),

                    "duration_hours": (
                        course.duration_hours
                    ),

                    "status": enrollment.status,

                    "progress": (
                        enrollment.progress_percentage
                    ),

                    "enrolled_at": (
                        enrollment.enrolled_at
                    ),

                    "started_at": (
                        enrollment.started_at
                    ),

                    "completed_at": (
                        enrollment.completed_at
                    ),

                    "expires_at": (
                        enrollment.expires_at
                    ),

                    "certificate": certificate_data,
                }
            )

        # ============================================================
        # ORGANIZATION DATA
        # ============================================================

        organization_data = {}

        if organization:

            organization_data = {
                "id": getattr(
                    organization,
                    "id",
                    None,
                ),

                "name": getattr(
                    organization,
                    "name",
                    None,
                ),
            }

        # ============================================================
        # USER DATA
        # ============================================================

        full_name = ""

        get_full_name = getattr(
            user,
            "get_full_name",
            None,
        )

        if callable(get_full_name):
            full_name = get_full_name()

        user_data = {
            "id": user.id,

            "name": (
                full_name
                or getattr(
                    user,
                    "name",
                    None,
                )
                or user.email
            ),

            "email": user.email,

            "role": str(
                getattr(
                    user,
                    "role",
                    "",
                )
            ),

            "company": getattr(
                user,
                "company",
                None,
            ),
        }

        # ============================================================
        # RESPONSE
        # ============================================================

        return Response(
            {
                # ====================================================
                # ORGANIZATION
                # ====================================================

                "organization": organization_data,

                # ====================================================
                # USER
                # ====================================================

                "user": user_data,

                # ====================================================
                # STATISTICS
                # ====================================================

                "statistics": {

                    # PROJECTS
                    "active_projects": len(
                        active_project_proposals
                    ),

                    "completed_projects": len(
                        completed_project_proposals
                    ),

                    "total_projects": len(
                        project_proposals
                    ),

                    # PROCUREMENT
                    "active_procurements": len(
                        active_procurement_proposals
                    ),

                    "completed_procurements": len(
                        completed_procurement_proposals
                    ),

                    "total_procurements": len(
                        procurement_proposals
                    ),

                    # MANUAL
                    "manual_proposals": len(
                        manual_proposals
                    ),

                    # PENDING
                    "proposals": len(
                        pending_proposal_list
                    ),

                    "pending_proposals": len(
                        pending_proposal_list
                    ),

                    # SUPPORT
                    "open_support": (
                        open_support.count()
                    ),

                    # BILLING
                    "outstanding_invoices": (
                        outstanding
                    ),

                    "invoice_count": (
                        invoices.count()
                    ),

                    # TRAINING
                    "enrolled_courses": (
                        enrollments.count()
                    ),

                    "active_courses": (
                        active_enrollments.count()
                    ),

                    "completed_courses": (
                        completed_enrollments.count()
                    ),

                    "training_progress": round(
                        float(
                            training_average
                        ),
                        2,
                    ),
                },

                # ====================================================
                # PROJECTS
                # ====================================================

                "projects": project_list,

                # ====================================================
                # PROCUREMENT
                # ====================================================

                "procurements": procurement_list,

                # ====================================================
                # MANUAL
                # ====================================================

                "manual_proposals": manual_list,

                # ====================================================
                # RECENT WORK
                # ====================================================

                "recent_work": recent_work,

                # ====================================================
                # PENDING PROPOSALS
                # ====================================================

                "proposals": pending_proposal_list,

                # ====================================================
                # SUPPORT
                # ====================================================

                "support": support_list,

                # ====================================================
                # INVOICES
                # ====================================================

                "invoices": [
                    {
                        "id": invoice.id,

                        "amount": invoice.amount,

                        "amount_paid": (
                            invoice.amount_paid
                        ),

                        "outstanding": max(
                            (
                                invoice.amount
                                or Decimal("0.00")
                            )
                            -
                            (
                                invoice.amount_paid
                                or Decimal("0.00")
                            ),
                            Decimal("0.00"),
                        ),

                        "created_at": (
                            invoice.created_at
                        ),
                    }
                    for invoice in (
                        invoices
                        .order_by(
                            "-created_at"
                        )[:5]
                    )
                ],

                # ====================================================
                # TRAINING
                # ====================================================

                "training": {

                    "statistics": {

                        "total_courses": (
                            enrollments.count()
                        ),

                        "active_courses": (
                            active_enrollments.count()
                        ),

                        "completed_courses": (
                            completed_enrollments.count()
                        ),

                        "average_progress": round(
                            float(
                                training_average
                            ),
                            2,
                        ),
                    },

                    "courses": training_courses,
                },
            }
        )