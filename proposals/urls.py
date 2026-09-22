from django.urls import path

from . import views


from .views import (
    client_proposal_api,PublicProcurementTrackingView,
    client_toggle_feature_api,ClientProcurementListView,ClientProcurementDetailView,
    client_accept_proposal_api,client_update_quotation,
    client_decline_proposal_api,client_quote_preview_api,ClientQuotationPreviewView,
)

app_name = "proposals"
urlpatterns = [

    # ========================================================
    # INTERNAL / ADMIN PROPOSAL API
    # ========================================================

    path(
        "generate/",
        views.generate,
        name="proposal-generate",
    ),

    path(
        "<uuid:proposal_id>/",
        views.detail,
        name="proposal-detail",
    ),
    

    
    path(
    "client/<uuid:public_token>/quotation/update/",
    client_update_quotation,
    name="client-update-quotation",
),

    path(
        "<uuid:proposal_id>/revise/",
        views.revise,
        name="proposal-revise",
    ),

    path(
        "<uuid:proposal_id>/accept/",
        views.accept,
        name="proposal-accept",
    ),
    path(

        "client/procurement/<uuid:public_token>/",

        ClientProcurementDetailView.as_view(),

        name="client-procurement-detail",

    ),

    path(
        "<uuid:proposal_id>/revisions/",
        views.revisions,
        name="proposal-revisions",
    ),

    # ========================================================
    # PUBLIC CLIENT PROPOSAL
    # ========================================================

    path(
        "client/<uuid:public_token>/",
        client_proposal_api,
        name="client_proposal",
    ),

    path(
        "client/<uuid:public_token>/features/<int:feature_id>/toggle/",
        client_toggle_feature_api,
        name="client_toggle_feature_api",
    ),
    path(
    "client/csrf/",
    views.client_csrf_api,
    name="client_csrf_api",
),

    path(
        "client/<uuid:public_token>/accept/",
        client_accept_proposal_api,
        name="client_accept_proposal_api",
    ),
    path(

        "client/<uuid:public_token>/accept/",

        client_accept_proposal_api,

        name="client_accept_proposal",

    ),

    path(

        "client/<uuid:public_token>/decline/",

        client_decline_proposal_api,

        name="client_decline_proposal",

    ),
    path(

        "client/procurement/",

        ClientProcurementListView.as_view(),

        name="client-procurement-list",

    ),
    path(
    "clint/<uuid:public_token>/quotation/preview/",
    client_quote_preview_api,
    name="client-quotation-preview",
    
),
    path(
        "client/<uuid:public_token>/quotation/preview/",
        ClientQuotationPreviewView.as_view(),
        name="client-quotation-preview",
    ),

   
]