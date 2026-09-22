
# crm/serializers.py

from rest_framework import serializers

from .models import (
    QuoteRequest,
    ProcurementQuotationItem,ProcurementClientRevisionItem,ProcurementClientRevision,
)


class ClientQuotationItemSerializer(serializers.ModelSerializer):
    """
    Client-facing quotation item.

    All pricing values come directly from Django.
    """

    unit_price = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = ProcurementQuotationItem
        fields = [
            "id",
            "category",
            "name",
            "brand",
            "model",
            "description",
            "specifications",
            "quantity",
            "unit_price",
            "total_price",
        ]

    def get_unit_price(self, obj):
        if obj.unit_price is None:
            return None
        return str(obj.unit_price)

    def get_total_price(self, obj):
        if obj.total_price is None:
            return None
        return str(obj.total_price)


class ClientQuotationSerializer(serializers.ModelSerializer):
    """
    Complete client-facing quotation attached to a proposal.
    """

    items = ClientQuotationItemSerializer(
        many=True,
        read_only=True,
    )

    subtotal = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    tax = serializers.SerializerMethodField()
    delivery_fee = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()

    formatted_subtotal = serializers.SerializerMethodField()
    formatted_discount = serializers.SerializerMethodField()
    formatted_tax = serializers.SerializerMethodField()
    formatted_delivery_fee = serializers.SerializerMethodField()
    formatted_total = serializers.SerializerMethodField()

    class Meta:
        model = QuoteRequest
        fields = [
            "id",

            "title",
            "request_type",
            "description",
            "purpose",
            "notes",

            "budget",
            "currency",
            "deadline",

            "status",

            "items",

            "subtotal",
            "discount",
            "tax",
            "delivery_fee",
            "total",

            "formatted_subtotal",
            "formatted_discount",
            "formatted_tax",
            "formatted_delivery_fee",
            "formatted_total",

            "created_at",
            "updated_at",
        ]

    def get_subtotal(self, obj):
        return str(obj.subtotal)

    def get_discount(self, obj):
        return str(obj.discount)

    def get_tax(self, obj):
        return str(obj.tax)

    def get_delivery_fee(self, obj):
        return str(obj.delivery_fee)

    def get_total(self, obj):
        return str(obj.total)

    def get_formatted_subtotal(self, obj):
        return f"{obj.currency} {obj.subtotal:,.2f}"

    def get_formatted_discount(self, obj):
        return f"{obj.currency} {obj.discount:,.2f}"

    def get_formatted_tax(self, obj):
        return f"{obj.currency} {obj.tax:,.2f}"

    def get_formatted_delivery_fee(self, obj):
        return f"{obj.currency} {obj.delivery_fee:,.2f}"

    def get_formatted_total(self, obj):
        return f"{obj.currency} {obj.total:,.2f}"





class ProcurementClientRevisionItemSerializer(
    serializers.ModelSerializer
):
    effective_unit_price = serializers.SerializerMethodField()

    class Meta:
        model = ProcurementClientRevisionItem

        fields = [
            "id",
            "quotation_item",
            "name",
            "brand",
            "model",
            "category",
            "description",
            "specifications",
            "quantity",
            "quoted_unit_price",
            "proposed_unit_price",
            "approved_unit_price",
            "effective_unit_price",
            "total_price",
            "removed",
            "client_notes",
            "staff_notes",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "quotation_item",
            "quoted_unit_price",
            "approved_unit_price",
            "effective_unit_price",
            "total_price",
            "staff_notes",
            "created_at",
            "updated_at",
        ]

    def get_effective_unit_price(self, obj):
        return str(obj.effective_unit_price)

class ProcurementClientRevisionSerializer(
    serializers.ModelSerializer
):
    items = ProcurementClientRevisionItemSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = ProcurementClientRevision

        fields = [
            "id",
            "quote",
            "revision_number",
            "status",
            "items",
            "discount",
            "tax",
            "delivery_fee",
            "subtotal",
            "total",
            "client_notes",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "quote",
            "revision_number",
            "status",
            "subtotal",
            "total",
            "created_at",
            "updated_at",
        ]




class ProcurementClientRevisionItemUpdateSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = ProcurementClientRevisionItem

        fields = [
            "id",
            "quantity",
            "proposed_unit_price",
            "removed",
            "client_notes",
        ]

        read_only_fields = [
            "id",
        ]

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Quantity must be at least 1."
            )

        return value

    def validate_proposed_unit_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Price cannot be negative."
            )

        return value



class ProcurementClientRevisionUpdateSerializer(
    serializers.ModelSerializer
):
    items = ProcurementClientRevisionItemUpdateSerializer(
        many=True,
        required=False,
    )

    class Meta:
        model = ProcurementClientRevision

        fields = [
            "items",
            "discount",
            "tax",
            "delivery_fee",
            "client_notes",
        ]

        extra_kwargs = {
            "discount": {
                "required": False,
            },
            "tax": {
                "required": False,
            },
            "delivery_fee": {
                "required": False,
            },
            "client_notes": {
                "required": False,
            },
        }

    def update(self, instance, validated_data):
        items_data = validated_data.pop(
            "items",
            [],
        )

        # Client can only edit draft revisions.
        if instance.status != "draft":
            raise serializers.ValidationError(
                "This revision can no longer be edited."
            )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        for item_data in items_data:
            item_id = item_data.pop("id", None)

            if not item_id:
                continue

            try:
                item = instance.items.get(
                    id=item_id
                )
            except ProcurementClientRevisionItem.DoesNotExist:
                continue

            for attr, value in item_data.items():
                setattr(item, attr, value)

            item.save()

        instance.calculate_totals(save=True)

        return instance            