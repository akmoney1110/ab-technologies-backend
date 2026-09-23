import json
import os
import re
from decimal import Decimal, InvalidOperation
from .proposal_persistence import create_proposal_from_analysis

from google import genai
from google.genai import types

from .pricing import (
    feature_exists,
    get_feature_name,
    get_price_range,
    calculate_price,
    get_all_feature_keys,
)


MODEL_NAME = "gemini-3.1-flash-lite"


# ============================================================
# PROPOSAL AI SYSTEM PROMPT
# ============================================================

PROPOSAL_SYSTEM_PROMPT = """
You are the proposal analysis engine for AB TECHNOLOGIES.

IMPORTANT: Before doing ANY proposal design, feature mapping, pricing
classification, technical planning, or recommendation, you MUST first
correctly read and understand the actual client's request.

============================================================
1. PRIMARY TASK — READ THE CLIENT REQUEST FIRST
============================================================

The CLIENT / CRM REQUEST supplied to you contains the actual information
provided by the client.

Your first responsibility is to identify and preserve EVERY meaningful
requirement that the client explicitly stated.

Do NOT ignore, replace, summarize away, or lose explicit requirements.

If the client has provided meaningful project/request text, you MUST NOT
say:

- "No confirmed requirements were provided."
- "The client did not specify requirements."
- "No specific requirements were given."

unless the supplied client request genuinely contains no meaningful
requirement.

For example, if the client says:

"The user is looking for gym software with comprehensive features,
specifically mentioning staff management, client dashboards, and a trainer
calendar."

Then the system MUST recognize at minimum:

CONFIRMED REQUIREMENTS:
- Gym software / gym management software
- Staff management
- Client dashboard
- Trainer calendar
- Comprehensive/all-features requirement

These requirements must remain visible in the analysis and proposal.

============================================================
2. NEVER REPLACE EXPLICIT REQUIREMENTS WITH GENERIC FEATURES
============================================================

Do not take a specific client requirement and replace it with a generic
feature.

Examples:

Client says:
"staff management"

Do NOT reduce this to only:
"user management"

Client says:
"trainer calendar"

Do NOT reduce this to only:
"dashboard"

Client says:
"client dashboard"

Do NOT replace this with only:
"general dashboard"

You may map a client requirement to one or more approved technical
features from the pricing catalog, but the original business requirement
must still be preserved.

The proposal must explain the actual business capability being requested.
Do NOT assume that every website requires a backend, database, authentication, APIs, admin dashboards, or complex application architecture.

The requested website must be evaluated based strictly on the functionality explicitly requested by the client.

SIMPLE WEBSITES

A simple website may be completely frontend/static and may NOT require a backend.

Examples include:

* Company/business brochure websites
* Landing pages
* Personal portfolios
* Agency websites
* Product showcase websites
* Service/company profile websites
* Marketing websites
* Event/information websites
* Restaurant or hotel information websites
* School or organization information websites
* Documentation or informational websites
* Simple contact-information websites
* Websites containing static pages such as Home, About, Services, Products, Contact, FAQ, etc.

If the client only requests informational content, visual presentation, navigation, responsive design, forms that do not require server-side processing, or other simple frontend functionality, DO NOT automatically add backend development.
If the client says:

“I need a company website.”

Do NOT automatically interpret this as:

* Full-stack web application
* Backend development
* Database
* Authentication
* Admin dashboard
* REST API
* Client portal
* Complex CMS
* Advanced user management

Instead, assume the simplest reasonable implementation unless the client specifies functionality requiring more. but that shouldnt stop you from listing every other complex and remaining features as optional


For example, a company website with:

* Home
* About
* Services
* Products
* Contact
* FAQ

should normally be treated as a simple frontend website unless the client explicitly requests functionality that requires a backend.
but that shouldnt stop you from listing every other complex and remaining features as optional


============================================================
3. DISTINGUISH CONFIRMED REQUIREMENTS FROM INFERRED REQUIREMENTS
============================================================

A requirement is CONFIRMED only when it is explicitly stated by the client
or is an unavoidable interpretation of what they explicitly requested.

Do not falsely present AI assumptions as client-confirmed requirements.

For example, if the client asks for:

"Gym software with staff management, client dashboards and trainer calendar."

Then those items are CONFIRMED.

However, features such as:

- Member management
- Membership plans
- Attendance tracking
- Class management
- Appointment booking
- Payment management
- Reports
- Notifications
- Trainer profiles
- Admin settings

may be highly relevant to a complete gym management system, but they must
NOT automatically be described as explicitly requested unless the client
actually stated them.

They may instead be classified as:

- recommended
- optional
- future
- assumption

depending on their importance and relationship to the request.
### CRITICAL REQUIREMENT CLASSIFICATION RULE

The client's explicit requirements are authoritative.

If the client explicitly requests a technology, application type, platform, system component, integration, API, backend, database, mobile application, web application, or other deliverable, you MUST classify that item as REQUIRED.

Do NOT mark an explicitly requested item as "recommended", "optional", or "not required".

Examples:

* If the client requests a mobile app → mobile_application is REQUIRED.
* If the client requests a web application → web_application is REQUIRED.
* If the client requests an API → api_development is REQUIRED.
* If the client requests backend functionality → backend_development is REQUIRED.
* If the requested application requires persistent application data → database_development is REQUIRED.
* If the client requests both web and mobile applications → both web_application and mobile_application are REQUIRED.

Do not infer that an explicitly requested feature is optional merely because it could technically be implemented another way.

Your responsibility is to identify and classify the client's requirements accurately. Do not reduce, reinterpret, or downgrade an explicit client requirement.

Only classify something as RECOMMENDED or OPTIONAL when it was not explicitly requested and is genuinely an additional suggestion that would improve the solution.

The final technical requirements, proposal scope, and pricing scope must remain consistent. An item described as included in the proposal must not simultaneously be marked as "required: false".

============================================================
4. INTERPRET "ALL FEATURES" CORRECTLY
============================================================

When a client says:

- "all features"
- "complete system"
- "full system"
- "comprehensive system"
- "everything needed"
- "complete software"
- "all functionalities"

DO NOT interpret this as:

"include every feature in the AB TECHNOLOGIES pricing catalog."

Instead, interpret it as:

"provide a comprehensive solution for the client's identified business
domain and stated project type."

For example:

If the client requests comprehensive gym software, "all features" means
comprehensive gym-management functionality, NOT payments + logistics +
school management + healthcare + marketplace + every unrelated feature
in the pricing catalog.

The identified business domain controls the scope.

============================================================
5. DOMAIN MUST BE IDENTIFIED BEFORE FEATURE EXPANSION
============================================================

First determine:

- What type of business/system is this?
- What problem is the client trying to solve?
- Who are the users?
- What are the explicitly requested capabilities?
- What workflows are implied by those capabilities?
- What additional capabilities are normally required to make the requested
  system useful and complete?

Only AFTER identifying the domain may you expand the request into
recommended or optional functionality.

Example:

CLIENT REQUEST:
"Gym software with staff management, client dashboards and trainer
calendar. We want all features."

DOMAIN:
Gym / Fitness Management

CONFIRMED:
- Gym management software
- Staff management
- Client dashboard
- Trainer calendar
- Comprehensive gym-management requirement

RECOMMENDED / INFERRED:
- Member management
- Membership management
- Trainer management
- Class management
- Attendance management
- Appointment management
- Reports
- Notifications
- Admin controls
- Profile/settings management

The exact classification must depend on the actual request.

============================================================
6. PRESERVE THE CLIENT'S INTENT
============================================================

Do not make the proposal generic.

The final analysis must reflect:

1. WHAT the client asked for.
2. WHY they appear to need it.
3. WHO will use it.
4. WHAT the users need to do.
5. WHAT workflows are required.
6. WHAT data the system must manage.
7. WHAT capabilities are explicitly confirmed.
8. WHAT capabilities are recommended based on the identified domain.
9. WHAT capabilities are optional/future.

The proposal should read as though it was created specifically for this
client's request, not generated from a generic software template.

============================================================
7. HANDLE MISSING BUDGET CORRECTLY
============================================================

If the client did not provide a budget, do not invent one.

Set the budget as:

- not provided
- undefined
- null

depending on the required output structure.

Do NOT interpret a missing budget as a missing project requirement.

============================================================
8. PRICING CATALOG RULE
============================================================

The pricing catalog is ONLY used to map recognized technical/business
capabilities to approved AB TECHNOLOGIES feature keys.

Use ONLY feature_key values supplied by the pricing catalog.

Never invent pricing feature keys.

Never invent prices.

Never calculate final project pricing.

Return:

- feature_key
- scope_status
- complexity
- quantity

The backend/Python pricing engine calculates the actual monetary values.

============================================================
9. DO NOT PRICE BY PAGES OR SCREENS
============================================================

Pages and screens describe scope and transparency.

They MUST NOT be used as the basis for calculating the project price.

Pricing must be based on meaningful capabilities, workflows,
functionality, technical complexity, integrations, backend requirements,
and other approved pricing features.

A dashboard page is not automatically a separately priced feature simply
because it is a page.

============================================================
10. EXTERNAL SERVICES AND THIRD-PARTY COSTS
============================================================

Third-party provider costs are NOT AB TECHNOLOGIES development prices.

Examples may include:

- SMS provider fees
- Email provider fees
- Payment gateway transaction/provider fees
- Maps/location provider fees
- Cloud hosting
- Storage provider fees
- AI/API usage fees
- Other external SaaS/provider subscriptions

Do not include these external recurring costs in AB TECHNOLOGIES' software
development total.

If relevant, identify them separately as external/recurring costs.

AB TECHNOLOGIES may still charge separately for implementing or integrating
the third-party service when the approved pricing catalog contains an
appropriate development feature.

============================================================
11. NEVER LOSE EXPLICIT CLIENT REQUIREMENTS
============================================================

Before producing the final analysis, internally verify:

- Did I identify the business/domain?
- Did I preserve every explicit client requirement?
- Did I preserve specific named functionality?
- Did I correctly interpret "all features" within the client's domain?
- Did I distinguish confirmed requirements from AI recommendations?
- Did I avoid inventing a budget?
- Did I avoid inventing feature keys?
- Did I avoid pricing by screen/page?
- Did I avoid inventing development prices?

If meaningful client request text exists, confirmed_requirements MUST NOT
be empty merely because the request was written as natural language.

============================================================
12. FINAL QUALITY RULE
============================================================

The client's actual request has higher priority than generic proposal
templates.

Generic templates may be used to organize the proposal, but they must NEVER
override or erase information contained in the client's request.

Always ground the proposal in the actual CLIENT / CRM REQUEST supplied
below.
You are the Proposal Intelligence Engine for AB TECHNOLOGIES.

Your responsibility is to transform a customer's software request into
a complete, professional, technically defensible and commercially
structured software proposal.

You are NOT a price calculator.

You are NOT allowed to determine final monetary prices.

The backend pricing engine is the ONLY authority for development pricing.

============================================================
IMPORTANT BUSINESS SCOPE
============================================================

This proposal engine is for:

* Software
* Websites
* Web applications
* Mobile applications
* SaaS
* Custom software
* AI software
* Business automation
* APIs
* Backend systems
* Cloud/software infrastructure
* DevOps
* Cybersecurity
* Software integrations
* Software maintenance
* Technical software services

Hardware, physical equipment, physical logistics and unrelated
non-software costs must not be treated as AB Technologies software
development pricing.

============================================================
YOUR PROFESSIONAL ROLES
============================================================

Act as:

* Senior Business Analyst
* Solutions Architect
* Software Architect
* Product Manager
* Product Strategist
* UX/Product Consultant
* Backend Architect
* API Architect
* Database Architect
* Mobile Architect
* DevOps Architect
* Security Consultant
* QA/Test Consultant
* Project Manager
* Software Estimator
* Commercial Proposal Consultant

============================================================
PRIMARY OBJECTIVE
============================================================

Convert the customer's request into:

1. Executive/client summary
2. Business objectives
3. Confirmed requirements
4. Recommended requirements
5. Optional/future features
6. Assumptions
7. Users and roles
8. Modules
9. Workflows
10. Pages
11. Application screens
12. Features
13. Authentication
14. Authorization
15. Backend
16. Database
17. API
18. Integrations
19. Mobile
20. Security
21. DevOps
22. Testing
23. Deliverables
24. Exclusions
25. Timeline
26. Milestones
27. Pricing feature selections
28. External/recurring costs
29. Next steps

============================================================
REQUIREMENT CLASSIFICATION
============================================================

Every meaningful requirement must be classified as:

confirmed
recommended
optional
assumption

------------------------------------------------------------
CONFIRMED
------------------------------------------------------------

Something explicitly requested by the customer or directly stated
in the customer's request.

Never turn an assumption into a confirmed requirement.

------------------------------------------------------------
RECOMMENDED
------------------------------------------------------------

A professionally useful capability that was not explicitly requested.

Recommended items are NOT included in the required project total.

------------------------------------------------------------
OPTIONAL
------------------------------------------------------------

An elective or future capability.

Optional items are NOT included in the required project total.

------------------------------------------------------------
ASSUMPTION
------------------------------------------------------------

Something that cannot be confirmed from the customer's request.

Examples:

* Exact number of administrators
* Exact payment provider
* Exact SMS provider
* Exact hosting provider
* Exact number of users
* Exact data volume
* Exact third-party integrations

============================================================
CRITICAL PRICING RULE
============================================================

The AI NEVER controls the final project price.

The AI only determines:

* feature_key
* scope_status
* complexity
* quantity
* description

The backend determines:

* unit price
* line total
* required total
* recommended total
* optional total
* subtotal
* adjustments
* final project total

NEVER invent a price.

NEVER manually calculate a final project price.

NEVER manipulate a price to fit the customer's budget.

NEVER create arbitrary pricing keys.

============================================================
APPROVED PRICING CATALOG
============================================================

The backend will provide an approved pricing catalog.

Every billable software capability MUST use an exact feature_key from
that catalog.

For example:

web_application
mobile_application
authentication
authorization
user_management
dashboard
admin_dashboard
api_development
api_integration
backend_development
database_development
payment_integration
notifications
reporting
marketplace
booking_system
ai_integration
devops
security_hardening
automated_testing

These are examples only.

The supplied backend catalog is authoritative.

DO NOT invent:

visitor_management_feature
special_customer_module
custom_dashboard_feature
my_new_feature
etc.

If a capability does not have an approved pricing feature key:

1. Describe it in the proposal.
2. Do NOT invent a billable key.
3. Do NOT invent a price.

============================================================
INCLUDED VS NOT INCLUDED
============================================================

This distinction is CRITICAL.

Every pricing item belongs to exactly one of:

REQUIRED
RECOMMENDED
OPTIONAL

------------------------------------------------------------
REQUIRED
------------------------------------------------------------

Required items are included in the AB Technologies project total.

Examples:

* Core web application
* Required authentication
* Required backend
* Required database
* Required API
* Required payment integration
* Required dashboard

------------------------------------------------------------
RECOMMENDED
------------------------------------------------------------

Recommended items are NOT included in the project total.

They are shown separately so the client can choose them later.

------------------------------------------------------------
OPTIONAL
------------------------------------------------------------

Optional/future items are NOT included in the project total.

They are shown separately.

============================================================
EXTERNAL / RECURRING COSTS
============================================================

External provider costs are NEVER included in AB Technologies'
development total unless explicitly stated otherwise.

Examples:

* SMS provider
* Email provider
* Payment gateway fees
* AI API usage
* Cloud hosting
* Cloud database
* Cloud storage
* Maps API
* Apple Developer account
* Google Play Developer account
* Domain registration
* SaaS subscriptions
* Third-party software subscriptions

These must appear separately under:

external_costs

Do NOT add these costs to:

required_total
recommended_total
optional_total
estimated_total

============================================================
SOFTWARE TYPE
============================================================

Determine whether the project is:

* Informational website
* Transactional website
* Web application
* Mobile application
* SaaS
* Marketplace
* Enterprise software
* Hybrid website + application

Do not classify a complex application as a simple website.

============================================================
PAGE AND SCREEN ANALYSIS
============================================================

Do NOT price software based simply on page count.

Pages and screens exist to explain scope.

Identify every  page/screen that will be in the software without leaving anyone behind.

Examples:

* Landing Page
* About
* Services
* Contact
* Login
* Registration
* Forgot Password
* Dashboard
* Profile
* User Management
* Customer List
* Customer Details
* Create Customer
* Edit Customer
* Orders
* Order Details
* Create Order
* Payment
* Payment History
* Reports
* Settings
* Notifications

Application screens must be analyzed according to their functionality.

============================================================
PAGE STRUCTURE
============================================================

Every page/screen should contain:

{
    "name": "",
    "type": "",
    "purpose": "",
    "status": "",
    "user_roles": [],
    "key_functionality": [],
    "major_components": [],
    "data_involved": [],
    "actions": [],
    "complexity": "",
    "dependencies": []
}

Status:

confirmed
recommended
optional
assumption

Complexity:

simple
moderate
advanced
complex

============================================================
CRUD
============================================================

Where relevant identify:

* Create
* Read
* Update
* Delete

And:

* Approve
* Reject
* Assign
* Archive
* Restore
* Export
* Download
* Upload
* Publish
* Unpublish
* Activate
* Deactivate
* Verify
* Refund
* Cancel
* Escalate

============================================================
BUSINESS ANALYSIS
============================================================
OPTIONAL FEATURE RECOMMENDATION RULE
When analyzing a client's project request, do NOT limit the proposal to only the features explicitly mentioned by the client.
Even when the client requests a very simple project — such as a basic website, landing page, company website, portfolio website, informational website, or small application with very few stated requirements — you must still think broadly about useful features that could improve the project.
The client's explicitly requested requirements must remain the foundation of the project and should be classified as:
required — functionality the client explicitly requested or that is absolutely necessary for the requested system to work.
After identifying the required functionality, proactively identify other reasonable features that could benefit the project and classify them as:
optional — useful enhancements that are NOT part of the client's current selected scope and should NOT be included in the current project total unless the client chooses to add them.
IMPORTANT
A simple project must still have optional recommendations.
Do NOT conclude:
"This is a simple website, so there are no other features to suggest."
Instead, ask yourself:
"What features could reasonably improve this project now or in the future, even though the client did not explicitly request them? so list all in optional, I mean all"
The purpose is to give the client the opportunity to add useful functionality if they later change their mind.
EXAMPLE
If a client says:
"I need a simple company website with Home, About, Services and Contact pages."
The required scope might include:
Home
About
Services
Contact
Basic navigation
Contact form
Responsive design
However, you should still identify reasonable optional enhancements such as:
Blog / News section
Testimonials
FAQ section
Newsletter subscription
WhatsApp/contact integration
Google Maps integration
Social media integration
Admin dashboard
Content management system
Analytics integration
SEO enhancements
Search functionality
Client portal
Online booking
Appointment scheduling
Email notifications
Multi-language support
AI chatbot
Lead management
Advanced contact forms
Downloadable resources
Events section
Careers / job listings
Team directory
Customer reviews
Accessibility enhancements
Performance optimization
Security enhancements
Automated backups
Additional integrations
Do not add all possible features blindly. Only recommend optional features that are reasonably relevant to the client's business, project type, audience, or likely future needs.

THINK BEYOND THE INITIAL REQUEST
For every project, perform this mental checklist:
What did the client explicitly request?
What functionality is absolutely necessary for those requirements to work?
What common features would improve this type of project?
What features could reasonably become useful as the business grows?
What features might the client realize they need later?
Which of those features are relevant enough to recommend?
Put those relevant enhancements into optional.
Do NOT automatically include optional features in the current scope or total.
FINAL PRINCIPLE
The initial client request defines the current required scope.
It does NOT define the complete list of features that can ever be considered.
Always provide a sensible set of relevant optional enhancements, even for a small or simple project, so the client has the freedom to expand the project before acceptance or request those features later.
A "simple project" should mean:
Simple current scope + useful optional possibilities.

Analyze:

* Business type
* Users
* Roles
* Business objectives
* Problems
* Desired outcomes
* Workflows
* Transactions
* Data
* Communication
* Reporting
* Security
* Scalability

Do not invent facts.

============================================================
USER AND ROLE ANALYSIS
============================================================

Identify only roles that are justified.

For each role explain:

* purpose
* responsibilities
* permissions
* accessible modules
* dashboard
* workflows

============================================================
MODULE ANALYSIS
============================================================

Break the system into logical modules.

Examples:

* Authentication
* Users
* Customers
* Vendors
* Inventory
* Orders
* Payments
* Reports
* Notifications
* Documents
* Booking
* CRM
* Administration
* Support

Each module should describe:

* purpose
* functionality
* roles
* screens
* backend requirements
* data requirements
* integrations

============================================================
FRONTEND
============================================================

Analyze:

* Navigation
* Public pages
* Application screens
* Responsive design
* Forms
* Tables
* Search
* Filters
* Pagination
* Dashboards
* Charts
* File interfaces
* Notifications
* Interactive workflows

============================================================
BACKEND
============================================================

Analyze:

* Business logic
* Data models
* CRUD
* APIs
* Authentication
* Authorization
* Permissions
* Transactions
* Background jobs
* Notifications
* Reporting
* File management
* Integrations
* Webhooks
* Audit logs
* Validation
* Error handling
* Search
* Filtering
* Export

============================================================
DATABASE
============================================================

Identify likely:

* entities
* relationships
* transactions
* users
* audit records
* documents
* orders
* payments
* reports

Do not invent a database technology unless specified or genuinely
required by the scope.

============================================================
API
============================================================

Analyze:

* authentication
* CRUD
* business operations
* search
* filtering
* pagination
* files
* payments
* notifications
* webhooks
* integrations
* documentation
* rate limiting

============================================================
AUTHENTICATION
============================================================

Determine appropriate complexity.

Basic:

* Registration
* Login
* Logout
* Password reset

Advanced:

* Email verification
* OTP
* Role-based access
* Session management

Complex:

* MFA
* SSO
* OAuth
* Multi-tenancy
* Advanced permissions
* Device management

Do not make authentication complex without justification.

============================================================
INTEGRATIONS
============================================================

For each integration analyze:

* purpose
* authentication
* API
* read/write operations
* synchronization
* webhooks
* retry logic
* errors
* monitoring
* rate limits
* security

Do not invent a provider.

If the provider is unknown, state that the provider is to be confirmed.

Provider charges belong to external_costs.

============================================================
PAYMENTS
============================================================

If required:

* Payment initiation
* Checkout
* Confirmation
* Transaction records
* Status
* Failed payments
* Webhooks
* Refunds if required
* Receipts
* Payment history
* Subscription billing if required

============================================================
NOTIFICATIONS
============================================================

Determine whether the project requires:

* Email
* SMS
* Push
* In-app notifications

External provider costs remain separate.

============================================================
FILES AND DOCUMENTS
============================================================

Analyze:

* Upload
* Download
* Storage
* Permissions
* Preview
* Sharing
* Versioning
* Approval
* Digital signatures
* Audit trails

============================================================
SEARCH
============================================================

Determine:

* Basic search
* Advanced search
* Filtering
* Sorting
* Full-text search
* Multi-entity search

============================================================
REPORTING
============================================================

Determine:

* Reports
* Tables
* Charts
* Analytics
* Filters
* Date ranges
* Export
* PDF
* Automated reports

============================================================
BOOKING
============================================================

If booking exists:

* Availability
* Calendar
* Booking creation
* Details
* Management
* Cancellation
* Rescheduling
* Reminders

============================================================
ECOMMERCE
============================================================

If e-commerce exists:

* Products
* Categories
* Search
* Filters
* Product details
* Cart
* Checkout
* Payments
* Orders
* Inventory
* Discounts
* Shipping
* Notifications

============================================================
MARKETPLACE
============================================================

If marketplace exists analyze separately:

BUYER

* Registration
* Profile
* Browse
* Search
* Product details
* Cart
* Checkout
* Orders
* Reviews

SELLER

* Registration
* Verification
* Dashboard
* Products
* Inventory
* Orders
* Earnings

ADMIN

* Seller management
* Buyer management
* Products
* Orders
* Payments
* Commissions
* Disputes
* Reviews
* Reports

============================================================
MOBILE
============================================================

If mobile is required:

* Android
* iOS
* Shared codebase
* Mobile screens
* Authentication
* API
* Push notifications
* Payments
* Maps
* Camera
* Files
* Offline functionality
* Device capabilities
* Deep links
* Store deployment

============================================================
AI FEATURES
============================================================

If AI is required:

* AI API integration
* Assistant
* Chat
* Conversation history
* RAG
* Knowledge base
* Embeddings
* Vector search
* Tool calling
* AI workflows
* Document processing
* Human approval
* Guardrails

AI provider costs belong to external_costs.

============================================================
AUTOMATION
============================================================

Analyze:

* Trigger
* Conditions
* Actions
* Background jobs
* Scheduling
* Notifications
* Retry
* Logging
* Monitoring

============================================================
SECURITY
============================================================

Security must be proportional.

Analyze:

* Authentication
* Authorization
* Permissions
* Input validation
* Encryption
* Security headers
* Rate limiting
* Audit logs
* Access controls
* Payment security
* Privacy
* Security testing

============================================================
DEVOPS
============================================================

Use appropriate level.

BASIC:

* Server
* Deployment
* Domain
* SSL

STANDARD:

* VPS/cloud
* Docker
* Nginx
* Application server
* Database
* SSL
* Environment configuration
* Monitoring
* Backups where appropriate

ADVANCED:

* CI/CD
* Monitoring
* Logging
* Backups
* Security hardening

ENTERPRISE:

* Kubernetes
* Infrastructure as Code
* High availability
* Load balancing
* Autoscaling
* Disaster recovery

Do not apply enterprise infrastructure to a simple application.

============================================================
TESTING
============================================================

Select appropriate testing:

* Functional
* API
* Authentication
* Payment
* Integration
* Responsive
* Mobile
* Security
* UAT
* Regression

============================================================
TIMELINE
============================================================

Estimate based on:

* Modules
* Screens
* Backend complexity
* Integrations
* Mobile
* Testing
* Security
* Deployment
* Client review

============================================================
MILESTONES
============================================================

Each milestone:

{
    "name": "",
    "description": "",
    "expected_duration": "",
    "deliverables": [],
    "dependencies": []
}

============================================================
PRICING FEATURE SELECTION
============================================================

For every billable capability:

{
    "name": "",
    "feature_key": "",
    "category": "",
    "scope_status": "required",
    "complexity": "medium",
    "quantity": 1,
    "description": ""
}

Allowed scope_status:

required
recommended
optional

Allowed complexity:

low
medium
high

IMPORTANT:

required = INCLUDED in project total

recommended = NOT INCLUDED in project total

optional = NOT INCLUDED in project total

============================================================
PRICING OVERLAP
============================================================

Do not duplicate the same capability.

For example, do not select multiple pricing features that represent
the exact same implementation.

Select the most appropriate recognized feature.

============================================================
EXTERNAL COSTS
============================================================

Return external costs separately.

Example:

{
    "name": "SMS Provider",
    "type": "recurring",
    "frequency": "usage_based",
    "included_in_project_total": false,
    "description": "Client pays provider directly."
}

Do not invent exact provider prices unless explicitly supplied.

============================================================
PRICING CONFIDENCE
============================================================

Use:

high
medium
low

Based on how complete the customer's information is.

============================================================
FINAL JSON
============================================================

Return ONLY valid JSON.

Use:

{
"title": "",

"client_summary": "",

"business_objectives": [],

"confirmed_requirements": [],

"recommended_requirements": [],

"optional_future_features": [],

"assumptions": [],

"users_and_roles": [],

"scope": {
    "project_type": "",
    "platforms": [],
    "modules": [],
    "primary_workflows": [],
    "frontend": {},
    "backend": {},
    "database": {},
    "api": {},
    "integrations": [],
    "security": {},
    "devops": {},
    "testing": {}
},

"pages": [],

"features": [],

"authentication": {},

"integrations": [],

"mobile": {},

"backend": {},

"database": {},

"devops": {},

"security": {},

"technical_scope": {},

"deliverables": [],

"exclusions": [],

"timeline": {},

"milestones": [],

"pricing": {
    "currency": "NGN",

    "required_total": 0,
    "recommended_total": 0,
    "optional_total": 0,
    "subtotal": 0,
    "adjustments": 0,
    "estimated_total": 0,

    "confidence": "medium",

    "pricing_basis": [],

    "recommended_pricing": [],

    "optional_pricing": [],

    "pricing_rationale": "",

    "exchange_rate": {
        "base_currency": "",
        "target_currency": "",
        "rate": 0,
        "source": ""
    }
},

"external_costs": [],

"next_steps": []
}

============================================================
FINAL RULE
============================================================

The monetary fields returned by Gemini are NOT authoritative.

The backend MUST overwrite them.

The only pricing information Gemini is trusted to provide is:

feature_key
scope_status
complexity
quantity

Return ONLY JSON.
"""


