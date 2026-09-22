import json
import logging
import os
import time
from datetime import datetime

from dotenv import load_dotenv

from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

from knowledge.services import search_knowledge

from .tools import (
    create_lead,
    update_lead,
    create_quote_request,
    create_project_request,
    create_support_ticket,
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

MODEL = "gemini-2.5-flash"

MAX_GEMINI_RETRIES = 3

RETRY_DELAYS = [2, 5, 10]

MAX_TOOL_ROUNDS = 5

MAX_OPTIONS = 20

MAX_OPTION_LENGTH = 200

MAX_KNOWLEDGE_RESULTS = 8

MAX_KNOWLEDGE_CHARS = 20_000

MAX_HISTORY_MESSAGES = 100

MAX_REPLY_LENGTH = 20_000

MAX_TOOL_ARGUMENT_CHARS = 10_000


# ============================================================
# GEMINI API KEY
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not configured."
    )


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# CUSTOM EXCEPTIONS
# ============================================================

class GeminiQuotaExhausted(Exception):
    """
    Raised when Gemini's daily/project/model quota
    has been exhausted.

    This error MUST NOT be retried.
    """

    def __init__(
        self,
        message=(
            "Gemini daily free-tier quota "
            "has been exhausted."
        ),
        retry_after=None,
    ):
        super().__init__(message)

        self.retry_after = retry_after


class GeminiRateLimited(Exception):
    """
    Raised when Gemini temporarily rate-limits requests.
    """

    def __init__(
        self,
        message=(
            "Gemini is temporarily "
            "rate limiting requests."
        ),
        retry_after=None,
    ):
        super().__init__(message)

        self.retry_after = retry_after


class GeminiUnavailable(Exception):
    """
    Raised when Gemini remains unavailable after retries.
    """

    def __init__(
        self,
        message=(
            "Gemini is temporarily unavailable."
        ),
    ):
        super().__init__(message)


# ============================================================
# ERROR HELPERS
# ============================================================

def get_error_code(exc):
    """
    Safely extract an HTTP/status code from a Gemini exception.
    """

    code = getattr(
        exc,
        "code",
        None,
    )

    if code is not None:
        return code

    status_code = getattr(
        exc,
        "status_code",
        None,
    )

    if status_code is not None:
        return status_code

    return None
from .quoteproposal import (
    build_quote_proposal_context,
    build_quote_proposal_prompt,
    parse_proposal_response,
    normalize_generated_proposal,
)

def get_retry_after(exc):
    """
    Attempt to extract retry information from a Gemini error.
    """

    for attribute in (
        "retry_after",
        "retry_after_seconds",
    ):
        value = getattr(
            exc,
            attribute,
            None,
        )

        if value is not None:
            try:
                return float(value)
            except (
                TypeError,
                ValueError,
            ):
                pass

    return None


def is_daily_quota_error(exc):
    """
    Determine whether a Gemini 429 represents daily/project/
    model quota exhaustion instead of a temporary rate limit.
    """

    error_text = str(exc).lower()

    daily_quota_patterns = [
        "generaterequestsperdayperproject-freetier",
        "generaterequestsperdaypermodel-freetier",
        "daily quota",
        "daily limit",
        "quota exhausted",
        "quota exceeded",
        "quotaexceeded",
        "resource_exhausted",
        "free tier",
        "freetier",
        "requests per day",
        "per day per project",
        "per day per model",
    ]

    return any(
        pattern in error_text
        for pattern in daily_quota_patterns
    )


def is_temporary_rate_limit(exc):
    """
    Determine whether a 429 appears to be a temporary
    short-window rate limit.
    """

    code = get_error_code(exc)

    if code != 429:
        return False

    if is_daily_quota_error(exc):
        return False

    return True


# ============================================================
# GEMINI REQUEST WITH SMART RETRIES
# ============================================================

def generate_content_with_retry(
    *args,
    **kwargs,
):
    """
    Execute a Gemini request with intelligent retry behavior.

    429 daily quota:
        Never retry.

    429 temporary rate limit:
        Retry.

    503:
        Retry.

    Other 4xx:
        Immediately raise.

    Other 5xx:
        Immediately raise.
    """

    for attempt in range(MAX_GEMINI_RETRIES):

        try:
            return client.models.generate_content(
                *args,
                **kwargs,
            )

        # ====================================================
        # CLIENT ERRORS
        # ====================================================

        except ClientError as exc:

            status_code = get_error_code(exc)

            # ------------------------------------------------
            # DAILY QUOTA
            # ------------------------------------------------

            if is_daily_quota_error(exc):

                logger.warning(
                    "Gemini daily quota exhausted."
                )

                retry_after = get_retry_after(exc)

                raise GeminiQuotaExhausted(
                    message=(
                        "AB AI has reached today's "
                        "Gemini AI request limit."
                    ),
                    retry_after=retry_after,
                ) from exc

            # ------------------------------------------------
            # TEMPORARY RATE LIMIT
            # ------------------------------------------------

            if (
                status_code == 429
                and is_temporary_rate_limit(exc)
            ):

                if attempt < (
                    MAX_GEMINI_RETRIES - 1
                ):

                    delay = RETRY_DELAYS[
                        min(
                            attempt,
                            len(RETRY_DELAYS) - 1,
                        )
                    ]

                    retry_after = get_retry_after(exc)

                    if retry_after:
                        delay = max(
                            delay,
                            retry_after,
                        )

                    logger.warning(
                        "Gemini temporary rate limit. "
                        "Retry %s/%s in %s seconds.",
                        attempt + 1,
                        MAX_GEMINI_RETRIES,
                        delay,
                    )

                    time.sleep(delay)

                    continue

                raise GeminiRateLimited(
                    message=(
                        "Gemini is temporarily "
                        "rate limiting requests."
                    ),
                    retry_after=get_retry_after(exc),
                ) from exc

            # ------------------------------------------------
            # OTHER CLIENT ERRORS
            # ------------------------------------------------

            logger.error(
                "Gemini client error. "
                "status=%s error=%s",
                status_code,
                exc,
            )

            raise

        # ====================================================
        # SERVER ERRORS
        # ====================================================

        except ServerError as exc:

            status_code = get_error_code(exc)

            # ------------------------------------------------
            # TEMPORARY 503
            # ------------------------------------------------

            if status_code == 503:

                if attempt < (
                    MAX_GEMINI_RETRIES - 1
                ):

                    delay = RETRY_DELAYS[
                        min(
                            attempt,
                            len(RETRY_DELAYS) - 1,
                        )
                    ]

                    logger.warning(
                        "Gemini 503. "
                        "Retry %s/%s in %s seconds.",
                        attempt + 1,
                        MAX_GEMINI_RETRIES,
                        delay,
                    )

                    time.sleep(delay)

                    continue

                raise GeminiUnavailable(
                    (
                        "Gemini is temporarily unavailable. "
                        "Please try again shortly."
                    )
                ) from exc

            # ------------------------------------------------
            # OTHER SERVER ERRORS
            # ------------------------------------------------

            logger.error(
                "Gemini server error. "
                "status=%s error=%s",
                status_code,
                exc,
            )

            raise

    raise GeminiUnavailable(
        "Gemini request failed after retries."
    )

