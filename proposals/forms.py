# proposals/forms.py

from django import forms

from .models import (
    PricingRule,
    Proposal,
    ProposalFeature,
    ProposalRequirement,
    ProposalScreen,
)

class PricingFeatureSelect(forms.Select):
    """
    Feature selector populated directly from PRICING_CATALOG.

    Each option carries its pricing range so the admin
    JavaScript can calculate prices immediately.
    """

    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name=name,
            value=value,
            label=label,
            selected=selected,
            index=index,
            subindex=subindex,
            attrs=attrs,
        )

        feature_key = value

        if feature_key in PRICING_CATALOG:

            pricing = PRICING_CATALOG[
                feature_key
            ]

            option["attrs"]["data-min"] = str(
                pricing["min"]
            )

            option["attrs"]["data-max"] = str(
                pricing["max"]
            )

            option["attrs"]["data-category"] = (
                pricing["category"]
            )

            option["attrs"]["data-name"] = (
                pricing["name"]
            )

        return option




class ProposalFeatureEditorForm(forms.ModelForm):

    class Meta:
        model = ProposalFeature

        fields = [
            "feature_key",
            "name",
            "description",
            "category",
            "complexity",
            "quantity",
            "unit_price",
            "status",
        ]

        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "vLargeTextField",
                }
            ),
            "quantity": forms.NumberInput(
                attrs={
                    "min": 1,
                }
            ),
            "unit_price": forms.NumberInput(
                attrs={
                    "step": "0.01",
                }
            ),
        }


class ProposalRequirementEditorForm(forms.ModelForm):

    class Meta:
        model = ProposalRequirement

        fields = [
            "title",
            "description",
            "requirement_type",
            "status",
        ]

        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                }
            ),
        }

class AddProposalFeatureForm(forms.Form):

    feature_key = forms.ModelChoiceField(
        queryset=PricingRule.objects.filter(
            is_active=True
        ).order_by(
            "category",
            "name",
        ),
        empty_label="Select a pricing feature",
        label="Feature",
    )

    description = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Describe what this feature should do...",
            }
        ),
    )

    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
    )

    status = forms.ChoiceField(
        choices=[
            ("confirmed", "Confirmed"),
            ("recommended", "Recommended"),
            ("optional", "Optional"),
            ("future", "Future"),
        ],
        initial="recommended",
    )

    def save(self, proposal, user=None):
        from .services import create_proposal_feature

        pricing_rule = self.cleaned_data["feature_key"]

        return create_proposal_feature(
            proposal=proposal,
            feature_key=pricing_rule.code,
            name=pricing_rule.name,
            description=self.cleaned_data["description"],
            category=pricing_rule.category,
            quantity=self.cleaned_data["quantity"],
            status=self.cleaned_data["status"],
            source="admin",
        )
    


from django import forms

from .models import ProposalFeature
from .pricing import PRICING_CATALOG, calculate_price




# proposals/forms.py

from decimal import Decimal

from django import forms

from .models import ProposalFeature
from .pricing import PRICING_CATALOG, calculate_price


# proposals/forms.py

from decimal import Decimal

from django import forms

from .models import ProposalFeature
from .pricing import (
    PRICING_CATALOG,
    calculate_price,
    calculate_feature_total,
)


from decimal import Decimal

from django import forms

from .models import Proposal, ProposalFeature
from .pricing import (
    PRICING_CATALOG,
    calculate_feature_total,
    calculate_price,
)


# ============================================================
# SHARED CATALOG CHOICES
# ============================================================

def get_catalog_choices():
    """
    Build grouped choices directly from PRICING_CATALOG.

    PRICING_CATALOG is the single source of truth.
    """

    grouped = {}

    for feature_key, data in PRICING_CATALOG.items():
        category = data.get("category") or "Other"

        grouped.setdefault(category, [])

        minimum = data["min"]
        maximum = data["max"]

        grouped[category].append(
            (
                feature_key,
                f"{data['name']} — ₦{minimum:,.0f}–₦{maximum:,.0f}",
            )
        )

    return [
        (
            category,
            sorted(features, key=lambda item: item[1]),
        )
        for category, features in sorted(grouped.items())
    ]


# ============================================================
# INLINE FORM
# Used inside ProposalAdmin
# ============================================================