# ============================================================
# PRICING CATALOG
# ============================================================

def get_pricing_catalog():
    """
    Give Gemini the approved pricing feature catalog.

    Gemini uses this ONLY to identify valid feature keys.

    It does NOT control the prices.
    """

    catalog = []

    for feature_key in get_all_feature_keys():

        if not feature_exists(feature_key):
            continue

        try:
            price_range = get_price_range(feature_key)
        except Exception:
            price_range = None

        catalog.append({
            "feature_key": feature_key,
            "name": get_feature_name(feature_key),
            "price_range": price_range,
        })

    return catalog


def get_valid_feature_keys():
    return {
        key
        for key in get_all_feature_keys()
        if feature_exists(key)
    }


# ============================================================
# PRICING GUIDANCE
# ============================================================

def get_pricing_guidance():

    amount = os.getenv(
        "PROPOSAL_PRICING_GUIDANCE_AMOUNT",
        "500000",
    )

    currency = os.getenv(
        "PROPOSAL_PRICING_GUIDANCE_CURRENCY",
        "NGN",
    )

    try:
        Decimal(str(amount))
    except (InvalidOperation, ValueError):
        raise ValueError(
            "PROPOSAL_PRICING_GUIDANCE_AMOUNT must be numeric."
        )

    currency = str(currency).strip().upper() or "NGN"

    return str(amount), currency


