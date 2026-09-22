import json
import logging
import uuid
from django.shortcuts import render
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .gemini import (
    ask_gemini,
    GeminiQuotaExhausted,
    GeminiRateLimited,
    GeminiUnavailable,
)

from .models import Conversation, Message


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

MAX_MESSAGE_LENGTH = 10_000

MAX_HISTORY_MESSAGES = 100

MAX_OPTION_LENGTH = 200

MAX_OPTIONS = 20


# ============================================================
# ERROR RESPONSE
# ============================================================

def json_error(
    message,
    status=400,
    code=None,
    error_type=None,
    retry_after=None,
    request_id=None,
):
    """
    Return a consistent JSON error response.

    The React frontend can use these fields to determine
    what kind of error UI should be displayed.
    """

    payload = {
        "success": False,
        "error": message,
    }

    if code:
        payload["code"] = code

    if error_type:
        payload["error_type"] = error_type

    if retry_after is not None:
        payload["retry_after"] = retry_after

    if request_id:
        payload["request_id"] = request_id

    return JsonResponse(
        payload,
        status=status,
    )


# ============================================================
# OPTION CLEANING
# ============================================================

def clean_options(
    options,
    selection_mode,
):
    """
    Validate and normalize Gemini-generated options.

    Supported selection modes:

        none
        single
        multiple
    """

    if selection_mode not in {
        "single",
        "multiple",
        "none",
    }:
        selection_mode = "none"

    # No options should be returned for normal messages.
    if selection_mode == "none":
        return []

    if not isinstance(
        options,
        list,
    ):
        return []

    cleaned = []

    seen_values = set()

    for option in options:

        if not isinstance(
            option,
            dict,
        ):
            continue

        label = str(
            option.get(
                "label",
                "",
            )
        ).strip()

        value = str(
            option.get(
                "value",
                "",
            )
        ).strip()

        if not label or not value:
            continue

        # Prevent excessively large option values.
        label = label[:MAX_OPTION_LENGTH]
        value = value[:MAX_OPTION_LENGTH]

        # Prevent duplicate values.
        normalized_value = value.casefold()

        if normalized_value in seen_values:
            continue

        seen_values.add(
            normalized_value
        )

        cleaned.append(
            {
                "label": label,
                "value": value,
            }
        )

        # Never allow Gemini to flood the frontend
        # with hundreds of options.
        if len(cleaned) >= MAX_OPTIONS:
            break

    return cleaned


# ============================================================
# SESSION
# ============================================================

def get_session_id(request):
    """
    Return the Django session identifier.

    This allows conversations from anonymous visitors to be
    associated with their browser session.
    """

    try:

        if not request.session.session_key:
            request.session.create()

        return request.session.session_key

    except Exception:

        logger.exception(
            "Could not initialize AB AI session."
        )

        return None


# ============================================================
# CONVERSATION
# ============================================================

def get_conversation(conversation_id, session_id=None):
    if not conversation_id:
        return None
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except (Conversation.DoesNotExist, ValueError, DatabaseError):
        return None
    
    # Attach session for ownership instead of rejecting
    if session_id and not conversation.session_id:
        try:
            conversation.session_id = session_id
            conversation.save(update_fields=["session_id"])
        except DatabaseError:
            pass
    return conversation
# ============================================================
# CREATE CONVERSATION
# ============================================================

def create_conversation(
    session_id=None,
):
    """
    Create a new AB AI conversation.
    """

    try:

        conversation = Conversation.objects.create(
            session_id=session_id,
        )

        return conversation

    except DatabaseError:

        logger.exception(
            "Failed to create AB AI conversation."
        )

        return None


# ============================================================
# CONVERSATION HISTORY
# ============================================================

def build_history(
    conversation,
):
    """
    Build Gemini-compatible conversation history.

    Only the most recent MAX_HISTORY_MESSAGES messages
    are sent to Gemini.
    """

    history = list(
        Message.objects
        .filter(
            conversation=conversation
        )
        .order_by(
            "created_at",
            "id",
        )
    )

    # --------------------------------------------------------
    # Keep only the latest messages.
    #
    # We convert the QuerySet to a list first because Django
    # does not support negative QuerySet slicing.
    # --------------------------------------------------------

    if len(history) > MAX_HISTORY_MESSAGES:

        history = history[
            -MAX_HISTORY_MESSAGES:
        ]

    messages = []

    for item in history:

        role = item.role

        if role not in {
            "user",
            "assistant",
        }:
            continue

        content = (
            item.content or ""
        ).strip()

        if not content:
            continue

        messages.append(
            {
                "role": role,
                "content": content,
            }
        )

    return messages