class ProposalFeatureAdminForm(forms.ModelForm):

    feature_key = forms.ChoiceField(
        label="Feature",
        choices=[],
        required=True,
    )

    class Meta:
        model = ProposalFeature
        fields = [
            "feature_key",
            "description",
            "complexity",
            "quantity",
            "scope_status",
            "status",
            "source",
            "sort_order",
        ]

    class Media:
        js = (
            "proposals/proposal_feature_pricing.js",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["feature_key"].choices = get_catalog_choices()

        # Existing records
        if self.instance and self.instance.pk:
            if self.instance.feature_key in PRICING_CATALOG:
                self.initial["feature_key"] = self.instance.feature_key

    def clean_feature_key(self):
        feature_key = self.cleaned_data["feature_key"]

        if feature_key not in PRICING_CATALOG:
            raise forms.ValidationError(
                "The selected feature does not exist in the pricing catalog."
            )

        return feature_key

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]

        if quantity < 1:
            raise forms.ValidationError(
                "Quantity must be at least 1."
            )

        return quantity

    def save(self, commit=True):
        instance = super().save(commit=False)

        feature_key = self.cleaned_data["feature_key"]
        complexity = self.cleaned_data["complexity"]
        quantity = self.cleaned_data["quantity"]

        pricing = PRICING_CATALOG[feature_key]

        # --------------------------------------------------------
        # Catalog is authoritative
        # --------------------------------------------------------

        instance.feature_key = feature_key
        instance.name = pricing["name"]
        instance.category = pricing["category"]

        instance.unit_price = calculate_price(
            feature_key=feature_key,
            complexity=complexity,
        )

        instance.total_price = calculate_feature_total(
            feature_key=feature_key,
            complexity=complexity,
            quantity=quantity,
        )

        if commit:
            instance.save()

        return instance


# ============================================================
# STANDALONE ADMIN FORM
# Used at:
# /admin/proposals/proposalfeature/add/
# ============================================================

class ProposalFeatureStandaloneAdminForm(ProposalFeatureAdminForm):

    proposal = forms.ModelChoiceField(
        queryset=Proposal.objects.all(),
        required=True,
        label="Proposal",
    )

    class Meta(ProposalFeatureAdminForm.Meta):
        fields = [
            "proposal",
            
            "feature_key",
            "description",
            "complexity",
            "quantity",
            "scope_status",
            "status",
            "source",
            "sort_order",
        ]
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 5,
                    "style": "width: 100%;",
                    "placeholder": (
                        "Describe what this feature does, "
                        "how it works, and what is included."
                    ),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["proposal"].queryset = Proposal.objects.all().order_by(
            "-created_at"
        )

        if self.instance and self.instance.pk:
            self.initial["proposal"] = self.instance.proposal_id



    # ============================================================
    # JAVASCRIPT
    # ============================================================

    class Media:
        js = (
            "admin/js/proposal_feature_pricing.js",
        )








from django import forms
from .models import ProposalScreen


class ProposalScreenAdminForm(forms.ModelForm):
    class Meta:
        model = ProposalScreen

        fields = [
            "proposal",
            "name",
            "screen_type",
            "purpose",
            
            "user_roles",
            "key_functionality",
            "major_components",
            "data_involved",
            "actions",
            "complexity",
            "dependencies",
            "status",
            "sort_order",
        ]

        widgets = {
           
           
            
            "purpose": forms.Textarea(
                attrs={
                    "rows": 4,
                    "style": "width: 100%;",
                }
            ),

            "user_roles": forms.Textarea(
                attrs={
                    "rows": 4,
                    "style": "width: 100%; font-family: monospace;",
                    "placeholder": '["Admin", "Manager", "Staff"]',
                }
            ),

            "key_functionality": forms.Textarea(
                attrs={
                    "rows": 5,
                    "style": "width: 100%; font-family: monospace;",
                    "placeholder": '["View records", "Create record", "Approve record"]',
                }
            ),

            "major_components": forms.Textarea(
                attrs={
                    "rows": 5,
                    "style": "width: 100%; font-family: monospace;",
                    "placeholder": '["Navigation", "Data table", "Filters", "Forms"]',
                }
            ),

            "data_involved": forms.Textarea(
                attrs={
                    "rows": 5,
                    "style": "width: 100%; font-family: monospace;",
                    "placeholder": '["Users", "Orders", "Payments"]',
                }
            ),

            "actions": forms.Textarea(
                attrs={
                    "rows": 5,
                    "style": "width: 100%; font-family: monospace;",
                    "placeholder": '["Create", "Edit", "Delete", "Submit"]',
                }
            ),

            "dependencies": forms.Textarea(
                attrs={
                    "rows": 5,
                    "style": "width: 100%; font-family: monospace;",
                    "placeholder": '["Authentication", "Backend API"]',
                }
            ),

            "complexity": forms.TextInput(
                attrs={
                    "style": "width: 100%;",
                    "placeholder": "low / medium / high",
                }
            ),
        }