# ============================================================
# QUOTE → PROPOSAL AI GENERATION
# ============================================================

def generate_quote_proposal_content(
    quote,
):
    """
    Generate proposal CONTENT from a priced QuoteRequest.

    This function does NOT create the Proposal.

    Django creates the Proposal after Gemini returns.

    Financial values are supplied to Gemini from Django and
    are never generated by Gemini.
    """

    context = build_quote_proposal_context(
        quote
    )

    prompt = build_quote_proposal_prompt(
        context
    )

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.2,
    )

    response = generate_content_with_retry(
        model=MODEL,

        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=prompt
                    )
                ],
            )
        ],

        config=config,
    )

    text = get_response_text(
        response
    )

    generated = parse_proposal_response(
        text
    )

    return normalize_generated_proposal(
        generated
    )
# ============================================================
# AB AI SYSTEM PROMPT
# ============================================================

AB_AI_SYSTEM_PROMPT = """
You are AB AI, the intelligent AI assistant for AB Technologies.

AB Technologies is a technology company providing:

- Custom software development
- Web applications
- Mobile applications
- AI and automation
- Cloud solutions
- DevOps
- Cybersecurity
- Networking
- IT infrastructure
- Hardware procurement
- Corporate and bulk procurement
- Supplier sourcing
- Software products
- Digital learning and training
- IT consulting
- Technical support
- Digital transformation


============================================================
CORE PURPOSE
============================================================

Your job is to help visitors understand AB Technologies and
guide them toward the right technology service, product,
training, procurement option, or business solution.

Be helpful, professional, concise, and conversational.


============================================================
TECHNOLOGY-ONLY SCOPE
============================================================

AB AI is strictly a technology assistant.

You may answer questions about:

- software
- programming
- web development
- mobile development
- AI
- automation
- cloud
- DevOps
- cybersecurity
- networking
- IT infrastructure
- hardware
- computers
- servers
- databases
- APIs
- technology products
- technology procurement
- technical education
- digital transformation
- AB Technologies
- AB Technologies services
- AB Technologies products
- AB Technologies training
- AB Technologies procurement
- technical support

If the user asks about something outside technology, such as:

- politics
- sports
- cooking
- entertainment
- relationships
- general life advice
- personal opinions
- unrelated news
- non-technical medical questions
- non-technical legal questions
- other unrelated subjects

DO NOT answer the question.

Instead:

1. Politely explain that AB AI is focused on technology.
2. Do not provide the requested non-technology answer.
3. Offer to help with a technology-related question.

============================================================
LEAD NOTES
============================================================
When creating a lead, always include a brief summary of the
visitor's request in the 'notes' field. This helps the sales
team understand the enquiry without reading the full chat.

============================================================
CONVERSATION RULES
============================================================

1. Answer technology questions directly.

2. Keep conversations natural and helpful.

3. Do NOT ask for:

   - name
   - email
   - phone number
   - company
   - budget
   - deadline

   unless the user clearly wants to start an enquiry,
   quotation, project, procurement request, consultation,
   training request, or support request.

4. Do NOT create a Lead simply because somebody is chatting.

5. A visitor is NOT automatically a lead.

6. Only create a Lead when the user has clearly indicated
   that they want AB Technologies to follow up or act.

7. Never silently create business records.

8. Collect information progressively.

9. Ask only for information relevant to the current request.

10. Never repeatedly ask for information already provided.

11. Remember information supplied earlier in the conversation.

12. Never invent:

   - prices
   - products
   - services
   - customers
   - contracts
   - policies
   - availability
   - delivery times
   - warranties
   - company facts

13. Use the supplied AB Technologies knowledge.

14. If the knowledge database does not contain a company-specific
    answer, be honest.

15. General technology questions can be answered normally.
16. ask about budget: When the client is uncertain about their requirements 
    or solution, ask whether they have a budget or expected budget range .
    always continue with or without budget 

============================================================
OPTIONS
============================================================

The website may display selectable options.

When appropriate, include concise options in your final response.

Options are optional.

Use options when they make the conversation easier.

Use:

- single when one answer normally makes sense
- multiple when several answers can apply
- none when options are unnecessary

Normally allow free text.

Include "Other" when appropriate.

Keep option labels short.

Never create options unnecessarily.

IMPORTANT:

Selecting an option does NOT automatically mean that the
visitor has submitted a business request.

Do not create a CRM record merely because an option was selected.


============================================================
CRM / TOOL RULES
============================================================

You have access to AB Technologies business tools.

Tools are executed by Django.

Django is the authority.

You may request a tool when the user's intent clearly
requires a business action.

NEVER create a Lead for a general question.

NEVER create a QuoteRequest without a Lead.

NEVER create a ProjectRequest without a Lead.

NEVER create a SupportTicket unless the user is actually
requesting technical support.

Before creating a business record, make sure the required
information is available.

If required information is missing, ask for it.

Never fabricate customer information.

Use information provided across the conversation.

After a tool succeeds, explain the result naturally.

Never expose:

- internal tool names
- database details
- stack traces
- implementation details
- internal IDs unless explicitly appropriate


============================================================
LEAD CREATION
============================================================

A Lead represents a genuine business opportunity or enquiry.

Do NOT create a Lead for:

- greetings
- general questions
- technology questions
- casual conversations
- asking about AB Technologies
- asking what services AB Technologies provides

Create a Lead only when the visitor has clearly expressed
interest in having AB Technologies follow up or act.


============================================================
PROCUREMENT EXAMPLE
============================================================

If a user says:

"I need 100 laptops."

Do NOT immediately create a Lead.

First understand the request.

For example:

"What type of laptops are you looking for?"

You may progressively ask about:

- device type
- quantity
- specifications
- brand
- model
- operating system
- intended use
- delivery location
- other relevant requirements

If the user later clearly wants AB Technologies to prepare
a quotation, collect the necessary contact information and
create the appropriate CRM records.


============================================================
PROJECT EXAMPLE
============================================================

If a user says:

"I want AB Technologies to build a mobile app."

Ask useful discovery questions such as:

- What type of app?
- What is the main purpose?
- Who will use it?
- What major features are required?

Do not immediately ask for every possible business detail.


============================================================
SUPPORT EXAMPLE
============================================================

If the user reports a technical problem, understand the issue
first.

Only create a support ticket when the user is actually asking
AB Technologies for support or wants the issue recorded.


============================================================
TOOL EXECUTION
============================================================

When a tool is required:

1. Request the appropriate tool.
2. Wait for Django's result.
3. Review the result.
4. Continue the conversation naturally.

Never claim that a record was created unless Django returned
a successful result.

If a tool returns success=false:

- do not claim success
- do not fabricate a result
- explain that the operation could not be completed
- ask for whatever information is genuinely needed


============================================================
FINAL RESPONSE FORMAT
============================================================

Your final response should normally be a natural-language
answer.

Do NOT output markdown JSON unless explicitly requested.

The application will normalize your final response for the
frontend.

When appropriate, you may provide concise choices in your
response, but do not invent unnecessary options.


============================================================
IMPORTANT
============================================================

Django is the authority.

You must never directly access the database.

Gemini only decides what should happen.

Django performs the actual business operation.

Never bypass Django.
"""


