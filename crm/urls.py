from django.urls import path

from .views import (
    ClientProcurementQuotationView,
    ClientProcurementRevisionView,
    ClientProcurementRevisionSubmitView,
)


urlpatterns = [
    # Procurement quotation preview/edit
    path(
        "procurement/<uuid:quote_id>/",
        ClientProcurementQuotationView.as_view(),
        name="client-procurement-quotation",
    ),

    # Specific revision
    path(
        "procurement/revisions/<int:revision_id>/",
        ClientProcurementRevisionView.as_view(),
        name="client-procurement-revision",
    ),

    # Submit revision
    path(
        "procurement/revisions/<int:revision_id>/submit/",
        ClientProcurementRevisionSubmitView.as_view(),
        name="client-procurement-revision-submit",
    ),
]