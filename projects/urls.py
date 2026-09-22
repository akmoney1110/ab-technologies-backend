from django.urls import path

from .views import (
    ClientProjectListView,
    ClientProjectDetailView,
    StaffProjectMilestoneUpdateView,
    StaffProjectListView,
    StaffProjectDetailView,GenerateQuoteProposalView,
)
from .views import (
    ProjectCommentListCreateView,
    ProjectUpdateListView,
    StaffProjectUpdateCreateView,ClientProjectContentFileUploadView,
    StaffProjectUpdateFileUploadView,ClientProjectContentView
)


urlpatterns = [
    path(
        "",
        ClientProjectListView.as_view(),
        name="client-project-list",
    ),
    path(
        "quote-requests/<uuid:quote_id>/generate-proposal/",
        GenerateQuoteProposalView.as_view(),
        name="generate-quote-proposal",
    ),

    path(
        "<uuid:proposal_id>/",
        ClientProjectDetailView.as_view(),
        name="client-project-detail",
    ),
    path(
        "<uuid:proposal_id>/content/",
        ClientProjectContentView.as_view(),
        name="client-project-content",
    ),
    path(
        "<uuid:proposal_id>/content/files/",
        ClientProjectContentFileUploadView.as_view(),
        name="client-project-content-file-upload",
    ),
    path(

        "staff/",

        StaffProjectListView.as_view(),

        name="staff-project-list",

    ),

    path(
        "staff/<uuid:proposal_id>/",
        StaffProjectDetailView.as_view(),
        name="staff-project-detail",
    ),

    path(
        "staff/<uuid:proposal_id>/milestones/<int:milestone_id>/",
        StaffProjectMilestoneUpdateView.as_view(),
        name="staff-project-milestone-update",
    ),
    path(
        "<uuid:proposal_id>/comments/",
        ProjectCommentListCreateView.as_view(),
        name="project-comments",
    ),

    path(
        "<uuid:proposal_id>/updates/",
        ProjectUpdateListView.as_view(),
        name="project-updates",
    ),

    # Staff
    path(
        "projects/staff/<uuid:proposal_id>/updates/",
        StaffProjectUpdateCreateView.as_view(),
        name="staff-project-update-create",
    ),

    path(
        "projects/staff/<uuid:proposal_id>/updates/<int:update_id>/files/",
        StaffProjectUpdateFileUploadView.as_view(),
        name="staff-project-update-file-upload",
    ),
]