# ============================================================
# CRM TOOL DECLARATIONS
# ============================================================

CREATE_LEAD = types.FunctionDeclaration(
    name="create_lead",

    description="""
Create a genuine AB Technologies lead when a visitor has clear
commercial, project, procurement, consultation, training or
support intent and has agreed to proceed.
pls do not leave the intent empty so i can use it to reference there crm

Do NOT use this for casual conversation or general questions.

Only call this when the visitor has clearly indicated that
AB Technologies should follow up or act.
""",

    parameters={
        "type": "object",

        "properties": {

            "name": {
                "type": "string",
                "description": (
                    "Visitor's name, if provided."
                ),
            },

            "email": {
                "type": "string",
                "description": (
                    "Visitor's email address, if provided."
                ),
            },

            "phone": {
                "type": "string",
                "description": (
                    "Visitor's phone number, if provided."
                ),
            },

            "company": {
                "type": "string",
                "description": (
                    "Visitor's company, if provided."
                ),
            },

            "intent": {
                "type": "string",
                "description": (
                    "The visitor's genuine business intent."
                ),
            },

            "source": {
                "type": "string",
                "description": (
                    "Lead source, normally website or AB AI."
                ),
            },

            "notes": {
                "type": "string",
                "description": (
                    "Useful context about the enquiry."
                ),
            },
        },

        "required": [
            "intent",
        ],
    },
)


UPDATE_LEAD = types.FunctionDeclaration(
    name="update_lead",

    description="""
Update an existing AB Technologies lead when new information
is provided or an existing lead needs to be updated.
""",

    parameters={
        "type": "object",

        "properties": {

            "lead_id": {
                "type": "string",
                "description": (
                    "Existing lead UUID."
                ),
            },

            "name": {
                "type": "string",
            },

            "email": {
                "type": "string",
            },

            "phone": {
                "type": "string",
            },

            "company": {
                "type": "string",
            },

            "intent": {
                "type": "string",
            },

            "status": {
                "type": "string",
            },

            "notes": {
                "type": "string",
            },
        },

        "required": [
            "lead_id",
        ],
    },
)