class ProposalScreenEditorForm(forms.ModelForm):

    class Meta:
        model = ProposalScreen

        fields = [
            "name",
            "screen_type",
            "purpose",
            "user_roles",
            "key_functionality",
            "major_components",
            "data_involved",
            "actions",
            "complexity",
            "dependencies",
            "status",
            "sort_order",
        ]

        widgets = {
            "purpose": forms.Textarea(
                attrs={
                    "rows": 4,
                }
            ),

            "user_roles": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": '["Admin", "Manager", "Staff"]',
                }
            ),

            "key_functionality": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": '["View records", "Create record", "Approve record"]',
                }
            ),

            "major_components": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": '["Navigation", "Table", "Filters", "Forms"]',
                }
            ),

            "data_involved": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": '["Users", "Orders", "Payments"]',
                }
            ),

            "actions": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": '["Create", "Edit", "Delete", "Submit"]',
                }
            ),

            "dependencies": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": '["Authentication", "Backend API"]',
                }
            ),

            "complexity": forms.TextInput(
                attrs={
                    "placeholder": "low / medium / high",
                }
            ),
        }





from django import forms

from crm.models import Lead

from .models import (
    Proposal,
    ProposalUpdate,
    ProposalComment,
)


class ProposalUpdateAdminForm(forms.ModelForm):

    client = forms.ModelChoiceField(
        queryset=Lead.objects.all(),
        required=True,
        label="Client",
        help_text="Select the client for this project update.",
    )

    milestone = forms.ChoiceField(
        choices=[],
        required=False,
        label="Milestone",
        help_text="Select the milestone this update belongs to.",
    )

    class Meta:
        model = ProposalUpdate

        fields = (
            "client",
            "proposal",
            "milestone",
            "title",
            "description",
            "created_by",
        )

    def __init__(self, *args, **kwargs):

        super().__init__(
            *args,
            **kwargs,
        )

        # ----------------------------------------------------
        # CLIENT
        # ----------------------------------------------------

        self.fields["client"].label_from_instance = (
            self.client_label
        )

        # ----------------------------------------------------
        # PROPOSALS
        # ----------------------------------------------------

        self.fields["proposal"].queryset = (
            Proposal.objects
            .select_related("lead")
            .all()
            .order_by("-created_at")
        )

        self.fields["proposal"].label_from_instance = (
            self.proposal_label
        )

        # ----------------------------------------------------
        # EXISTING UPDATE
        # ----------------------------------------------------

        if self.instance.pk:

            proposal = self.instance.proposal

            if proposal:

                self.fields["client"].initial = (
                    proposal.lead
                )

                self.set_milestone_choices(
                    proposal
                )

                if self.instance.milestone_id:

                    self.fields["milestone"].initial = (
                        str(
                            self.instance.milestone_id
                        )
                    )

        # ----------------------------------------------------
        # FORM SUBMISSION
        # ----------------------------------------------------

        proposal_id = self.data.get(
            "proposal"
        )

        if proposal_id:

            try:

                proposal = Proposal.objects.get(
                    pk=proposal_id
                )

                self.set_milestone_choices(
                    proposal
                )

            except Proposal.DoesNotExist:

                pass

    # ========================================================
    # CLIENT LABEL
    # ========================================================

    @staticmethod
    def client_label(client):

        name = getattr(
            client,
            "name",
            None,
        )

        email = getattr(
            client,
            "email",
            None,
        )

        company = getattr(
            client,
            "company",
            None,
        )

        parts = []

        if name:
            parts.append(name)

        if company:
            parts.append(
                f"({company})"
            )

        if email:
            parts.append(
                f"- {email}"
            )

        if parts:
            return " ".join(parts)

        return str(client)

    # ========================================================
    # PROPOSAL LABEL
    # ========================================================

    @staticmethod
    def proposal_label(proposal):

        client = proposal.lead

        client_name = getattr(
            client,
            "name",
            None,
        ) or getattr(
            client,
            "email",
            "",
        )

        return (
            f"{proposal.title} "
            f"— {client_name} "
            f"[{proposal.status}]"
        )

    # ========================================================
    # MILESTONES
    # ========================================================

    def set_milestone_choices(
        self,
        proposal,
    ):

        choices = [
            (
                "",
                "General project update",
            )
        ]

        milestones = (
            proposal.milestones
            or []
        )

        for index, milestone in enumerate(
            milestones,
            start=1,
        ):

            milestone = dict(
                milestone
            )

            milestone_id = milestone.get(
                "id"
            ) or index

            name = (
                milestone.get("title")
                or milestone.get("name")
                or milestone.get("label")
                or f"Milestone {milestone_id}"
            )

            status = milestone.get(
                "status"
            )

            if status:
                name = (
                    f"{name} "
                    f"({status.replace('_', ' ').title()})"
                )

            choices.append(
                (
                    str(milestone_id),
                    name,
                )
            )

        self.fields[
            "milestone"
        ].choices = choices

    # ========================================================
    # SAVE
    # ========================================================

    def save(
        self,
        commit=True,
    ):

        instance = super().save(
            commit=False
        )

        proposal = self.cleaned_data.get(
            "proposal"
        )

        milestone = self.cleaned_data.get(
            "milestone"
        )

        if milestone:
            instance.milestone_id = int(
                milestone
            )
        else:
            instance.milestone_id = None

        if commit:
            instance.save()

        return instance