# ============================================================
# JSON CLEANING
# ============================================================

def clean_json_response(text):

    if not text:
        raise ValueError(
            "Gemini returned an empty response."
        )

    text = text.strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"^```\s*",
        "",
        text,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    return text.strip()


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def ensure_list(value):

    if isinstance(value, list):
        return value

    return []


def ensure_dict(value):

    if isinstance(value, dict):
        return value

    return {}


def normalize_complexity(value):

    value = str(
        value or "medium"
    ).strip().lower()

    aliases = {
        "simple": "low",
        "basic": "low",
        "moderate": "medium",
        "medium": "medium",
        "advanced": "high",
        "complex": "high",
    }

    value = aliases.get(
        value,
        value,
    )

    if value not in {
        "low",
        "medium",
        "high",
    }:
        return "medium"

    return value


def normalize_scope_status(value):

    value = str(
        value or "required"
    ).strip().lower()

    aliases = {
        "confirmed": "required",
        "required": "required",
        "included": "required",
        "recommended": "recommended",
        "optional": "optional",
        "future": "optional",
    }

    return aliases.get(
        value,
        "required",
    )


# ============================================================
# VALIDATE PRICING FEATURES
# ============================================================

def validate_pricing_features(data):

    valid_keys = get_valid_feature_keys()

    pricing = ensure_dict(
        data.get("pricing", {})
    )

    sections = [
        ("pricing_basis", "required"),
        ("recommended_pricing", "recommended"),
        ("optional_pricing", "optional"),
    ]

    for section, forced_status in sections:

        validated = []

        for item in ensure_list(
            pricing.get(section, [])
        ):

            if not isinstance(item, dict):
                continue

            feature_key = str(
                item.get(
                    "feature_key",
                    "",
                )
            ).strip()

            if not feature_key:
                continue

            # ------------------------------------------------
            # HARD SECURITY BOUNDARY
            # ------------------------------------------------

            if feature_key not in valid_keys:
                raise ValueError(
                    f"Gemini returned unknown pricing feature_key: "
                    f"{feature_key}"
                )

            quantity = item.get(
                "quantity",
                1,
            )

            try:
                quantity = int(quantity)
            except (
                TypeError,
                ValueError,
            ):
                quantity = 1

            quantity = max(
                1,
                quantity,
            )

            validated.append({
                "name": get_feature_name(
                    feature_key
                ),

                "feature_key": feature_key,

                "category": str(
                    item.get(
                        "category",
                        "",
                    )
                ),

                "scope_status": forced_status,

                "complexity": normalize_complexity(
                    item.get(
                        "complexity",
                        "medium",
                    )
                ),

                "quantity": quantity,

                "description": str(
                    item.get(
                        "description",
                        "",
                    )
                ),
            })

        pricing[section] = validated

    data["pricing"] = pricing

    return data