CREATE_QUOTE_REQUEST = types.FunctionDeclaration(
    name="create_quote_request",

    description="""
Create a quotation request when the user clearly wants AB Technologies
to prepare pricing, a quotation, or a proposal.

This function supports:
1. Hardware procurement quotations.
2. Software development quotations.
3. Website and mobile application quotations.
4. IT infrastructure and networking quotations.
5. Cloud, hosting, security, automation, consultancy, and other
   technology services.
6. Training, digital learning, and skill-development quotations.

A valid lead must already exist.

IMPORTANT RULES:

LEAD:
- Never fabricate a lead ID.
- Use only the existing lead UUID provided by the system.

GENERAL:
- Extract what the client actually requested.
- Do not invent information that the client did not provide.
- Do not invent prices.
- Do not invent brands or models.
- Do not invent technical specifications.
- If information was not provided by the client, use null or an
  empty value where appropriate.
- Preserve the client's original requirements as accurately as possible.

HARDWARE PROCUREMENT:
- A quotation request may contain multiple hardware items.
- Each distinct hardware item MUST be represented as a separate item
  in the items array.
- Examples of separate items include laptops, desktops, monitors,
  printers, servers, network switches, routers, firewalls, Wi-Fi
  access points, UPS units, CCTV cameras, storage devices, and
  accessories.
- Preserve the quantity for each individual item.
- Preserve the brand ONLY when the client explicitly provides a brand.
- Preserve the model ONLY when the client explicitly provides a model.
- If the client does not specify a brand, brand must be null.
- If the client does not specify a model, model must be null.
- Extract technical specifications when explicitly provided.
- Do NOT select a brand or model on behalf of the client during
  requirement extraction.
- Do NOT generate or guess a unit price.
- Do NOT generate or guess a total price.
- unit_price and total_price MUST remain null unless the client
  explicitly provided an actual price.
- Django/AB Technologies staff will enter or determine prices later.
- Django is responsible for calculating item totals, subtotal,
  discounts, taxes, delivery charges, and final quotation totals.
- If the client gives one quantity for one item, do not apply that
  quantity to other items.
- Do not merge different hardware categories into one item.

Example:

Client:
"I need a quotation for 10 laptops, 10 network switches and
10 Wi-Fi access points for training purposes."

Return separate items:

Laptop × 10
Network Switch × 10
Wi-Fi Access Point × 10

Brand:
null

Model:
null

unit_price:
null

total_price:
null

Purpose:
"training purposes"

If the client says:
"I need 10 HP laptops"

Then:

brand:
"HP"

If the client says:
"I need 10 HP 14-ep0299 laptops"

Then:

brand:
"HP"
model:
"14-ep0299"

Do not add a different HP model or price unless the client explicitly
provides it.

TRAINING:
- Training requests may also contain multiple courses or training
  items.
- Preserve course names, participant counts, delivery mode, duration,
  skill level, location, preferred dates, and other requirements when
  provided.
- Do not invent training prices.

BUDGET:
- Capture a budget only when the client explicitly provides one.
- A budget is a client constraint, NOT a calculated quotation total.
- Do not treat the budget as the price of an item.
- If no budget was provided, use null.

CURRENCY:
- Preserve the currency explicitly provided by the client.
- If no currency is provided, use null rather than inventing one.

DEADLINE:
- Capture the client's requested deadline or delivery date when
  explicitly provided.
- Do not invent a deadline.

TITLE:
- Generate a concise title describing the quotation request.
- The title should represent the overall request, not just the first
  item.

DESCRIPTION:
- Preserve the client's overall requirement in a clear and useful form.
- Do not add specifications, prices, brands, or models that the client
  did not provide.

NOTES:
- Include relevant additional requirements, constraints, preferences,
  urgency, purpose, delivery information, or clarification points.

The request should be created as a draft quotation request.
It is NOT yet a final quotation.

Pricing and final quotation generation happen later after AB Technologies
staff have reviewed the requested items and entered/confirmed prices.
""",

    parameters={
        "type": "object",

        "properties": {

            "lead_id": {
                "type": "string",
                "description": (
                    "Existing AB Technologies lead UUID. "
                    "Never fabricate this value."
                ),
            },

            "title": {
                "type": "string",
                "description": (
                    "Short title describing the overall quotation request. "
                    "Example: 'Training Hardware Procurement Request'."
                ),
            },

            "description": {
                "type": "string",
                "description": (
                    "Clear description of the client's overall quotation "
                    "requirement. Preserve the client's actual request "
                    "without inventing missing information."
                ),
            },

            "request_type": {
                "type": "string",
                "enum": [
                    "hardware_procurement",
                    "software_development",
                    "website",
                    "mobile_application",
                    "networking",
                    "cloud_hosting",
                    "security",
                    "automation",
                    "consultancy",
                    "training",
                    "other",
                ],
                "description": (
                    "Primary type of quotation request."
                ),
            },

            "purpose": {
                "type": "string",
                "description": (
                    "Purpose or intended use of the requested products "
                    "or services, if explicitly provided by the client. "
                    "Otherwise null."
                ),
            },

            "items": {
                "type": "array",
                "description": (
                    "Individual items/services requested by the client. "
                    "For hardware procurement, each distinct hardware "
                    "category must be a separate item."
                ),
                "items": {
                    "type": "object",
                    "properties": {

                        "category": {
                            "type": "string",
                            "description": (
                                "Hardware or service category, such as "
                                "Laptop, Network Switch, Wi-Fi Access Point, "
                                "Printer, Website, Mobile Application, "
                                "Training Course, etc."
                            ),
                        },

                        "name": {
                            "type": "string",
                            "description": (
                                "Specific item or service name."
                            ),
                        },

                        "brand": {
                            "type": "string",
                            "description": (
                                "Brand explicitly provided by the client. "
                                "Use null when the client did not specify "
                                "a brand."
                            ),
                        },

                        "model": {
                            "type": "string",
                            "description": (
                                "Model explicitly provided by the client. "
                                "Use null when the client did not specify "
                                "a model."
                            ),
                        },

                        "quantity": {
                            "type": "integer",
                            "description": (
                                "Quantity requested for this specific item."
                            ),
                        },

                        "specifications": {
                            "type": "object",
                            "description": (
                                "Technical specifications explicitly "
                                "provided by the client. Do not invent "
                                "missing specifications."
                            ),
                        },

                        "description": {
                            "type": "string",
                            "description": (
                                "Additional description or requirement "
                                "for this individual item."
                            ),
                        },

                        "unit_price": {
                            "type": "number",
                            "description": (
                                "Actual price explicitly supplied by the "
                                "client, if any. Otherwise null. Never "
                                "invent a price."
                            ),
                        },

                        "total_price": {
                            "type": "number",
                            "description": (
                                "Only use when the client explicitly "
                                "provided an actual total price. Otherwise "
                                "must be null. Django calculates this later."
                            ),
                        },
                    },

                    "required": [
                        "category",
                        "name",
                        "quantity",
                        "brand",
                        "model",
                        "specifications",
                        "unit_price",
                        "total_price",
                    ],
                },
            },

            "budget": {
                "type": "number",
                "description": (
                    "Client's explicitly stated budget or budget limit. "
                    "This is NOT the quotation total. Use null if none "
                    "was provided."
                ),
            },

            "currency": {
                "type": "string",
                "description": (
                    "Currency explicitly provided by the client, such as "
                    "NGN, USD, GBP, or CAD. Use null if not provided."
                ),
            },

            "deadline": {
                "type": "string",
                "description": (
                    "Requested delivery/completion deadline or date, "
                    "if explicitly provided. Otherwise null."
                ),
            },

            "notes": {
                "type": "string",
                "description": (
                    "Additional client requirements, constraints, "
                    "preferences, urgency, delivery requirements, or "
                    "other relevant information."
                ),
            },
        },

        "required": [
            "lead_id",
            "title",
            "description",
            "request_type",
            "items",
        ],
    },
)


