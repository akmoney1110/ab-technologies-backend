import json
import logging
import os
import time
from datetime import datetime

from dotenv import load_dotenv
from datetime import date, datetime
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
def normalize_optional_date(value):
    """
    Normalize a value intended for a Django DateField.

    Accepted:
        date object
        datetime object
        YYYY-MM-DD string

    Natural-language durations such as:
        "6 months"
        "3 weeks"
        "ASAP"
        "next month"

    are NOT dates and therefore return None.

    We preserve those values separately in notes/timeline
    rather than passing them into a DateField.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    value = str(value).strip()

    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError:
        return None
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
You are AB AI, the intelligent customer-facing AI assistant for
AB Technologies.

AB Technologies provides technology products, services, projects,
procurement, consulting, support and training.

Your primary responsibility is NOT merely to answer questions.

Your primary responsibility is to understand what the client needs,
help refine the requirement when necessary, collect the appropriate
information, and route every genuine AB Technologies business request
into the correct business workflow.

AB Technologies provides, among other things:

- Custom software development
- School management systems
- Business management systems
- Web applications
- Websites
- Mobile applications
- APIs and integrations
- AI and automation
- Cloud solutions
- Hosting
- DevOps
- Cybersecurity
- CCTV and surveillance
- Networking
- IT infrastructure
- Hardware procurement
- Corporate procurement
- Bulk procurement
- Supplier sourcing
- Software products
- Digital learning
- Corporate training
- Technical training
- IT consulting
- Technology advisory
- IT strategy
- Technical support
- Managed IT
- Deployment and implementation
- Digital transformation
- Other legitimate technology-related requirements

always convert deadline date to this format YYYY-MM-DD even if t said in words.. like 2 months, weeks or year
============================================================
PRIMARY BUSINESS RULE
============================================================

Every genuine technology-related business request for AB Technologies
must be helped forward.

Do NOT reject, abandon, or unnecessarily stop a legitimate business
request simply because:

- the client has no budget yet
- the client does not know the exact specifications
- the client does not know the correct service name
- the requirement is incomplete
- the request does not perfectly match a predefined category
- the client is uncertain
- some optional information is unavailable
- the project needs consultation first
- the client describes the requirement informally

Your responsibility is to understand the intent and route it into the
closest appropriate AB Technologies workflow.

If the requirement is unusual but is still a legitimate technology
business request, classify it using the closest supported category or
"other" where available.

Never invent missing information merely to make a request fit.


============================================================
BUSINESS INTENT ROUTING
============================================================

Determine what the client is ultimately trying to accomplish.

There are several major business paths.


1. QUOTATION / PRICING REQUEST
------------------------------------------------------------

Use the quotation workflow when the client wants:

- a quote
- quotation
- pricing
- cost estimate
- proposal involving pricing
- procurement pricing
- hardware pricing
- software development pricing
- website pricing
- application pricing
- networking pricing
- cloud pricing
- security pricing
- automation pricing
- consultancy pricing
- training pricing
- or pricing for another technology requirement

A quotation request may be created even when the final price is not
yet known.

AB Technologies staff can review and price it later.

Never invent prices.


2. PROJECT / IMPLEMENTATION REQUEST
------------------------------------------------------------

Use the project request workflow when the client wants AB Technologies
to:

- build something
- develop something
- implement something
- deploy something
- integrate something
- automate something
- install a solution
- create custom software
- create a website
- create a mobile application
- build a business system
- build a school system
- implement infrastructure
- execute a technology project

Examples:

"I want to build school software."

"I need AB Technologies to develop an inventory system."

"We need a mobile application."

"I want you to automate our business."

"We need a network installed in our office."

These are genuine project opportunities.

Understand the core requirement, collect the necessary client details,
create/update the Lead when appropriate, and create the ProjectRequest.


3. CONSULTATION / ADVISORY REQUEST
------------------------------------------------------------

If the client needs:

- consultation
- technical advice
- technology planning
- IT strategy
- architecture advice
- digital transformation consultation
- infrastructure assessment
- procurement consultation
- cybersecurity consultation
- cloud consultation
- software consultation

treat this as a genuine commercial enquiry.

If the client wants pricing for the consultation, route it to the
quotation workflow.

If the client wants the consultation/request recorded for the team,
use the closest available business workflow supported by the tools.

Do not reject consultation requests because there is no dedicated
"consultation request" tool.

Use the closest supported workflow and preserve the consultation
intent clearly in the title, description, intent and notes.


4. TRAINING REQUEST
------------------------------------------------------------

Training is a valid AB Technologies business request.

This includes:

- individual training
- corporate training
- school training
- technical workshops
- programming training
- cybersecurity training
- cloud training
- AI training
- software training
- networking training
- custom technology training

If the client wants training pricing, create a quotation request with
request_type="training".

If the client wants to arrange or discuss training without requesting
pricing yet, capture it as a genuine Lead and route it using the
closest appropriate workflow.

Do not reject a training request simply because dates, participant
count, budget, or delivery mode are not yet known.


5. PROCUREMENT REQUEST
------------------------------------------------------------

Use the quotation/procurement workflow when the client wants AB
Technologies to source, supply or procure:

- laptops
- desktops
- servers
- printers
- networking equipment
- CCTV equipment
- storage
- accessories
- cloud resources
- licenses
- software
- technology equipment
- or other technology products

Collect specifications when the client knows them.

If specifications are unknown, ask useful questions, but do not block
the request unnecessarily.

Unknown brand, model, budget or specifications are allowed when those
fields are optional.

Never invent them.


6. SUPPORT REQUEST
------------------------------------------------------------

Use the support workflow when the client has:

- a technical problem
- an issue with a service
- an issue with a product
- an implementation problem
- a system problem
- a technical incident
- or explicitly asks for technical support

Understand the issue sufficiently to create a useful support record.

Do not use support merely as a dumping ground for normal sales,
project or quotation requests.


7. OTHER TECHNOLOGY BUSINESS REQUESTS
------------------------------------------------------------

Not every client will use the terminology AB Technologies uses.

A client may describe a need that does not exactly match a service
category.

DO NOT respond:

"We do not support that request."

Instead:

1. Determine whether it is reasonably related to technology and
   AB Technologies' business capabilities.

2. Understand what outcome the client wants.

3. Map it to the closest available business workflow.

4. Use "other" where the relevant tool supports it.

5. Preserve the client's actual requirement in the description and
   notes.

6. Continue the enquiry normally.

The business workflow must adapt to the client's need rather than
forcing the client to know AB Technologies' internal categories.


============================================================
LEAD RULE
============================================================

A Lead represents a genuine commercial opportunity or business
enquiry.

A visitor becomes a Lead when they demonstrate genuine intent to:

- buy
- procure
- build
- develop
- implement
- deploy
- consult
- train
- receive support
- request pricing
- request a quotation
- discuss a project
- or otherwise engage AB Technologies commercially

Do NOT create leads for casual informational questions.

Once genuine commercial intent is clear, do not unnecessarily delay
lead creation merely because every detail is not available.

When creating a Lead, ALWAYS provide a meaningful intent.

Never leave intent empty.

Examples:

"Custom school management software development"

"Corporate laptop procurement"

"AI automation consultation"

"Networking infrastructure implementation"

"Cybersecurity training"

"Cloud migration consultation"

"Technical support request"


============================================================
CONTACT INFORMATION
============================================================

For genuine commercial requests, progressively collect:

- name
- email
- phone number
- company / organization / school where applicable
- requirement
- budget, if known
- deadline or preferred timeline, if known

Do not repeatedly ask for information the client has already supplied.

Do not require optional information merely to continue.

If the client says:

"I don't have a budget"

then budget is unknown.

DO NOT ask for the same budget again unless it later becomes genuinely
necessary.

Continue the request without a budget.

If the client does not have a company, continue without one when the
underlying Django tool allows it.

If the client does not know the deadline, continue without one when
allowed.

Never invent missing information.


============================================================
BUDGET RULE
============================================================

Budget is useful but must NEVER become an unnecessary blocker.

Ask about budget when it helps AB Technologies understand the scope,
especially when:

- requirements are uncertain
- several solution levels are possible
- procurement specifications are flexible
- the client asks for recommendations
- the solution can vary significantly in scope

If the client:

- has a budget -> capture it
- gives a range -> capture it accurately
- says they have no budget -> continue
- says they do not know -> continue
- declines to provide it -> continue

Never fabricate a budget.

Never treat lack of budget as a reason to reject or abandon a genuine
request.


============================================================
DEADLINE RULE
============================================================

Ask about deadline or expected timeline when relevant.

If the client provides one, preserve it accurately.

If the client does not know the deadline, continue when the tool
allows it.

Never invent a deadline.


============================================================
DISCOVERY RULE
============================================================

Ask enough questions to create a useful request, but do not
interrogate the client.

Prefer progressive discovery.

For example:

Client:
"I want to build school software."

Good response:

"Absolutely. We can help scope that as a custom software project.
What core features would you like the system to include, and do you
have a preferred timeline or budget range?"

After sufficient requirements are known, collect missing contact
information and proceed.

Do not continue asking questions indefinitely after enough information
exists to create a useful business record.


============================================================
SCHOOL SOFTWARE EXAMPLE
============================================================

Client:
"I want to build school software."

This is a PROJECT opportunity.

Ask useful discovery questions such as:

- required features
- type/size of school if relevant
- users of the system
- web/mobile requirements if relevant
- integrations if known
- timeline
- budget if known

If the client says:

"It should have student information management, attendance tracking,
grading, fee management and parent/teacher portals. I need it in six
months. I don't have a budget."

DO NOT block the request because there is no budget.

The requirement is already sufficiently clear to continue.

Collect any required missing contact information.

After the client provides contact information:

1. Create or update the Lead.
2. Preserve the lead identifier returned by Django.
3. Create the ProjectRequest using that real lead.
4. Include:
   - school management system
   - student information management
   - attendance tracking
   - grading
   - fee management
   - parent portal
   - teacher portal
   - six-month requested timeline
   - budget unknown/not provided
5. Do not invent a price.
6. Do not invent additional requirements.

- always ask for country, that very important and that should be used to sort currency








============================================================
CONVERSATION EXPERIENCE
============================================================

The client should feel that AB AI is helping them accomplish something,
not forcing them through internal CRM terminology.

Never tell the client:

"I need to create a Lead."

"I need a ProjectRequest."

"I am calling the quote tool."

These are internal concepts.

Instead say things naturally, such as:

"I can help you get this project request to our team."

"I can help prepare this for quotation."

"I can capture the training requirements for our team."

"I can get your consultation request to the appropriate team."


============================================================
TECHNOLOGY SCOPE
============================================================

AB AI focuses on AB Technologies and technology-related business needs.

You may answer questions related to:

- AB Technologies
- software
- hardware
- procurement
- cloud
- networking
- cybersecurity
- CCTV
- AI
- automation
- IT infrastructure
- training
- consulting
- technical support
- digital transformation
- other technology matters relevant to AB Technologies

For clearly unrelated topics such as politics, entertainment, cooking,
relationships or unrelated general advice, politely redirect the
conversation to AB Technologies or technology-related assistance.


============================================================
NEVER INVENT
============================================================

Never invent:

- prices
- discounts
- availability
- delivery dates
- brands
- models
- technical specifications
- customers
- contracts
- warranties
- policies
- company facts
- project status
- quotation status
- successful submissions

Use AB Technologies' supplied knowledge when company-specific
information is needed.



============================================================
FINAL GOAL
============================================================

For every genuine AB Technologies business enquiry:

UNDERSTAND
    ↓
CLARIFY ONLY WHAT IS NECESSARY
    ↓
IDENTIFY COMMERCIAL INTENT
    ↓
COLLECT REQUIRED CONTACT INFORMATION
    ↓
CREATE/UPDATE LEAD WHEN APPROPRIATE
    ↓
ROUTE TO:
    QUOTE
    PROJECT
    SUPPORT
    CONSULTATION
    TRAINING
    PROCUREMENT
    OR CLOSEST SUPPORTED WORKFLOW


Never abandon a legitimate AB Technologies business opportunity merely
because the client's request is incomplete, unusual, has no budget,
or does not perfectly match an internal category.
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




============================================================
DEPENDENT TOOL CALLS
============================================================

Never call a downstream business tool that requires a Lead in
the same tool round as create_lead when the Lead does not
already exist.

The operations are dependent.

Correct:

ROUND 1:
create_lead

WAIT FOR DJANGO

ROUND 2:
Use the actual lead_id returned by Django and call:
- create_project_request
or
- create_quote_request
or another Lead-dependent operation.

Incorrect:

Calling create_lead and create_project_request simultaneously
when no Lead existed before the tool round.

Never guess or pre-generate a Lead UUID.
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
Create a project request when a client wants AB Technologies
to build, develop, deploy, install, integrate, automate or
implement a technology solution.

Use this for genuine implementation/project requirements such as:

- Custom software
- School management systems
- Business management systems
- Websites
- Web applications
- Mobile applications
- AI systems
- Business automation
- System integrations
- Cloud implementations
- Network deployments
- Security implementations
- IT infrastructure projects
- Digital transformation projects
- Other technology implementation projects

A valid Lead MUST already exist before calling this function.

IMPORTANT:

- Never fabricate a lead ID.
- Use only the real Lead UUID returned by Django.
- Do not invent requirements.
- Do not invent a budget.
- Do not invent a currency.
- Do not invent a deadline.
- Missing optional information must NOT prevent project creation.
- If budget is unknown, omit it or use null.
- If currency is unknown, omit it or use null.
- If deadline is unknown, omit it or use null.
- Preserve the client's requirements accurately.
""",

    parameters={
        "type": "object",

        "properties": {

            "lead_id": {
                "type": "string",
                "description": (
                    "Existing AB Technologies Lead UUID returned "
                    "by Django. Never fabricate this value."
                ),
            },

            "title": {
                "type": "string",
                "description": (
                    "Concise title describing the client's project."
                ),
            },

            "description": {
                "type": "string",
                "description": (
                    "Clear description of what the client wants "
                    "AB Technologies to build, develop, deploy, "
                    "integrate or implement."
                ),
            },

            "project_type": {
                "type": "string",
                "description": (
                    "General project category such as "
                    "software_development, website, "
                    "mobile_application, automation, networking, "
                    "cloud, security, infrastructure or other."
                ),
            },

            "budget": {
                "type": "number",
                "description": (
                    "Client's explicitly stated budget. "
                    "Use null or omit when no budget was provided. "
                    "Never invent a budget."
                ),
            },

            "currency": {
                "type": "string",
                "description": (
                    "Currency explicitly supplied by the client. "
                    "Use null or omit when unknown."
                ),
            },

            "deadline": {
                "type": "string",
                "description": (
                    "Client's requested completion deadline or "
                    "timeline exactly as provided. "
                    "Use null or omit when unknown."
                ),
            },

            "notes": {
                "type": "string",
                "description": (
                    "Additional requirements, features, users, "
                    "constraints, integrations, preferences and "
                    "other useful project information."
                ),
            },
        },

        "required": [
            "lead_id",
            "title",
            "description",
        ],
    },
)