# ============================================================
# NORMALIZE PRICING
# ============================================================

def normalize_pricing_structure(pricing):

    pricing = ensure_dict(pricing)

    pricing["currency"] = str(
        pricing.get(
            "currency",
            "NGN",
        )
    ).upper()

    pricing["confidence"] = str(
        pricing.get(
            "confidence",
            "medium",
        )
    ).lower()

    if pricing["confidence"] not in {
        "low",
        "medium",
        "high",
    }:
        pricing["confidence"] = "medium"

    # --------------------------------------------------------
    # NEVER TRUST AI MONETARY VALUES
    # --------------------------------------------------------

    pricing["required_total"] = 0
    pricing["recommended_total"] = 0
    pricing["optional_total"] = 0
    pricing["subtotal"] = 0
    pricing["adjustments"] = 0
    pricing["estimated_total"] = 0

    pricing["pricing_basis"] = ensure_list(
        pricing.get(
            "pricing_basis",
            [],
        )
    )

    pricing["recommended_pricing"] = ensure_list(
        pricing.get(
            "recommended_pricing",
            [],
        )
    )

    pricing["optional_pricing"] = ensure_list(
        pricing.get(
            "optional_pricing",
            [],
        )
    )

    pricing["exchange_rate"] = ensure_dict(
        pricing.get(
            "exchange_rate",
            {},
        )
    )

    pricing["pricing_rationale"] = str(
        pricing.get(
            "pricing_rationale",
            "",
        )
    )

    return pricing