CREATE_PROJECT_REQUEST = types.FunctionDeclaration(
    name="create_project_request",

    description="""
Create a project request when the user clearly wants AB
Technologies to build, develop, deploy or implement a
technology solution.

A valid lead must already exist.

Never fabricate a lead ID.
""",

    parameters={
        "type": "object",

        "properties": {

            "lead_id": {
                "type": "string",
                "description": (
                    "Existing AB Technologies lead UUID."
                ),
            },

            "title": {
                "type": "string",
            },

            "description": {
                "type": "string",
            },

            "project_type": {
                "type": "string",
            },

            "budget": {
                "type": "number",
            },

            "currency": {
                "type": "string",
            },

            "deadline": {
                "type": "string",
            },

            "notes": {
                "type": "string",
            },
        },

        "required": [
            "title",
            "description",
        ],
    },
)


CREATE_SUPPORT_TICKET = types.FunctionDeclaration(
    name="create_support_ticket",

    description="""
Create a technical support ticket when the user clearly
requests AB Technologies technical support or asks for
their technology problem to be recorded or also Create a support ticket when the user clearly wants AB
Technologies consulting, advisory, or IT strategy services.

Do not create support tickets for general technology questions.
""",

    parameters={
        "type": "object",

        "properties": {

            "lead_id": {
                "type": "string",
            },

            "subject": {
                "type": "string",
            },

            "description": {
                "type": "string",
            },

            "priority": {
                "type": "string",
            },
        },

        "required": [
            "subject",
            "description",
        ],
    },
)


# ============================================================
# GEMINI TOOL OBJECT
# ============================================================

CRM_TOOL = types.Tool(
    function_declarations=[
        CREATE_LEAD,
        UPDATE_LEAD,
        CREATE_QUOTE_REQUEST,
        CREATE_PROJECT_REQUEST,
        CREATE_SUPPORT_TICKET,
    ]
)


# ============================================================
# TOOL EXECUTION
# ============================================================

def execute_tool(
    name,
    arguments,
    conversation=None,
):
    """
    Execute a Django business tool.

    Gemini decides which tool is needed.

    Django executes it.

    Gemini never receives direct database access.
    """

    arguments = arguments or {}

    if not isinstance(arguments, dict):
        arguments = {}

    try:

        if name == "create_lead":

            return create_lead(
                conversation=conversation,
                **arguments,
            )

        if name == "update_lead":

            return update_lead(
                **arguments,
            )

        if name == "create_quote_request":

            return create_quote_request(
                **arguments,
            )

        if name == "create_project_request":

            return create_project_request(
                **arguments,
            )

        if name == "create_support_ticket":

            return create_support_ticket(
                **arguments,
            )

        logger.error(
            "Unknown AB AI tool requested: %s",
            name,
        )

        return {
            "success": False,
            "error": (
                "The requested business operation "
                "is not available."
            ),
        }

    except Exception:

        logger.exception(
            "AB AI tool execution failed. tool=%s",
            name,
        )

        return {
            "success": False,
            "error": (
                "The requested business operation "
                "could not be completed."
            ),
        }


# ============================================================
# LATEST USER MESSAGE
# ============================================================

def get_latest_user_message(
    history,
):
    """
    Find the latest user message.
    """

    for message in reversed(history):

        if message.get("role") != "user":
            continue

        content = (
            message.get(
                "content",
                "",
            )
            or ""
        ).strip()

        if content:
            return content

    return ""


# ============================================================
# KNOWLEDGE SEARCH
# ============================================================

