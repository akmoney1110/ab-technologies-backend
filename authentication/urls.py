from django.urls import path

from .views import (
    ClientDashboardView,
    LoginView,
    MeView,
)


urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path(
        "client/dashboard/",
        ClientDashboardView.as_view(),
        name="client-dashboard",
    ),
]