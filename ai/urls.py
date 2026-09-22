from django.urls import path

from .views import chat,admin


urlpatterns = [
    path("chat/", chat, name="ai-chat"),
    path("admin/knowledge/knowledgeimporter/", admin, name="admin-chat"),
]