def build_knowledge_context(
    latest_user_message,
):
    """
    Retrieve relevant AB Technologies knowledge.

    Handles both:

        list

    and:

        {
            "results": [...]
        }

    response formats.
    """

    if not latest_user_message:
        return ""

    try:

        results = search_knowledge(
            latest_user_message
        )

    except Exception:

        logger.exception(
            "Knowledge search failed."
        )

        return ""

    if not results:
        return ""

    # --------------------------------------------------------
    # NORMALIZE SEARCH RESULT
    # --------------------------------------------------------

    if isinstance(results, dict):

        items = (
            results.get("results")
            or results.get("items")
            or results.get("knowledge")
            or results.get("documents")
            or results.get("data")
            or []
        )

    elif isinstance(
        results,
        (list, tuple),
    ):

        items = results

    else:

        items = []

    if not isinstance(
        items,
        (list, tuple),
    ):

        return ""

    # --------------------------------------------------------
    # LIMIT RESULTS
    # --------------------------------------------------------

    items = items[
        :MAX_KNOWLEDGE_RESULTS
    ]

    context_parts = []

    total_chars = 0

    # --------------------------------------------------------
    # BUILD CONTEXT
    # --------------------------------------------------------

    for item in items:

        if not isinstance(
            item,
            dict,
        ):
            continue

        title = (
            item.get("title")
            or item.get("name")
            or item.get("heading")
            or ""
        )

        content = (
            item.get("content")
            or item.get("text")
            or item.get("body")
            or item.get("description")
            or ""
        )

        if not content:
            continue

        title = str(
            title
        ).strip()

        content = str(
            content
        ).strip()

        if title:

            block = (
                f"### {title}\n"
                f"{content}"
            )

        else:

            block = content

        remaining = (
            MAX_KNOWLEDGE_CHARS
            - total_chars
        )

        if remaining <= 0:
            break

        block = block[
            :remaining
        ]

        context_parts.append(
            block
        )

        total_chars += len(
            block
        )

    if not context_parts:
        return ""

    return (
        "AB TECHNOLOGIES KNOWLEDGE BASE\n\n"
        "Use the following information when relevant. "
        "Do not invent company-specific facts that are "
        "not supported by this knowledge.\n\n"
        + "\n\n".join(
            context_parts
        )
    )


# ============================================================
# SYSTEM INSTRUCTION
# ============================================================

def build_system_instruction(
    history,
):
    """
    Build the complete AB AI system instruction.
    """

    latest_user_message = (
        get_latest_user_message(
            history
        )
    )

    knowledge_context = (
        build_knowledge_context(
            latest_user_message
        )
    )

    current_date = (
        datetime.now().strftime(
            "%Y-%m-%d"
        )
    )

    instruction = (
        AB_AI_SYSTEM_PROMPT
        + "\n\n"
        + "============================================================"
        + "\nCURRENT DATE"
        + "\n============================================================"
        + "\n"
        + current_date
    )

    if knowledge_context:

        instruction += (
            "\n\n"
            "============================================================"
            "\nAB TECHNOLOGIES KNOWLEDGE"
            "\n============================================================"
            "\n"
            + knowledge_context
        )

    return instruction


# ============================================================
# BUILD GEMINI CONTENTS
# ============================================================

def build_contents(
    history,
):
    """
    Convert Django conversation history into Gemini contents.

    Django:
        user
        assistant

    Gemini:
        user
        model
    """

    contents = []

    # --------------------------------------------------------
    # Limit history
    # --------------------------------------------------------

    if len(history) > MAX_HISTORY_MESSAGES:

        history = history[
            -MAX_HISTORY_MESSAGES:
        ]

    # --------------------------------------------------------
    # Convert messages
    # --------------------------------------------------------

    for item in history:

        role = item.get(
            "role"
        )

        content = (
            item.get(
                "content",
                "",
            )
            or ""
        ).strip()

        if not content:
            continue

        if role == "user":

            contents.append(
                types.Content(
                    role="user",

                    parts=[
                        types.Part(
                            text=content
                        )
                    ],
                )
            )

        elif role == "assistant":

            contents.append(
                types.Content(
                    role="model",

                    parts=[
                        types.Part(
                            text=content
                        )
                    ],
                )
            )

    return contents


# ============================================================
# FUNCTION CALL EXTRACTION
# ============================================================

def extract_function_calls(
    response,
):
    """
    Extract function calls from Gemini's response.

    Returns a list of FunctionCall objects.
    """

    function_calls = []

    candidates = getattr(
        response,
        "candidates",
        [],
    ) or []

    for candidate in candidates:

        content = getattr(
            candidate,
            "content",
            None,
        )

        if not content:
            continue

        parts = getattr(
            content,
            "parts",
            [],
        ) or []

        for part in parts:

            function_call = getattr(
                part,
                "function_call",
                None,
            )

            if function_call:

                function_calls.append(
                    function_call
                )

    return function_calls


# ============================================================
# RESPONSE TEXT
# ============================================================

def get_response_text(
    response,
):
    """
    Safely retrieve Gemini's final text response.
    """

    text = getattr(
        response,
        "text",
        None,
    )

    if isinstance(
        text,
        str,
    ):

        return text.strip()

    # --------------------------------------------------------
    # Defensive fallback
    # --------------------------------------------------------

    candidates = getattr(
        response,
        "candidates",
        [],
    ) or []

    text_parts = []

    for candidate in candidates:

        content = getattr(
            candidate,
            "content",
            None,
        )

        if not content:
            continue

        parts = getattr(
            content,
            "parts",
            [],
        ) or []

        for part in parts:

            part_text = getattr(
                part,
                "text",
                None,
            )

            if isinstance(
                part_text,
                str,
            ) and part_text.strip():

                text_parts.append(
                    part_text.strip()
                )

    return "\n".join(
        text_parts
    ).strip()


