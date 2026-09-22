from django.urls import path

from .views import (
    StaffProcurementListView,
    StaffProcurementDetailView,PublicProcurementTrackingView,
    StaffProcurementTrackingView,
    StaffProcurementCompleteView,ClientProcurementTrackingView
)

app_name = "procurement"

urlpatterns = [
    path(
        "staff/",
        StaffProcurementListView.as_view(),
        name="staff-procurement-list",
    ),
    path(

        "track/<str:tracking_reference>/",

        PublicProcurementTrackingView.as_view(),

        name="public-procurement-tracking",

    ),

    path(
        "staff/<uuid:proposal_id>/",
        StaffProcurementDetailView.as_view(),
        name="staff-procurement-detail",
    ),

    path(
        "staff/<uuid:proposal_id>/tracking/",
        StaffProcurementTrackingView.as_view(),
        name="staff-procurement-tracking",
    ),

    path(
        "staff/<uuid:proposal_id>/complete/",
        StaffProcurementCompleteView.as_view(),
        name="staff-procurement-complete",
    ),
    path(

        "client/<uuid:public_token>/tracking/",

        ClientProcurementTrackingView.as_view(),

        name="client-procurement-tracking",

    ),
]