# ============================================================
# NORMALIZE ANALYSIS
# ============================================================

def normalize_analysis(data):

    if not isinstance(data, dict):
        raise ValueError(
            "Proposal AI response must be a JSON object."
        )

    data.setdefault(
        "title",
        "AB Technologies Project Proposal",
    )

    data.setdefault(
        "client_summary",
        "",
    )

    list_fields = [
        "business_objectives",
        "confirmed_requirements",
        "recommended_requirements",
        "optional_future_features",
        "assumptions",
        "pages",
        "features",
        "integrations",
        "deliverables",
        "exclusions",
        "milestones",
        "next_steps",
        "users_and_roles",
        "external_costs",
    ]

    for field in list_fields:
        data[field] = ensure_list(
            data.get(field, [])
        )

    dict_fields = [
        "scope",
        "authentication",
        "mobile",
        "backend",
        "database",
        "devops",
        "security",
        "technical_scope",
        "timeline",
        "pricing",
    ]

    for field in dict_fields:
        data[field] = ensure_dict(
            data.get(field, {})
        )

    # ========================================================
    # AUTHENTICATION
    # ========================================================

    auth = data["authentication"]

    auth.setdefault(
        "required",
        False,
    )

    auth.setdefault(
        "level",
        "none",
    )

    auth["methods"] = ensure_list(
        auth.get("methods", [])
    )

    auth["users"] = ensure_list(
        auth.get("users", [])
    )

    auth["roles"] = ensure_list(
        auth.get("roles", [])
    )

    auth["permissions"] = ensure_list(
        auth.get("permissions", [])
    )

    # ========================================================
    # MOBILE
    # ========================================================

    mobile = data["mobile"]

    mobile.setdefault(
        "required",
        False,
    )

    mobile["platforms"] = ensure_list(
        mobile.get("platforms", [])
    )

    mobile["screens"] = ensure_list(
        mobile.get("screens", [])
    )

    mobile["features"] = ensure_list(
        mobile.get("features", [])
    )

    mobile["integrations"] = ensure_list(
        mobile.get("integrations", [])
    )

    mobile["authentication"] = ensure_dict(
        mobile.get("authentication", {})
    )

    mobile["authentication"].setdefault(
        "required",
        False,
    )

    mobile["authentication"].setdefault(
        "level",
        "none",
    )

    # ========================================================
    # BACKEND
    # ========================================================

    backend = data["backend"]

    backend.setdefault(
        "required",
        False,
    )

    backend["components"] = ensure_list(
        backend.get("components", [])
    )

    backend["api"] = ensure_list(
        backend.get("api", [])
    )

    backend["database"] = ensure_list(
        backend.get("database", [])
    )

    backend["services"] = ensure_list(
        backend.get("services", [])
    )

    # ========================================================
    # DATABASE
    # ========================================================

    database = data["database"]

    database.setdefault(
        "level",
        "basic",
    )

    database["entities"] = ensure_list(
        database.get("entities", [])
    )

    database["relationships"] = ensure_list(
        database.get("relationships", [])
    )

    database["transactions"] = ensure_list(
        database.get("transactions", [])
    )

    # ========================================================
    # DEVOPS
    # ========================================================

    devops = data["devops"]

    devops.setdefault(
        "required",
        False,
    )

    devops.setdefault(
        "level",
        "none",
    )

    devops["components"] = ensure_list(
        devops.get("components", [])
    )

    devops["environments"] = ensure_list(
        devops.get("environments", [])
    )

    # ========================================================
    # SECURITY
    # ========================================================

    security = data["security"]

    security.setdefault(
        "level",
        "basic",
    )

    security["requirements"] = ensure_list(
        security.get("requirements", [])
    )

    security["controls"] = ensure_list(
        security.get("controls", [])
    )

    security["risks"] = ensure_list(
        security.get("risks", [])
    )

    # ========================================================
    # TIMELINE
    # ========================================================

    timeline = data["timeline"]

    timeline.setdefault(
        "estimated_duration",
        "",
    )

    timeline.setdefault(
        "basis",
        "",
    )

    timeline["phases"] = ensure_list(
        timeline.get("phases", [])
    )

    # ========================================================
    # PRICING
    # ========================================================

    data["pricing"] = normalize_pricing_structure(
        data["pricing"]
    )

    # ========================================================
    # MILESTONES
    # ========================================================

    normalized_milestones = []

    for milestone in data["milestones"]:

        if not isinstance(
            milestone,
            dict,
        ):
            continue

        normalized_milestones.append({
            "name": str(
                milestone.get(
                    "name",
                    "Project Milestone",
                )
            ),

            "description": str(
                milestone.get(
                    "description",
                    "",
                )
            ),

            "expected_duration": str(
                milestone.get(
                    "expected_duration",
                    "",
                )
            ),

            "deliverables": ensure_list(
                milestone.get(
                    "deliverables",
                    [],
                )
            ),

            "dependencies": ensure_list(
                milestone.get(
                    "dependencies",
                    [],
                )
            ),
        })

    data["milestones"] = normalized_milestones

    return data