# ============================================================
# CLEAN OPTIONS
# ============================================================

def clean_options(
    raw_options,
):
    """
    Safely normalize optional UI choices.
    """

    if not isinstance(
        raw_options,
        list,
    ):

        return []

    cleaned = []

    seen_values = set()

    for option in raw_options:

        if isinstance(
            option,
            str,
        ):

            label = option.strip()

            value = label

        elif isinstance(
            option,
            dict,
        ):

            label = str(
                option.get(
                    "label",
                    "",
                )
                or ""
            ).strip()

            value = str(
                option.get(
                    "value",
                    "",
                )
                or ""
            ).strip()

        else:

            continue

        if not label:
            continue

        if not value:
            value = label

        label = label[
            :MAX_OPTION_LENGTH
        ]

        value = value[
            :MAX_OPTION_LENGTH
        ]

        normalized_value = (
            value.casefold()
        )

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

        if len(cleaned) >= MAX_OPTIONS:
            break

    return cleaned


# ============================================================
# PARSE OPTIONAL UI RESPONSE
# ============================================================

def extract_ui_metadata(
    text,
):
    """
    Optional parser for a lightweight JSON response if Gemini
    happens to return JSON despite the normal text configuration.

    This is NOT required for Gemini function calling.

    It exists only as a defensive compatibility layer.
    """

    if not text:
        return None

    candidate = text.strip()

    if not (
        candidate.startswith("{")
        and candidate.endswith("}")
    ):

        return None

    try:

        data = json.loads(
            candidate
        )

    except (
        json.JSONDecodeError,
        TypeError,
    ):

        return None

    if not isinstance(
        data,
        dict,
    ):

        return None

    if "reply" not in data:
        return None

    return data


# ============================================================
# CLEAN RESPONSE
# ============================================================

