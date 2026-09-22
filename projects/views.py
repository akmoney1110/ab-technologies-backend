from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from proposals.models import Proposal
from .serializers import ProjectSerializer

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from proposals.models import Proposal
from .serializers import ProjectSerializer


# ============================================================
# CLIENT PROJECT QUERYSET
# ============================================================

class ClientProjectQuerySetMixin:
    """
    Returns ONLY actual software/service projects.

    Important:
    - project_request = actual project
    - quote_request = procurement
    - manual = manually created proposal / other

    Accepted and completed projects remain visible.
    """

    PROJECT_SOURCE = "project_request"

    PROJECT_STATUSES = [
        "accepted",
        "completed",
    ]

    def get_queryset(self):
        user = self.request.user

        user_email = (
            str(getattr(user, "email", "") or "")
            .strip()
            .lower()
        )

        if not user_email:
            return Proposal.objects.none()

        return (
            Proposal.objects
            .filter(
                source=self.PROJECT_SOURCE,
                status__in=self.PROJECT_STATUSES,
                lead__email__iexact=user_email,
                project_request__isnull=False,
            )
            .select_related(
                "lead",
                "organization",
                "project_request",
                "client_content",
            )
            .order_by("-updated_at")
        )


# ============================================================
# CLIENT PROJECT LIST
# ============================================================

class ClientProjectListView(
    ClientProjectQuerySetMixin,
    generics.ListAPIView,
):
    """
    Lists the client's actual projects.

    Procurement quotations are excluded because their
    Proposal.source is "quote_request".
    """

    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

class ClientProjecDetailView(
    ClientProjectQuerySetMixin,
    generics.RetrieveAPIView,
):
    """
    Return one accepted proposal as a project.
    """

    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from proposals.models import Proposal

from .serializers import ProjectSerializer

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from proposals.models import Proposal

from .serializers import ProjectSerializer


class ClientProjectDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, proposal_id):
        try:
            proposal = (
                Proposal.objects
                .select_related("client_content")
                .prefetch_related("client_content__files")
                .get(
                    id=proposal_id,
                    status__in=["accepted", "completed"],
                    lead__email=request.user.email,
                )
            )

        except Proposal.DoesNotExist:
            return Response(
                {"detail": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProjectSerializer(
            proposal,
            context={"request": request},
        )

        return Response(serializer.data)



# crm/views.py

from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from crm.models import QuoteRequest
from ai.quoteproposal import (
    generate_and_create_quote_proposal,
)

from projects.permissions import IsStaffOrAdmin
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from proposals.models import Proposal

from .permissions import IsStaffOrAdmin

class GenerateQuoteProposalView(
    generics.GenericAPIView
):
    permission_classes = [
        IsAuthenticated,
        IsStaffOrAdmin,
    ]

    def post(
        self,
        request,
        quote_id,
    ):
        quote = get_object_or_404(
            QuoteRequest,
            id=quote_id,
        )

        # ====================================================
        # VALIDATE
        # ====================================================

        if quote.status != "priced":

            return Response(
                {
                    "success": False,
                    "detail": (
                        "This quotation must be fully "
                        "priced before a proposal can "
                        "be generated."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ====================================================
        # GENERATE
        # ====================================================

        try:

            proposal = (
                generate_and_create_quote_proposal(
                    quote_id=quote.id,
                    created_by=request.user,
                )
            )

        except ValueError as exc:

            return Response(
                {
                    "success": False,
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:

            import logging

            logging.getLogger(
                __name__
            ).exception(
                "Failed to generate proposal "
                "from quote %s",
                quote.id,
            )

            return Response(
                {
                    "success": False,
                    "detail": (
                        "The proposal could not be "
                        "generated. Please try again."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "success": True,

                "proposal": {
                    "id": str(
                        proposal.id
                    ),

                    "title": proposal.title,

                    "status": proposal.status,

                    "version": proposal.version,

                    "currency": proposal.currency,

                    "total_price": str(
                        proposal.total_price
                    ),

                    "quote_request_id": str(
                        quote.id
                    ),
                },
            },

            status=status.HTTP_201_CREATED,
        )
    





class StaffProjectListView(generics.GenericAPIView):
    permission_classes = [
        IsAuthenticated,
        IsStaffOrAdmin,
    ]

    def get(self, request):
        proposals = (
            Proposal.objects
            .filter(status__in=["accepted", "completed"],)
            .select_related("lead")
            .order_by("-updated_at")
        )

        projects = [
            self.serialize_project(proposal)
            for proposal in proposals
        ]

        return Response(projects)

    @staticmethod
    def normalize_milestones(milestones):
        """
        Ensure every milestone has a stable integer ID.
        """
        normalized = []

        for index, milestone in enumerate(
            milestones or [],
            start=1,
        ):
            milestone = dict(milestone)

            if not milestone.get("id"):
                milestone["id"] = index

            normalized.append(milestone)

        return normalized

    @classmethod
    def serialize_project(cls, proposal):
        milestones = cls.normalize_milestones(
            proposal.milestones
        )

        completed = sum(
            1
            for milestone in milestones
            if str(
                milestone.get("status", "")
            ).lower()
            in {
                "completed",
                "complete",
                "done",
            }
        )

        total = len(milestones)

        progress = (
            round((completed / total) * 100)
            if total
            else 0
        )

        return {
            "id": str(proposal.id),

            "project_id": str(proposal.id),

            "project_code": (
                f"PROJ-{str(proposal.id)[:8].upper()}"
            ),

            "title": proposal.title,

            "client": (
                str(proposal.lead)
                if proposal.lead
                else "Unknown Client"
            ),

            "status": proposal.status,

            "version": proposal.version,

            "value": (
                str(proposal.total_price)
                if getattr(
                    proposal,
                    "total_price",
                    None,
                ) is not None
                else None
            ),

            "client_summary": proposal.client_summary,

            "scope": proposal.scope,

            "pages": proposal.pages,

            "features": proposal.features,

            "authentication": proposal.authentication,

            "integrations": proposal.integrations,

            "mobile": proposal.mobile,

            "backend": proposal.backend,

            "devops": proposal.devops,

            "technical_scope": proposal.technical_scope,

            "deliverables": proposal.deliverables,

            "assumptions": proposal.assumptions,

            "exclusions": proposal.exclusions,

            "timeline": proposal.timeline,

            "milestones": milestones,

            "progress": progress,

            "milestone_count": total,

            "completed_milestone_count": completed,

            "accepted_at": proposal.accepted_at,

            "created_at": proposal.created_at,

            "updated_at": proposal.updated_at,
        }

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from proposals.models import Proposal
from .permissions import IsStaffOrAdmin
from .serializers import ProjectSerializer


class StaffProjectDetailView(generics.GenericAPIView):
    permission_classes = [
        IsAuthenticated,
        IsStaffOrAdmin,
    ]

    def get(
        self,
        request,
        proposal_id,
    ):
        try:
            proposal = (
                Proposal.objects
                .select_related(
                    "lead",
                    "client_content",
                )
                .prefetch_related(
                    "client_content__files",
                )
                .get(
                    id=proposal_id,
                    status__in=[
                        "accepted",
                        "completed",
                    ],
                )
            )

        except Proposal.DoesNotExist:
            return Response(
                {
                    "detail": "Project not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProjectSerializer(
            proposal,
            context={
                "request": request,
            },
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class StaffProjectMilestoneUpdateView(
    generics.GenericAPIView
):
    permission_classes = [
        IsAuthenticated,
        IsStaffOrAdmin,
    ]

    ALLOWED_STATUSES = {
        "pending",
        "in_progress",
        "completed",
    }

    def patch(
        self,
        request,
        proposal_id,
        milestone_id,
    ):
        try:
            proposal = (
                Proposal.objects
                .get(
    id=proposal_id,
    status__in=["accepted", "completed"],
)
                )
            

        except Proposal.DoesNotExist:
            return Response(
                {
                    "detail": "Project not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Normalize milestones first.
        milestones = (
            StaffProjectListView
            .normalize_milestones(
                proposal.milestones
            )
        )

        # Find requested milestone.
        milestone = next(
            (
                item
                for item in milestones
                if str(item.get("id"))
                == str(milestone_id)
            ),
            None,
        )

        if milestone is None:
            return Response(
                {
                    "detail": "Milestone not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = str(
            request.data.get(
                "status",
                "",
            )
        ).strip().lower()

        if (
            new_status
            not in self.ALLOWED_STATUSES
        ):
            return Response(
                {
                    "detail": (
                        "Invalid milestone status."
                    ),
                    "allowed_statuses": [
                        "pending",
                        "in_progress",
                        "completed",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update milestone.
        milestone["status"] = new_status

        # Save normalized milestones back
        # to the proposal.
        proposal.milestones = milestones

        proposal.save(
            update_fields=[
                "milestones",
                "updated_at",
            ]
        )
        proposal.check_and_mark_completed()

        # Recalculate progress.
        completed = sum(
            1
            for item in milestones
            if str(
                item.get("status", "")
            ).lower()
            in {
                "completed",
                "complete",
                "done",
            }
        )

        total = len(milestones)

        progress = (
            round(
                (completed / total) * 100
            )
            if total
            else 0
        )

        return Response(
            {
                "message": (
                    "Milestone updated successfully."
                ),

                "proposal_id": str(
                    proposal.id
                ),

                "milestone": milestone,

                "progress": progress,

                "completed_milestones": (
                    completed
                ),

                "total_milestones": total,
            }
        )
    


# proposals/views.py

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from proposals.models import Proposal, ProposalComment
from .serializers import ProposalCommentSerializer



class ProjectCommentListCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, proposal_id):
        comments = (
            ProposalComment.objects
            .filter(
                proposal_id=proposal_id,
                action="comment",
            )
            .order_by("created_at")
        )

        serializer = ProposalCommentSerializer(
            comments,
            many=True,
        )

        return Response(serializer.data)

    def post(self, request, proposal_id):
        try:
            proposal = Proposal.objects.get(
                id=proposal_id,
                status="accepted",
            )
        except Proposal.DoesNotExist:
            return Response(
                {"detail": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        milestone_id = request.data.get("milestone_id")
        message = str(
            request.data.get("message", "")
        ).strip()

        if not message:
            return Response(
                {"detail": "Comment message is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = ProposalComment.objects.create(
            proposal=proposal,
            milestone_id=milestone_id,
            message=message,
            action="comment",
            author_type="client",
        )

        serializer = ProposalCommentSerializer(comment)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )


from proposals.models import (
    Proposal,
    ProposalUpdate,
    ProposalUpdateFile,
)

from .serializers import (
    ProposalUpdateSerializer,
    ProposalUpdateFileSerializer,
)



class StaffProjectUpdateCreateView(generics.GenericAPIView):
    permission_classes = [
        IsAuthenticated,
        IsStaffOrAdmin,
    ]

    def post(self, request, proposal_id):
        try:
            proposal = Proposal.objects.get(
    id=proposal_id,
    status__in=["accepted", "completed"],
)
        except Proposal.DoesNotExist:
            return Response(
                {"detail": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        title = str(
            request.data.get("title", "")
        ).strip()

        description = str(
            request.data.get("description", "")
        ).strip()

        milestone_id = request.data.get("milestone_id")

        if not title:
            return Response(
                {"detail": "Update title is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        update = ProposalUpdate.objects.create(
            proposal=proposal,
            milestone_id=milestone_id,
            title=title,
            description=description,
            created_by=request.user,
        )

        serializer = ProposalUpdateSerializer(update)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )
    



class StaffProjectUpdateFileUploadView(generics.GenericAPIView):
    permission_classes = [
        IsAuthenticated,
        IsStaffOrAdmin,
    ]

    def post(self, request, proposal_id, update_id):
        try:
            update = ProposalUpdate.objects.select_related(
                "proposal"
            ).get(
                id=update_id,
                proposal_id=proposal_id,
                proposal__status__in=["accepted", "completed"],
            )
        except ProposalUpdate.DoesNotExist:
            return Response(
                {"detail": "Project update not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            return Response(
                {"detail": "File is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        update_file = ProposalUpdateFile.objects.create(
            update=update,
            file=uploaded_file,
            original_name=uploaded_file.name,
        )

        serializer = ProposalUpdateFileSerializer(
            update_file
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )
        




class ProjectUpdateListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, proposal_id):
        updates = (
    ProposalUpdate.objects
    .filter(
        proposal_id=proposal_id,
        proposal__status__in=["accepted", "completed"],
    )
    .prefetch_related("files")
    .order_by("-created_at")
)

        serializer = ProposalUpdateSerializer(
            updates,
            many=True,
        )

        return Response(serializer.data)






from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from proposals.models import Proposal

from .models import ClientProjectContent
from .serializers import ClientProjectContentSerializer

from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from proposals.models import Proposal

from .models import ClientProjectContent
from .serializers import ClientProjectContentSerializer,ClientProjectContentFileSerializer


class ClientProjectContentView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ClientProjectContentSerializer

    def get_proposal(self, request, proposal_id):
        print("====================================")
        print("CONTENT REQUEST")
        print("proposal_id:", proposal_id)
        print("user:", request.user)
        print("user email:", request.user.email)

        try:
            proposal = Proposal.objects.select_related("lead").get(
                id=proposal_id
            )
        except Proposal.DoesNotExist:
            print("❌ PROPOSAL DOES NOT EXIST")
            return None

        print("proposal found:", proposal.id)
        print("proposal status:", proposal.status)

        lead = getattr(proposal, "lead", None)

        if lead:
            print("proposal lead:", lead)
            print("proposal lead email:", getattr(lead, "email", None))
        else:
            print("❌ PROPOSAL HAS NO LEAD")

        print("====================================")

        # Authorization
        if lead and lead.email == request.user.email:
            return proposal

        # If the authenticated user is staff/admin,
        # allow them to access the project too.
        if (
            getattr(request.user, "is_staff", False)
            or getattr(request.user, "is_superuser", False)
        ):
            return proposal

        role = str(getattr(request.user, "role", "") or "").upper()

        if role in {"ADMIN", "MANAGER", "STAFF"}:
            return proposal

        return None

    def get_content(self, proposal):
        content, created = ClientProjectContent.objects.get_or_create(
            proposal=proposal
        )

        if created:
            print("✅ Created ClientProjectContent:", content.id)
        else:
            print("✅ Existing ClientProjectContent:", content.id)

        return content

    def get(self, request, proposal_id):
        proposal = self.get_proposal(request, proposal_id)

        if proposal is None:
            return Response(
                {"detail": "Project not found or you do not have access."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if str(proposal.status).lower() not in {"accepted", "completed"}:
            return Response(
                {"detail": "Only accepted or completed projects have client content."},
                status=status.HTTP_404_NOT_FOUND,
            )

        content = self.get_content(proposal)

        serializer = self.get_serializer(
            content,
            context={"request": request},
        )

        return Response(serializer.data)

    def patch(self, request, proposal_id):
        proposal = self.get_proposal(request, proposal_id)

        if proposal is None:
            return Response(
                {"detail": "Project not found or you do not have access."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if str(proposal.status).lower() not in {"accepted", "completed"}:
            return Response(
                {"detail": "Only accepted or completed projects can have client content."},
                status=status.HTTP_404_NOT_FOUND,
            )

        content = self.get_content(proposal)

        serializer = self.get_serializer(
            content,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        if not serializer.is_valid():
            print("❌ CLIENT CONTENT VALIDATION ERROR:")
            print(serializer.errors)

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()

        print("✅ CLIENT CONTENT SAVED")

        return Response(serializer.data)
    




class ClientProjectContentFileUploadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ClientProjectContentFileSerializer

    def get_proposal(self, request, proposal_id):
        return get_object_or_404(
            Proposal,
            id=proposal_id,
            status__in=["accepted", "completed"],
            lead__email=request.user.email,
        )

    def post(self, request, proposal_id):
        proposal = self.get_proposal(request, proposal_id)

        content, _ = ClientProjectContent.objects.get_or_create(
            proposal=proposal
        )

        serializer = self.get_serializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        file_obj = serializer.save(content=content)

        return Response(
            self.get_serializer(file_obj).data,
            status=status.HTTP_201_CREATED,
        )    