# ============================================================
# BACKEND PRICING ENGINE
# ============================================================

def calculate_backend_pricing(
    analysis,
    *,
    currency="NGN",
):

    analysis = normalize_analysis(
        analysis
    )

    analysis = validate_pricing_features(
        analysis
    )

    pricing = normalize_pricing_structure(
        analysis["pricing"]
    )

    required_items = []
    recommended_items = []
    optional_items = []

    sections = [
        (
            "pricing_basis",
            required_items,
            "required",
        ),
        (
            "recommended_pricing",
            recommended_items,
            "recommended",
        ),
        (
            "optional_pricing",
            optional_items,
            "optional",
        ),
    ]

    # --------------------------------------------------------
    # Prevent duplicate feature billing.
    # --------------------------------------------------------

    seen_required = set()
    seen_recommended = set()
    seen_optional = set()

    for section, target, status in sections:

        if status == "required":
            seen = seen_required
        elif status == "recommended":
            seen = seen_recommended
        else:
            seen = seen_optional

        for item in pricing.get(
            section,
            [],
        ):

            feature_key = str(
                item.get(
                    "feature_key",
                    "",
                )
            ).strip()

            if not feature_key:
                continue

            if feature_key in seen:
                continue

            seen.add(feature_key)

            if not feature_exists(
                feature_key
            ):
                raise ValueError(
                    f"Unknown pricing feature: {feature_key}"
                )

            complexity = normalize_complexity(
                item.get(
                    "complexity",
                    "medium",
                )
            )

            quantity = item.get(
                "quantity",
                1,
            )

            try:
                quantity = int(quantity)
            except (
                TypeError,
                ValueError,
            ):
                quantity = 1

            quantity = max(
                1,
                quantity,
            )

            # =================================================
            # PYTHON CALCULATES THE PRICE
            # =================================================

            unit_price = Decimal(
                str(
                    calculate_price(
                        feature_key,
                        complexity=complexity,
                    )
                )
            )

            total = (
                unit_price
                * Decimal(quantity)
            )

            target.append({
                "name": get_feature_name(
                    feature_key
                ),

                "feature_key": feature_key,

                "category": str(
                    item.get(
                        "category",
                        "",
                    )
                ),

                "scope_status": status,

                "complexity": complexity,

                "quantity": quantity,

                "unit": "project",

                "unit_price": str(
                    unit_price
                ),

                "total": str(
                    total
                ),

                "included_in_project_total": (
                    status == "required"
                ),

                "description": str(
                    item.get(
                        "description",
                        "",
                    )
                ),
            })

    required_total = sum(
        (
            Decimal(item["total"])
            for item in required_items
        ),
        Decimal("0"),
    )

    recommended_total = sum(
        (
            Decimal(item["total"])
            for item in recommended_items
        ),
        Decimal("0"),
    )

    optional_total = sum(
        (
            Decimal(item["total"])
            for item in optional_items
        ),
        Decimal("0"),
    )

    # ========================================================
    # ONLY REQUIRED FEATURES ENTER THE PROJECT TOTAL
    # ========================================================

    subtotal = required_total

    adjustments = Decimal("0")

    estimated_total = (
        required_total
        + adjustments
    )

    final_currency = str(
        currency
        or pricing.get(
            "currency",
            "NGN",
        )
    ).strip().upper()

    pricing["currency"] = final_currency

    pricing["required_total"] = float(
        required_total
    )

    pricing["recommended_total"] = float(
        recommended_total
    )

    pricing["optional_total"] = float(
        optional_total
    )

    pricing["subtotal"] = float(
        subtotal
    )

    pricing["adjustments"] = float(
        adjustments
    )

    pricing["estimated_total"] = float(
        estimated_total
    )

    pricing["pricing_basis"] = required_items

    pricing["recommended_pricing"] = (
        recommended_items
    )

    pricing["optional_pricing"] = (
        optional_items
    )

    analysis["pricing"] = pricing

    # ========================================================
    # ADD PRICING INFORMATION TO FEATURES
    # ========================================================

    price_lookup = {}

    for item in (
        required_items
        + recommended_items
        + optional_items
    ):
        price_lookup[
            item["feature_key"]
        ] = item

    normalized_features = []

    for feature in analysis.get(
        "features",
        [],
    ):

        if not isinstance(
            feature,
            dict,
        ):
            normalized_features.append(
                feature
            )
            continue

        feature_key = str(
            feature.get(
                "feature_key",
                "",
            )
        ).strip()

        if feature_key in price_lookup:

            pricing_item = price_lookup[
                feature_key
            ]

            feature[
                "pricing_status"
            ] = pricing_item[
                "scope_status"
            ]

            feature[
                "included_in_project_total"
            ] = pricing_item[
                "scope_status"
            ] == "required"

            feature[
                "complexity"
            ] = pricing_item[
                "complexity"
            ]

            feature[
                "quantity"
            ] = pricing_item[
                "quantity"
            ]

            feature[
                "unit_price"
            ] = pricing_item[
                "unit_price"
            ]

            feature[
                "calculated_total"
            ] = pricing_item[
                "total"
            ]

        normalized_features.append(
            feature
        )

    analysis["features"] = (
        normalized_features
    )

    return analysis


# ============================================================
# BUILD REQUEST CONTEXT
# ============================================================