# ============================================================
# REQUEST ID
# ============================================================

def get_request_id():
    """
    Generate an internal request identifier.

    Useful for tracing errors in production logs.
    """

    return uuid.uuid4().hex[:16]


# ============================================================
# CHAT ENDPOINT
# ============================================================

@csrf_exempt
@require_POST
def chat(request):
    """
    Main AB AI chat endpoint.

    Flow:

        React
          ↓
        Django
          ↓
        Conversation
          ↓
        User Message
          ↓
        Gemini
          ↓
        Django Tools
          ↓
        CRM / Database
          ↓
        Gemini
          ↓
        Assistant Message
          ↓
        React


    Important:

    Gemini never directly accesses the database.

    Django remains responsible for:

        - conversations
        - authentication
        - authorization
        - CRM
        - database writes
        - business rules
        - tool execution
    """

    request_id = get_request_id()

    logger.info(
        "AB AI request started. request_id=%s",
        request_id,
    )

    # ========================================================
    # SESSION
    # ========================================================

    session_id = get_session_id(
        request
    )

    # ========================================================
    # REQUEST BODY
    # ========================================================

    try:

        raw_body = request.body

    except Exception:

        logger.exception(
            "AB AI could not read request body. request_id=%s",
            request_id,
        )

        return json_error(
            "Could not read the request.",
            status=400,
            code="INVALID_REQUEST",
            error_type="validation",
            request_id=request_id,
        )

    if not raw_body:

        return json_error(
            "Request body is required.",
            status=400,
            code="EMPTY_REQUEST",
            error_type="validation",
            request_id=request_id,
        )

    # ========================================================
    # JSON PARSING
    # ========================================================

    try:

        data = json.loads(
            raw_body.decode(
                "utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):

        return json_error(
            "Invalid JSON request.",
            status=400,
            code="INVALID_JSON",
            error_type="validation",
            request_id=request_id,
        )

    if not isinstance(
        data,
        dict,
    ):

        return json_error(
            "Request body must be a JSON object.",
            status=400,
            code="INVALID_BODY",
            error_type="validation",
            request_id=request_id,
        )

    # ========================================================
    # MESSAGE
    # ========================================================

    message = data.get(
        "message",
        "",
    )

    if not isinstance(
        message,
        str,
    ):

        return json_error(
            "Message must be text.",
            status=400,
            code="MESSAGE_INVALID",
            error_type="validation",
            request_id=request_id,
        )

    message = message.strip()

    if not message:

        return json_error(
            "Message is required.",
            status=400,
            code="MESSAGE_REQUIRED",
            error_type="validation",
            request_id=request_id,
        )

    # ========================================================
    # MESSAGE LENGTH
    # ========================================================

    if len(message) > MAX_MESSAGE_LENGTH:

        return json_error(
            (
                "Your message is too long. "
                f"Please keep it under "
                f"{MAX_MESSAGE_LENGTH:,} characters."
            ),
            status=413,
            code="MESSAGE_TOO_LONG",
            error_type="validation",
            request_id=request_id,
        )

    # ========================================================
    # CONVERSATION ID
    # ========================================================

    conversation_id = data.get(
        "conversation_id"
    )

    if conversation_id:

        conversation_id = str(
            conversation_id
        ).strip()

    # ========================================================
    # GET EXISTING CONVERSATION
    # ========================================================

    conversation = get_conversation(
        conversation_id=conversation_id,
        session_id=session_id,
    )

    created_new_conversation = False

    # ========================================================
    # CREATE NEW CONVERSATION
    # ========================================================

    if conversation is None:

        conversation = create_conversation(
            session_id=session_id,
        )

        if conversation is None:

            return json_error(
                "Could not start the conversation right now.",
                status=500,
                code="CONVERSATION_CREATE_FAILED",
                error_type="server",
                request_id=request_id,
            )

        created_new_conversation = True

    # ========================================================
    # BACKWARD COMPATIBILITY
    # ========================================================

    # If an old conversation has no session ID, attach it
    # to the current anonymous session.

    if (
        session_id
        and not conversation.session_id
    ):

        try:

            conversation.session_id = session_id

            conversation.save(
                update_fields=[
                    "session_id",
                ]
            )

        except DatabaseError:

            logger.warning(
                "Could not attach session to conversation. "
                "request_id=%s conversation_id=%s",
                request_id,
                conversation.id,
            )

    # ========================================================
    # SAVE USER MESSAGE
    # ========================================================

    try:

        Message.objects.create(
            conversation=conversation,
            role="user",
            content=message,
        )

    except DatabaseError:

        logger.exception(
            "Failed to save AB AI user message. "
            "request_id=%s conversation_id=%s",
            request_id,
            conversation.id,
        )

        return json_error(
            "Could not save your message.",
            status=500,
            code="MESSAGE_SAVE_FAILED",
            error_type="server",
            request_id=request_id,
        )

    # ========================================================
    # BUILD HISTORY
    # ========================================================

    try:

        history = build_history(
            conversation
        )

    except DatabaseError:

        logger.exception(
            "Failed to build AB AI conversation history. "
            "request_id=%s conversation_id=%s",
            request_id,
            conversation.id,
        )

        return json_error(
            "Could not load the conversation.",
            status=500,
            code="HISTORY_LOAD_FAILED",
            error_type="server",
            request_id=request_id,
        )

    if not history:

        logger.error(
            "Conversation history unexpectedly empty. "
            "request_id=%s conversation_id=%s",
            request_id,
            conversation.id,
        )

        return json_error(
            "Could not build conversation history.",
            status=500,
            code="HISTORY_EMPTY",
            error_type="server",
            request_id=request_id,
        )

    # ========================================================
    # CALL GEMINI
    # ========================================================

    try:

        ai_response = ask_gemini(
            history,
            conversation=conversation,
        )

    # ========================================================
    # DAILY GEMINI QUOTA
    # ========================================================

    except GeminiQuotaExhausted as exc:

        logger.warning(
            "AB AI Gemini daily quota exhausted. "
            "request_id=%s conversation_id=%s retry_after=%s",
            request_id,
            conversation.id,
            getattr(
                exc,
                "retry_after",
                None,
            ),
        )

        return json_error(
            (
                "AB AI has reached its daily AI usage limit. "
                "Your conversation has been saved. "
                "Please try again later."
            ),
            status=429,
            code="AI_QUOTA_EXHAUSTED",
            error_type="quota",
            retry_after=getattr(
                exc,
                "retry_after",
                None,
            ),
            request_id=request_id,
        )

    # ========================================================
    # TEMPORARY RATE LIMIT
    # ========================================================

    except GeminiRateLimited as exc:

        retry_after = getattr(
            exc,
            "retry_after",
            None,
        )

        logger.warning(
            "AB AI Gemini rate limited. "
            "request_id=%s conversation_id=%s retry_after=%s",
            request_id,
            conversation.id,
            retry_after,
        )

        return json_error(
            (
                "AB AI is receiving too many requests "
                "right now. Please try again shortly."
            ),
            status=429,
            code="AI_RATE_LIMITED",
            error_type="rate_limit",
            retry_after=retry_after,
            request_id=request_id,
        )

    # ========================================================
    # GEMINI TEMPORARILY UNAVAILABLE
    # ========================================================

    except GeminiUnavailable as exc:

        logger.warning(
            "AB AI Gemini temporarily unavailable. "
            "request_id=%s conversation_id=%s error=%r",
            request_id,
            conversation.id,
            exc,
        )

        return json_error(
            (
                "AB AI is temporarily unavailable. "
                "Please try again in a moment."
            ),
            status=503,
            code="AI_UNAVAILABLE",
            error_type="connection",
            retry_after=10,
            request_id=request_id,
        )

    # ========================================================
    # UNEXPECTED GEMINI ERROR
    # ========================================================

    except Exception as exc:

        logger.exception(
            "Unexpected AB AI Gemini error. "
            "request_id=%s conversation_id=%s error=%r",
            request_id,
            conversation.id,
            exc,
        )

        return json_error(
            (
                "AB AI could not process your message "
                "right now. Please try again."
            ),
            status=502,
            code="AI_PROCESSING_FAILED",
            error_type="server",
            request_id=request_id,
        )

    # ========================================================
    # VALIDATE AI RESPONSE
    # ========================================================

    if not isinstance(
        ai_response,
        dict,
    ):

        logger.error(
            "AB AI returned invalid response type. "
            "request_id=%s type=%r",
            request_id,
            type(ai_response),
        )

        return json_error(
            "AB AI returned an invalid response.",
            status=502,
            code="INVALID_AI_RESPONSE",
            error_type="server",
            request_id=request_id,
        )

    # ========================================================
    # REPLY
    # ========================================================

    reply = ai_response.get(
        "reply",
        "",
    )

    if not isinstance(
        reply,
        str,
    ):

        reply = str(
            reply
        )

    reply = reply.strip()

    if not reply:

        logger.error(
            "AB AI returned an empty reply. "
            "request_id=%s conversation_id=%s",
            request_id,
            conversation.id,
        )

        return json_error(
            "AB AI returned an empty response.",
            status=502,
            code="EMPTY_AI_RESPONSE",
            error_type="server",
            request_id=request_id,
        )

    # ========================================================
    # SELECTION MODE
    # ========================================================

    selection_mode = ai_response.get(
        "selection_mode",
        "none",
    )

    if selection_mode not in {
        "none",
        "single",
        "multiple",
    }:

        logger.warning(
            "Invalid selection_mode from AB AI. "
            "request_id=%s mode=%r",
            request_id,
            selection_mode,
        )

        selection_mode = "none"

    # ========================================================
    # OPTIONS
    # ========================================================

    options = clean_options(
        ai_response.get(
            "options",
            [],
        ),
        selection_mode,
    )

    # ========================================================
    # SAFETY CHECK
    # ========================================================

    # If Gemini says there are no choices, don't accidentally
    # expose stale or malformed options.

    if selection_mode == "none":

        options = []

    # If Gemini requested a selection mode but produced no
    # valid options, fall back to normal text mode.

    if (
        selection_mode in {
            "single",
            "multiple",
        }
        and not options
    ):

        selection_mode = "none"

    # ========================================================
    # ALLOW TEXT
    # ========================================================

    allow_text = ai_response.get(
        "allow_text",
        True,
    )

    if not isinstance(
        allow_text,
        bool,
    ):

        allow_text = True

    # ========================================================
    # SAVE ASSISTANT MESSAGE
    # ========================================================

    try:

        with transaction.atomic():

            assistant_message = Message.objects.create(
                conversation=conversation,
                role="assistant",
                content=reply,
            )

            conversation.save(
                update_fields=[
                    "updated_at",
                ]
            )

    except DatabaseError:

        logger.exception(
            "Failed to save AB AI assistant response. "
            "request_id=%s conversation_id=%s",
            request_id,
            conversation.id,
        )

        return json_error(
            (
                "The response was generated, "
                "but could not be saved."
            ),
            status=500,
            code="ASSISTANT_MESSAGE_SAVE_FAILED",
            error_type="server",
            request_id=request_id,
        )

    # ========================================================
    # LOG SUCCESS
    # ========================================================

    logger.info(
        "AB AI request completed successfully. "
        "request_id=%s conversation_id=%s "
        "created_new=%s selection_mode=%s",
        request_id,
        conversation.id,
        created_new_conversation,
        selection_mode,
    )

    # ========================================================
    # RESPONSE
    # ========================================================

    return JsonResponse(
        {
            "success": True,

            "conversation_id": str(
                conversation.id
            ),

            "created_new_conversation": (
                created_new_conversation
            ),

            "message": {
                "id": assistant_message.id,

                "role": "assistant",

                "content": reply,

                "created_at": (
                    assistant_message.created_at.isoformat()
                ),
            },

            # ------------------------------------------------
            # Keep these top-level fields for your existing
            # React frontend.
            # ------------------------------------------------

            "reply": reply,

            "options": options,

            "selection_mode": selection_mode,

            "allow_text": allow_text,

            # ------------------------------------------------
            # Useful for debugging/tracing from the frontend.
            # ------------------------------------------------

            "request_id": request_id,
        }
    )



def admin(request):
    return render(request, "knowledge/inport.html")