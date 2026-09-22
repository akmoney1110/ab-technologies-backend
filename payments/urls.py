# payments/urls.py

from django.urls import path

from .views import (
    ClientProposalPaymentsView,
    ClientProposalPaymentDetailView,
    InitiateProposalMilestonePaymentView,InitiateProposalFullBalancePaymentView,
    VerifyProposalPaymentView,
    PaystackWebhookView,ClientAllPaymentsListView
)


urlpatterns = [

    # ============================================================
    # CLIENT PAYMENTS
    # ============================================================

    path(
        "client/<uuid:public_token>/payments/",
        ClientProposalPaymentsView.as_view(),
        name="client-proposal-payments",
    ),

    # ============================================================
    # INITIATE MILESTONE PAYMENT
    # ============================================================

    path(
        "client/<uuid:public_token>/payments/initiate/",
        InitiateProposalMilestonePaymentView.as_view(),
        name="initiate-proposal-milestone-payment",
    ),

    # ============================================================
    # VERIFY PAYMENT
    # ============================================================

    path(
        "client/<uuid:public_token>/payments/verify/",
        VerifyProposalPaymentView.as_view(),
        name="verify-proposal-payment",
    ),

    # ============================================================
    # PAYMENT DETAIL
    # ============================================================

    path(
        "client/<uuid:public_token>/payments/<uuid:payment_id>/",
        ClientProposalPaymentDetailView.as_view(),
        name="client-proposal-payment-detail",
    ),
    path(
    "client/all/",
    ClientAllPaymentsListView.as_view(),
    name="client-all-payments",
),


    # ============================================================
    # PAYSTACK WEBHOOK
    # ============================================================
    path(

        "client/<uuid:public_token>/payments/pay-full/",

        InitiateProposalFullBalancePaymentView.as_view(),

        name="initiate-proposal-full-balance-payment",

    ),
    path(
        "webhooks/paystack/",
        PaystackWebhookView.as_view(),
        name="paystack-webhook",
    ),
    
    
]