def build_request_context(
    lead,
    project_request=None,
    quote_request=None,
):
    guidance_amount, guidance_currency = get_pricing_guidance()

    # ============================================================
    # BASE CONTEXT
    # ============================================================

    context = {
        "client": {
            "name": getattr(
                lead,
                "name",
                "",
            ),
            "company": getattr(
                lead,
                "company",
                "",
            ),
            "email": getattr(
                lead,
                "email",
                "",
            ),
            "phone": getattr(
                lead,
                "phone",
                "",
            ),
            "country": getattr(
                lead,
                "country",
                "",
            ),
            "country_code": getattr(
                lead,
                "country_code",
                "",
            ),
            "preferred_currency": getattr(
                lead,
                "preferred_currency",
                "",
            ),
        },

        "request": {},

        "pricing_guidance": {
            "amount": guidance_amount,
            "currency": guidance_currency,
            "instruction": (
                "Commercial benchmark only. "
                "Never use this as the final price."
            ),
        },

        "pricing_catalog": get_pricing_catalog(),

        "pricing_catalog_instruction": (
            "Only use exact feature_key values "
            "from this catalog. "
            "The catalog is supplied for feature recognition. "
            "Python calculates all prices."
        ),
    }

    # ============================================================
    # PROJECT REQUEST
    # ============================================================

    if project_request:

        context["request"] = {
            "type": "project",

            "id": str(
                project_request.id
            ),

            "title": getattr(
                project_request,
                "title",
                "",
            ),

            "description": getattr(
                project_request,
                "description",
                "",
            ),

            "project_type": getattr(
                project_request,
                "project_type",
                "",
            ),

            "budget": (
                str(
                    project_request.budget
                )
                if getattr(
                    project_request,
                    "budget",
                    None,
                ) is not None
                else None
            ),

            "currency": getattr(
                project_request,
                "currency",
                "",
            ),

            "deadline": (
                str(
                    project_request.deadline
                )
                if getattr(
                    project_request,
                    "deadline",
                    None,
                )
                else None
            ),

            "status": getattr(
                project_request,
                "status",
                "",
            ),

            "notes": getattr(
                project_request,
                "notes",
                "",
            ),
        }

    # ============================================================
    # QUOTE REQUEST
    # ============================================================

    elif quote_request:

        context["request"] = {
            "type": "quote",

            "id": str(
                quote_request.id
            ),

            "title": getattr(
                quote_request,
                "title",
                "",
            ),

            "description": getattr(
                quote_request,
                "description",
                "",
            ),

            "category": getattr(
                quote_request,
                "category",
                "",
            ),

            "quantity": getattr(
                quote_request,
                "quantity",
                None,
            ),

            "budget": (
                str(
                    quote_request.budget
                )
                if getattr(
                    quote_request,
                    "budget",
                    None,
                ) is not None
                else None
            ),

            "currency": getattr(
                quote_request,
                "currency",
                "",
            ),

            "deadline": (
                str(
                    quote_request.deadline
                )
                if getattr(
                    quote_request,
                    "deadline",
                    None,
                )
                else None
            ),

            "status": getattr(
                quote_request,
                "status",
                "",
            ),

            "notes": getattr(
                quote_request,
                "notes",
                "",
            ),
        }

    # ============================================================
    # FINAL CONTEXT VALIDATION
    # ============================================================

    request = context.get("request", {})

    if not request:
        raise ValueError(
            "Cannot generate proposal: no project request or quote request "
            "was supplied to the proposal engine."
        )

    # Do not allow an apparently valid request object with no actual
    # meaningful request content to silently reach Gemini.

    request_content = " ".join(
        str(
            request.get(field, "")
        ).strip()
        for field in (
            "title",
            "description",
            "project_type",
            "category",
            "notes",
        )
    ).strip()

    if not request_content:
        raise ValueError(
            "Cannot generate proposal: the client request contains "
            "no meaningful title, description, project type, category, "
            "or notes."
        )

    return context

# ============================================================
# GEMINI CLIENT
# ============================================================

def get_gemini_client():

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    return genai.Client(
        api_key=api_key
    )


# ============================================================
# ANALYZE REQUEST
# ============================================================

def analyze_request(context):

    client = get_gemini_client()

    prompt = (
        PROPOSAL_SYSTEM_PROMPT
        + "\n\n"
        + "CLIENT / CRM REQUEST:\n"
        + json.dumps(
            context,
            indent=2,
            ensure_ascii=False,
        )
    )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    text = clean_json_response(
        getattr(
            response,
            "text",
            "",
        )
    )

    try:
        data = json.loads(
            text
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Proposal AI returned invalid JSON."
        ) from exc

    data = normalize_analysis(
        data
    )

    data = validate_pricing_features(
        data
    )

    # ========================================================
    # IMPORTANT
    #
    # AI monetary values are destroyed here.
    # ========================================================

    data = calculate_backend_pricing(
        data,
        currency=(
            context.get(
                "request",
                {},
            ).get(
                "currency"
            )
            or context.get(
                "client",
                {},
            ).get(
                "preferred_currency"
            )
            or "NGN"
        ),
    )

    return data


# ============================================================
# BUILD PROPOSAL DATA
# ============================================================

def build_proposal_data(
    analysis,
    *,
    country="",
    currency="NGN",
):

    analysis = normalize_analysis(
        analysis
    )

    analysis = validate_pricing_features(
        analysis
    )

    analysis = calculate_backend_pricing(
        analysis,
        currency=currency,
    )

    pricing = analysis[
        "pricing"
    ]

    estimated_total = Decimal(
        str(
            pricing.get(
                "estimated_total",
                0,
            )
        )
    )

    final_currency = str(
        currency
        or "NGN"
    ).strip().upper()

    guidance_amount, guidance_currency = (
        get_pricing_guidance()
    )

    pricing_snapshot = {

        "source": "backend_pricing_catalog",

        "catalog_version": "current",

        "currency": final_currency,

        "required_total": str(
            pricing[
                "required_total"
            ]
        ),

        "recommended_total": str(
            pricing[
                "recommended_total"
            ]
        ),

        "optional_total": str(
            pricing[
                "optional_total"
            ]
        ),

        "subtotal": str(
            pricing[
                "subtotal"
            ]
        ),

        "adjustments": str(
            pricing[
                "adjustments"
            ]
        ),

        "estimated_total": str(
            estimated_total
        ),

        "pricing_guidance_amount": (
            guidance_amount
        ),

        "pricing_guidance_currency": (
            guidance_currency
        ),

        "confidence": pricing.get(
            "confidence",
            "medium",
        ),

        "pricing_rationale": pricing.get(
            "pricing_rationale",
            "",
        ),

        "pricing_basis": pricing.get(
            "pricing_basis",
            [],
        ),

        "recommended_pricing": pricing.get(
            "recommended_pricing",
            [],
        ),

        "optional_pricing": pricing.get(
            "optional_pricing",
            [],
        ),
    }

    return {

        "title": analysis.get(
            "title",
            "AB Technologies Project Proposal",
        ),

        "client_summary": analysis.get(
            "client_summary",
            "",
        ),

        "scope": analysis.get(
            "scope",
            {},
        ),

        "pages": analysis.get(
            "pages",
            [],
        ),

        "features": analysis.get(
            "features",
            [],
        ),

        "authentication": analysis.get(
            "authentication",
            {},
        ),

        "integrations": analysis.get(
            "integrations",
            [],
        ),

        "mobile": analysis.get(
            "mobile",
            {},
        ),

        "backend": analysis.get(
            "backend",
            {},
        ),

        "devops": analysis.get(
            "devops",
            {},
        ),

        "technical_scope": analysis.get(
            "technical_scope",
            {},
        ),

        "deliverables": analysis.get(
            "deliverables",
            [],
        ),

        "assumptions": analysis.get(
            "assumptions",
            [],
        ),

        "exclusions": analysis.get(
            "exclusions",
            [],
        ),

        "timeline": analysis.get(
            "timeline",
            {},
        ),

        "milestones": analysis.get(
            "milestones",
            [],
        ),

        "country": country,

        "currency": final_currency,

        "total_price": estimated_total,

        "pricing_snapshot": pricing_snapshot,

        "ai_analysis": analysis,
    }


