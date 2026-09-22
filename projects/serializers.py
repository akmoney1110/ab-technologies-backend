from rest_framework import serializers

from proposals.models import (
    Proposal,
    ProposalComment,
    ProposalUpdate,
    ProposalUpdateFile,
)

from projects.models import (
    ClientProjectContent,
    ClientProjectContentFile,
)


# ============================================================
# PROPOSAL COMMENTS
# ============================================================

class ProposalCommentSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = ProposalComment

        fields = [
            "id",
            "proposal",
            "milestone_id",
            "message",
            "action",
            "author_type",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "author_type",
            "action",
        ]


# ============================================================
# PROPOSAL UPDATE FILES
# ============================================================

class ProposalUpdateFileSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = ProposalUpdateFile

        fields = [
            "id",
            "file",
            "original_name",
            "uploaded_at",
        ]

        read_only_fields = [
            "id",
            "original_name",
            "uploaded_at",
        ]

    def create(
        self,
        validated_data,
    ):
        uploaded_file = validated_data.get(
            "file"
        )

        if uploaded_file:
            validated_data[
                "original_name"
            ] = uploaded_file.name

        return super().create(
            validated_data
        )


# ============================================================
# PROPOSAL UPDATES
# ============================================================

class ProposalUpdateSerializer(
    serializers.ModelSerializer
):
    files = ProposalUpdateFileSerializer(
        many=True,
        read_only=True,
    )

    created_by_name = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = ProposalUpdate

        fields = [
            "id",
            "proposal",
            "milestone_id",
            "title",
            "description",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "files",
        ]

        read_only_fields = [
            "id",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "files",
        ]

    def get_created_by_name(
        self,
        obj,
    ):
        if not obj.created_by:
            return "AB Technologies"

        return (
            getattr(
                obj.created_by,
                "full_name",
                None,
            )
            or getattr(
                obj.created_by,
                "name",
                None,
            )
            or getattr(
                obj.created_by,
                "email",
                None,
            )
            or str(obj.created_by)
        )


# ============================================================
# CLIENT PROJECT CONTENT FILE
# ============================================================

class ClientProjectContentFileSerializer(
    serializers.ModelSerializer
):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ClientProjectContentFile

        fields = [
            "id",
            "file",
            "url",
            "original_name",
            "file_type",
            "description",
            "uploaded_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "original_name",
            "url",
            "uploaded_at",
            "updated_at",
        ]

    def create(
        self,
        validated_data,
    ):
        uploaded_file = validated_data.get(
            "file"
        )

        if uploaded_file:
            validated_data[
                "original_name"
            ] = uploaded_file.name

        return super().create(
            validated_data
        )

    def get_url(
        self,
        obj,
    ):
        if not obj.file:
            return None

        request = self.context.get(
            "request"
        )

        url = obj.file.url

        if request:
            return request.build_absolute_uri(
                url
            )

        return url


# ============================================================
# CLIENT PROJECT CONTENT
# ============================================================

class ClientProjectContentSerializer(
    serializers.ModelSerializer
):
    files = ClientProjectContentFileSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = ClientProjectContent

        fields = [
            "id",
            "proposal",

            # ------------------------------------------------
            # BRAND
            # ------------------------------------------------

            "brand_name",
            "tagline",

            "primary_color",
            "secondary_color",
            "accent_color",
            "background_color",
            "text_color",

            "font_family",

            # ------------------------------------------------
            # COMPANY / PROJECT INFORMATION
            # ------------------------------------------------

            "company_description",
            "about_content",
            "mission",
            "vision",

            # ------------------------------------------------
            # CONTACT
            # ------------------------------------------------

            "contact_information",
            "address",
            "phone",
            "email",
            "website",

            # ------------------------------------------------
            # GENERAL CONTENT
            # ------------------------------------------------

            "additional_content",
            "notes",

            # ------------------------------------------------
            # WORKFLOW
            # ------------------------------------------------

            "status",
            "submitted_at",
            "reviewed_at",

            # ------------------------------------------------
            # TIMESTAMPS
            # ------------------------------------------------

            "created_at",
            "updated_at",

            # ------------------------------------------------
            # CLIENT UPLOADS
            # ------------------------------------------------

            "files",
        ]

        read_only_fields = [
            "id",
            "proposal",

            "status",
            "submitted_at",
            "reviewed_at",

            "created_at",
            "updated_at",

            "files",
        ]


# ============================================================
# PROJECT
# ============================================================

class ProjectSerializer(serializers.ModelSerializer):
    code = serializers.SerializerMethodField()
    name = serializers.CharField(source="title", read_only=True)
    status = serializers.CharField(read_only=True)

    # ★ NEW FIELD
    proposal_public_token = serializers.UUIDField(
        source="public_token",
        read_only=True,
    )

    client_content = ClientProjectContentSerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = [
            # BASIC
            "id",
            "code",
            "name",
            "status",

            # ★ ADD THIS
            "proposal_public_token",

            "version",
            "accepted_version",
            "total_price",
            "currency",
            "accepted_at",
            "created_at",
            "updated_at",

            # STRUCTURE
            "milestones",
            "timeline",
            "deliverables",
            "scope",
            "pages",
            "features",
            "integrations",
            "technical_scope",

            # CLIENT CONTENT
            "client_content",
        ]

    def get_code(self, obj):
        return str(obj.id)[:8].upper()

    def to_representation(self, instance):
        # ... existing code ...
        return data

    def get_code(
        self,
        obj,
    ):
        return str(
            obj.id
        )[:8].upper()

    def to_representation(
        self,
        instance,
    ):
        data = super().to_representation(
            instance
        )

        # Normalize milestone IDs.
        milestones = (
            instance.milestones or []
        )

        normalized_milestones = []

        for index, milestone in enumerate(
            milestones,
            start=1,
        ):
            milestone = dict(
                milestone
            )

            if not milestone.get("id"):
                milestone["id"] = index

            normalized_milestones.append(
                milestone
            )

        data["milestones"] = (
            normalized_milestones
        )

        return data