def clean_response(
    data,
):
    """
    Normalize the final response into the format expected by
    the Django API and React frontend.
    """

    if isinstance(
        data,
        str,
    ):

        text = data.strip()

        return {
            "reply": text[
                :MAX_REPLY_LENGTH
            ],

            "options": [],

            "selection_mode": "none",

            "allow_text": True,
        }

    if not isinstance(
        data,
        dict,
    ):

        return {
            "reply": str(data)[
                :MAX_REPLY_LENGTH
            ],

            "options": [],

            "selection_mode": "none",

            "allow_text": True,
        }

    # ========================================================
    # REPLY
    # ========================================================

    reply = data.get(
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

    reply = reply[
        :MAX_REPLY_LENGTH
    ]

    # ========================================================
    # OPTIONS
    # ========================================================

    cleaned_options = clean_options(
        data.get(
            "options",
            [],
        )
    )

    # ========================================================
    # SELECTION MODE
    # ========================================================

    selection_mode = data.get(
        "selection_mode",
        "none",
    )

    if selection_mode not in {
        "none",
        "single",
        "multiple",
    }:

        selection_mode = "none"

    if not cleaned_options:

        selection_mode = "none"

    # ========================================================
    # ALLOW TEXT
    # ========================================================

    allow_text = data.get(
        "allow_text",
        True,
    )

    if not isinstance(
        allow_text,
        bool,
    ):

        allow_text = True

    return {
        "reply": reply,

        "options": cleaned_options,

        "selection_mode": selection_mode,

        "allow_text": allow_text,
    }


# ============================================================
# PARSE FINAL GEMINI RESPONSE
# ============================================================

def parse_final_response(
    response,
):
    """
    Convert Gemini's final natural-language response into the
    response structure expected by the application.

    Gemini 2.5 Flash + custom function calling does not use
    application/json response MIME type in this configuration.

    Therefore the normal final response is text.

    If Gemini happens to return the old JSON format, we support
    that defensively as well.
    """

    text = get_response_text(
        response
    )

    if not text:

        raise ValueError(
            "Gemini returned an empty response."
        )

    # --------------------------------------------------------
    # Check whether Gemini happened to return JSON.
    # --------------------------------------------------------

    structured = extract_ui_metadata(
        text
    )

    if structured is not None:

        return clean_response(
            structured
        )

    # --------------------------------------------------------
    # Normal text response.
    # --------------------------------------------------------

    return clean_response(
        text
    )


# ============================================================
# BUILD GEMINI CONFIG
# ============================================================

def build_generate_config(
    system_instruction,
):
    """
    Build the Gemini configuration.

    IMPORTANT:

    Do NOT combine:

        tools=[CRM_TOOL]

    with:

        response_mime_type="application/json"

    for the Gemini 2.5 Flash generate_content function-calling
    flow.

    Gemini function calls are structured independently through
    FunctionDeclaration.

    Final assistant output is returned as normal text and then
    normalized by Django.
    """

    return types.GenerateContentConfig(

        system_instruction=(
            system_instruction
        ),

        tools=[
            CRM_TOOL
        ],

        temperature=0.3,
    )


# ============================================================
# TOOL RESULT CONTENT
# ============================================================

def build_tool_response_content(
    function_calls,
    results,
):
    """
    Build the Gemini content containing function responses.

    Each FunctionResponse is paired with the corresponding
    function call.

    Gemini's API expects the function response to identify the
    function name and, when supplied, the function-call ID.
    """

    parts = []

    for function_call, result in zip(
        function_calls,
        results,
    ):

        name = (
            getattr(
                function_call,
                "name",
                "",
            )
            or ""
        )

        if not name:
            continue

        function_response_kwargs = {
            "name": name,
            "response": result,
        }

        function_call_id = getattr(
            function_call,
            "id",
            None,
        )

        if function_call_id:

            function_response_kwargs[
                "id"
            ] = function_call_id

        parts.append(
            types.Part(
                function_response=(
                    types.FunctionResponse(
                        **function_response_kwargs
                    )
                )
            )
        )

    if not parts:
        return None

    return types.Content(
        role="user",
        parts=parts,
    )


# ============================================================
# MAIN AB AI FUNCTION
# ============================================================

def ask_gemini(
    history,
    conversation=None,
):
    """
    Main AB AI engine.

    Architecture:

        Django conversation
                ↓
        Knowledge retrieval
                ↓
             Gemini
                ↓
        ┌───────┴────────┐
        │                │
     Tool call         Text
        │                │
        ↓                ↓
     Django           Final
       tool           response
        │
        ↓
     Gemini
        │
        ↓
     Final response

    Normal conversation:

        1 Gemini request

    Tool-assisted conversation:

        1 initial Gemini request
        +
        1 Gemini request per tool round

    There is NO unnecessary third "format this JSON" request.
    """

    # ========================================================
    # VALIDATE HISTORY
    # ========================================================

    if not history:

        raise ValueError(
            "Gemini requires conversation history."
        )

    if not isinstance(
        history,
        list,
    ):

        history = list(
            history
        )

    # ========================================================
    # SYSTEM INSTRUCTION
    # ========================================================

    system_instruction = (
        build_system_instruction(
            history
        )
    )

    # ========================================================
    # CONTENTS
    # ========================================================

    contents = build_contents(
        history
    )

    if not contents:

        raise ValueError(
            "No valid Gemini conversation content."
        )

    # ========================================================
    # CONFIG
    # ========================================================

    config = build_generate_config(
        system_instruction
    )

    # ========================================================
    # INITIAL GEMINI REQUEST
    # ========================================================

    response = (
        generate_content_with_retry(
            model=MODEL,
            contents=contents,
            config=config,
        )
    )

    # ========================================================
    # TOOL LOOP
    # ========================================================

    for tool_round in range(
        MAX_TOOL_ROUNDS
    ):

        function_calls = (
            extract_function_calls(
                response
            )
        )

        # ----------------------------------------------------
        # NO TOOL CALL
        # ----------------------------------------------------

        if not function_calls:
            break

        logger.info(
            "AB AI tool round %s/%s. calls=%s",
            tool_round + 1,
            MAX_TOOL_ROUNDS,
            len(function_calls),
        )

        # ----------------------------------------------------
        # ENSURE CANDIDATE EXISTS
        # ----------------------------------------------------

        candidates = getattr(
            response,
            "candidates",
            [],
        ) or []

        if not candidates:

            raise ValueError(
                "Gemini returned no candidates."
            )

        # ----------------------------------------------------
        # APPEND GEMINI MODEL CONTENT
        # ----------------------------------------------------

        model_content = getattr(
            candidates[0],
            "content",
            None,
        )

        if model_content:

            contents.append(
                model_content
            )

        # ----------------------------------------------------
        # EXECUTE ALL FUNCTION CALLS
        # ----------------------------------------------------

        tool_results = []

        for function_call in (
            function_calls
        ):

            name = (
                getattr(
                    function_call,
                    "name",
                    "",
                )
                or ""
            )

            arguments = (
                getattr(
                    function_call,
                    "args",
                    None,
                )
                or {}
            )

            if not isinstance(
                arguments,
                dict,
            ):

                arguments = {}

            # ------------------------------------------------
            # SAFETY LIMIT
            # ------------------------------------------------

            try:

                serialized_arguments = json.dumps(
                    arguments,
                    default=str,
                )

            except Exception:

                serialized_arguments = "{}"

            if len(
                serialized_arguments
            ) > MAX_TOOL_ARGUMENT_CHARS:

                logger.warning(
                    "AB AI tool arguments exceeded "
                    "maximum size. tool=%s",
                    name,
                )

                result = {
                    "success": False,
                    "error": (
                        "The requested operation "
                        "contained too much information."
                    ),
                }

                tool_results.append(
                    result
                )

                continue

            # ------------------------------------------------
            # LOG TOOL
            # ------------------------------------------------

            logger.info(
                "AB AI executing tool: %s",
                name,
            )

            # ------------------------------------------------
            # EXECUTE DJANGO TOOL
            # ------------------------------------------------

            result = execute_tool(
                name=name,
                arguments=arguments,
                conversation=conversation,
            )

            tool_results.append(
                result
            )

        # ----------------------------------------------------
        # SEND TOOL RESULTS BACK TO GEMINI
        # ----------------------------------------------------

        tool_response_content = (
            build_tool_response_content(
                function_calls,
                tool_results,
            )
        )

        if tool_response_content is None:

            raise ValueError(
                "Could not construct Gemini tool response."
            )

        contents.append(
            tool_response_content
        )

        # ----------------------------------------------------
        # NEXT GEMINI REQUEST
        # ----------------------------------------------------

        response = (
            generate_content_with_retry(
                model=MODEL,
                contents=contents,
                config=config,
            )
        )

    # ========================================================
    # TOOL LOOP SAFETY
    # ========================================================

    remaining_function_calls = (
        extract_function_calls(
            response
        )
    )

    if remaining_function_calls:

        logger.error(
            "AB AI reached maximum tool rounds."
        )

        raise GeminiUnavailable(
            (
                "AB AI could not complete the "
                "requested operation."
            )
        )

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    return parse_final_response(
        response
    )