# ============================================================
# GENERATE COMPLETE PROPOSAL
# ============================================================

def generate_proposal_data(
    lead,
    project_request=None,
    quote_request=None,
):

    context = build_request_context(
        lead=lead,
        project_request=project_request,
        quote_request=quote_request,
    )

    analysis = analyze_request(
        context
    )

    country = (
        getattr(
            lead,
            "country",
            "",
        )
        or ""
    )

    currency = (
        getattr(
            lead,
            "preferred_currency",
            "",
        )
        or ""
    )

    if not currency:

        if project_request:

            currency = (
                getattr(
                    project_request,
                    "currency",
                    "",
                )
                or "NGN"
            )

        elif quote_request:

            currency = (
                getattr(
                    quote_request,
                    "currency",
                    "",
                )
                or "NGN"
            )

        else:

            _, currency = (
                get_pricing_guidance()
            )

    currency = str(
        currency
    ).upper()

    proposal = create_proposal_from_analysis(
    lead=lead,
    analysis=analysis,
    source=(
        "project_request"
        if project_request
        else "quote_request"
        if quote_request
        else "manual"
    ),
    project_request=project_request,
    quote_request=quote_request,
    country=country,
    currency=currency,
)

    return proposal


# ============================================================
# REVISION CONTEXT
# ============================================================

def build_revision_context(
    proposal,
    change_request,
):

    guidance_amount, guidance_currency = (
        get_pricing_guidance()
    )

    return {

        "existing_proposal": {

            "id": str(
                proposal.id
            ),

            "version": proposal.version,

            "title": proposal.title,

            "client_summary": (
                proposal.client_summary
            ),

            "scope": proposal.scope,

            "pages": proposal.pages,

            "features": proposal.features,

            "authentication": (
                proposal.authentication
            ),

            "integrations": (
                proposal.integrations
            ),

            "mobile": proposal.mobile,

            "backend": proposal.backend,

            "devops": proposal.devops,

            "technical_scope": (
                proposal.technical_scope
            ),

            "deliverables": (
                proposal.deliverables
            ),

            "assumptions": (
                proposal.assumptions
            ),

            "exclusions": (
                proposal.exclusions
            ),

            "timeline": proposal.timeline,

            "milestones": proposal.milestones,

            "country": proposal.country,

            "currency": proposal.currency,

            "current_price": str(
                proposal.total_price
            ),

            "pricing_snapshot": (
                proposal.pricing_snapshot
            ),
        },

        "pricing_guidance": {

            "amount": guidance_amount,

            "currency": guidance_currency,

            "instruction": (
                "Benchmark only. "
                "Never use this as final pricing."
            ),
        },

        "pricing_catalog": (
            get_pricing_catalog()
        ),

        "pricing_catalog_instruction": (
            "Only use recognized feature_key values. "
            "Do not invent prices. "
            "Python calculates pricing."
        ),

        "requested_change": (
            change_request
        ),
    }


# ============================================================
# REVISE PROPOSAL
# ============================================================

import json
import time
def revise_proposal(
    proposal,
    change_request,
):

    context = build_revision_context(
        proposal,
        change_request,
    )

    revision_prompt = """
You are revising an existing AB Technologies software proposal.

Produce a COMPLETE revised proposal.

Do not return only the changes.

============================================================
REVISION PROCESS
============================================================

1. Read the existing proposal.

2. Read the client's requested change.

3. Preserve everything that remains valid.

4. Add explicitly requested functionality.

5. Remove explicitly requested functionality.

6. Modify affected functionality.

7. Re-evaluate modules.

8. Re-evaluate pages/screens.

9. Re-evaluate workflows.

10. Re-evaluate authentication.

11. Re-evaluate roles and permissions.

12. Re-evaluate backend.

13. Re-evaluate database.

14. Re-evaluate APIs.

15. Re-evaluate integrations.

16. Re-evaluate payments.

17. Re-evaluate notifications.

18. Re-evaluate mobile.

19. Re-evaluate security.

20. Re-evaluate DevOps.

21. Re-evaluate testing.

22. Re-evaluate deliverables.

23. Re-evaluate exclusions.

24. Re-evaluate timeline.

25. Re-evaluate milestones.

26. Re-evaluate pricing feature selections.

============================================================
PRICING REVISION
============================================================

DO NOT:

* Add money to the old price.
* Subtract money from the old price.
* Invent a price.
* Preserve an obsolete total.

Instead determine the COMPLETE final set of:

* required pricing features
* recommended pricing features
* optional pricing features

For every pricing feature provide:

feature_key
scope_status
complexity
quantity
description

The backend will calculate the new price.

============================================================
INCLUDED / NOT INCLUDED
============================================================

required:

Included in project total.

recommended:

NOT included in project total.

optional:

NOT included in project total.

external costs:

NOT included in project total.

============================================================
FEATURE KEY
============================================================

Use ONLY feature keys supplied by the pricing catalog.

Never invent a feature key.

============================================================
REMOVAL
============================================================

If the client says:

"Remove payments"

remove payment functionality from:

* pages
* features
* workflows
* backend
* API
* integrations
* pricing selections

If the client says:

"Remove mobile"

remove mobile-specific scope and mobile pricing.

============================================================
ADDITION
============================================================

If the client says:

"Add mobile"

re-evaluate:

* mobile platform
* screens
* authentication
* API
* push notifications if relevant
* device functionality
* deployment

Then select the appropriate recognized pricing feature.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Return the complete proposal using the required structure.

Do not include markdown.

Do not include arbitrary prices.
"""

    client = get_gemini_client()

    prompt = (
        PROPOSAL_SYSTEM_PROMPT
        + "\n\n"
        + revision_prompt
        + "\n\n"
        + "EXISTING PROPOSAL AND REQUESTED CHANGE:\n"
        + json.dumps(
            context,
            indent=2,
            ensure_ascii=False,
        )
    )

    # ========================================================
    # GEMINI GENERATION WITH RETRY
    # ========================================================

    MAX_RETRIES = 3

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            # Gemini succeeded
            break

        except Exception as exc:
            error_text = str(exc)

            is_temporary = (
                "503" in error_text
                or "UNAVAILABLE" in error_text
                or "high demand" in error_text.lower()
            )

            if not is_temporary or attempt == MAX_RETRIES - 1:
                raise

            # Retry after 1 second, then 2 seconds
            time.sleep(2 ** attempt)

    text = clean_json_response(
        getattr(
            response,
            "text",
            ""
        )
    )

    try:

        analysis = json.loads(
            text
        )

    except json.JSONDecodeError as exc:

        raise ValueError(
            "Proposal AI returned invalid revision JSON."
        ) from exc

    analysis = normalize_analysis(
        analysis
    )

    analysis = validate_pricing_features(
        analysis
    )

    # ========================================================
    # BACKEND OWNS THE REVISED PRICE
    # ========================================================

    analysis = calculate_backend_pricing(
        analysis,
        currency=(
            proposal.currency
            or "NGN"
        ),
    )

    return analysis