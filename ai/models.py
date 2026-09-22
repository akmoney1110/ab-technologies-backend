from django.db import models

# Create your models here.
from django.db import models
import uuid


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.id)


class Message(models.Model):

    ROLE_CHOICES = (
        ("user", "User"),
        ("assistant", "Assistant"),
    )

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES
    )

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"
    