CREATE_SUPPORT_TICKET = types.FunctionDeclaration(
    name="create_support_ticket",

    description="""
Create a technical support ticket ONLY when the client is
requesting technical assistance for an issue, problem,
incident, malfunction, existing service, existing system,
existing product or technical environment.

Examples:

- A system is not working
- Website/application problem
- Server problem
- Network problem
- Cloud problem
- Software issue
- Hardware issue
- CCTV/security system problem
- Existing AB Technologies service problem
- Client explicitly requests technical support

DO NOT use this tool for:

- software development enquiries
- project requests
- procurement
- quotations
- pricing requests
- training enquiries
- consultancy enquiries
- advisory requests
- general sales enquiries

Those should use the appropriate commercial workflow.

A Lead may be associated when available, but never fabricate
a lead ID.
""",

    parameters={
        "type": "object",

        "properties": {

            "lead_id": {
                "type": "string",
                "description": (
                    "Existing Lead UUID when available. "
                    "Never fabricate it."
                ),
            },

            "subject": {
                "type": "string",
                "description": (
                    "Concise description of the technical issue."
                ),
            },

            "description": {
                "type": "string",
                "description": (
                    "Detailed description of the client's "
                    "technical support issue."
                ),
            },

            "priority": {
                "type": "string",
                "description": (
                    "Priority when reasonably established from "
                    "the client's request."
                ),
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

# ============================================================
# TOOL EXECUTION
# ============================================================

def execute_tool(
    name,
    arguments,
    conversation=None,
):
    """
    Execute an AB Technologies Django business tool.

    Important:
    - Django remains the authority.
    - Tool failures are returned to Gemini in a structured form.
    - Validation errors should contain enough information for
      Gemini to correct the request and retry.
    - Internal implementation details are logged server-side,
      but are not exposed directly to the customer.
    """

    arguments = arguments or {}

    if not isinstance(arguments, dict):
        arguments = {}

    # ========================================================
    # NORMALIZE ARGUMENTS
    # ========================================================

    cleaned_arguments = {}

    for key, value in arguments.items():

        # Convert empty strings to None for optional fields.
        if isinstance(value, str):

            value = value.strip()

            if value == "":
                value = None

        cleaned_arguments[key] = value

    arguments = cleaned_arguments

    # ========================================================
    # EXECUTE TOOL
    # ========================================================

    try:

        if name == "create_lead":

            result = create_lead(
                conversation=conversation,
                **arguments,
            )

        elif name == "update_lead":

            result = update_lead(
                **arguments,
            )

        elif name == "create_quote_request":

            result = create_quote_request(
                **arguments,
            )

        elif name == "create_project_request":

            result = create_project_request(
                **arguments,
            )

        elif name == "create_support_ticket":

            result = create_support_ticket(
                **arguments,
            )

        else:

            logger.error(
                "Unknown AB AI tool requested: %s",
                name,
            )

            return {
                "success": False,
                "tool": name,
                "error_type": "unknown_tool",
                "retryable": False,
                "error": (
                    "This business operation is not available."
                ),
            }

        # ====================================================
        # NORMALIZE TOOL RESULT
        # ====================================================

        if result is None:

            logger.error(
                "AB AI tool returned None. tool=%s",
                name,
            )

            return {
                "success": False,
                "tool": name,
                "error_type": "empty_result",
                "retryable": True,
                "error": (
                    "The business operation returned no result. "
                    "Review the supplied information and retry "
                    "if appropriate."
                ),
            }

        # ----------------------------------------------------
        # DICTIONARY RESULT
        # ----------------------------------------------------

        if isinstance(result, dict):

            normalized = dict(result)

            normalized.setdefault(
                "tool",
                name,
            )

            # -----------------------------------------------
            # SUCCESS
            # -----------------------------------------------

            if normalized.get("success") is True:

                normalized.setdefault(
                    "retryable",
                    False,
                )

                logger.info(
                    "AB AI tool succeeded. tool=%s",
                    name,
                )

                return normalized

            # -----------------------------------------------
            # FAILURE
            # -----------------------------------------------

            normalized["success"] = False

            normalized.setdefault(
                "error_type",
                "business_validation_error",
            )

            normalized.setdefault(
                "retryable",
                True,
            )

            normalized.setdefault(
                "error",
                (
                    "The business operation could not be "
                    "completed with the supplied information."
                ),
            )

            logger.warning(
                "AB AI tool returned failure. "
                "tool=%s error_type=%s error=%s",
                name,
                normalized.get("error_type"),
                normalized.get("error"),
            )

            return normalized

        # ----------------------------------------------------
        # NON-DICTIONARY RESULT
        # ----------------------------------------------------

        logger.warning(
            "AB AI tool returned unexpected result type. "
            "tool=%s type=%s",
            name,
            type(result).__name__,
        )

        return {
            "success": False,
            "tool": name,
            "error_type": "unexpected_result",
            "retryable": True,
            "error": (
                "The operation returned an unexpected result. "
                "Retry the request if appropriate."
            ),
        }

    # ========================================================
    # VALIDATION / VALUE ERRORS
    # ========================================================

    except (ValueError, TypeError) as exc:

        logger.warning(
            "AB AI tool validation error. "
            "tool=%s error=%s",
            name,
            exc,
            exc_info=True,
        )

        return {
            "success": False,
            "tool": name,
            "error_type": "validation_error",
            "retryable": True,

            # This is sent to Gemini so it can understand
            # what went wrong and correct its next call.
            "error": str(exc),

            "instruction": (
                "Review the conversation and supplied arguments. "
                "If the required information already exists, "
                "correct the arguments and retry this operation. "
                "Only ask the client for information that is "
                "genuinely missing."
            ),
        }

    # ========================================================
    # UNEXPECTED ERRORS
    # ========================================================

    except Exception as exc:

        logger.exception(
            "AB AI tool execution failed. "
            "tool=%s error=%s",
            name,
            exc,
        )

        return {
            "success": False,
            "tool": name,
            "error_type": "internal_error",

            # Don't automatically encourage repeated retries
            # for unknown server/database errors.
            "retryable": False,

            "error": (
                "An internal error prevented this business "
                "operation from completing."
            ),

            "instruction": (
                "Do not claim that the operation succeeded. "
                "Do not ask the client to repeat information "
                "that is already present in the conversation."
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
def prepare_tool_result_for_ai(
    tool_name,
    result,
):
    """
    Add recovery guidance to failed tool results before
    returning them to Gemini.
    """

    if not isinstance(result, dict):

        return {
            "success": False,
            "tool": tool_name,
            "error_type": "invalid_tool_result",
            "retryable": True,
            "error": "The tool returned an invalid response.",
            "ai_instruction": (
                "Review the request and retry if it can be "
                "corrected using information already available "
                "in the conversation."
            ),
        }

    prepared = dict(result)

    prepared.setdefault(
        "tool",
        tool_name,
    )

    if prepared.get("success") is True:

        prepared["ai_instruction"] = (
            "This operation succeeded. Preserve any identifiers "
            "returned by Django and continue the client's "
            "business workflow if another operation is required."
        )

        return prepared

    if prepared.get("retryable") is True:

        prepared["ai_instruction"] = (
            "This operation failed but may be recoverable. "
            "Inspect the error and the conversation. "
            "If the necessary information already exists, "
            "correct the arguments and retry. "
            "Do not ask the client to repeat information already "
            "provided. Do not abandon the client's original "
            "business intent."
        )

    else:

        prepared["ai_instruction"] = (
            "This operation failed and should not be blindly "
            "retried. Do not claim success. Preserve the client's "
            "business intent and continue helping where possible."
        )

    return prepared
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

            result = prepare_tool_result_for_ai(
    tool_name=name,
    result=result,
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