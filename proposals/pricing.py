from decimal import Decimal

from .models import PricingRule



# proposals/pricing.py

"""
AB Technologies Software Pricing Catalog

This file is the source of truth for:
- Recognized software/application features
- Development pricing ranges
- Application foundations
- Complexity-based pricing

IMPORTANT:
External provider/API subscription costs are NOT included here.
For example:
- Stripe's own fees
- Twilio/SMS charges
- SendGrid/Brevo charges
- OpenAI/Gemini API charges
- AWS/Cloud hosting charges

Those are recurring/external costs and should be stored separately
from AB Technologies development pricing.
"""

from decimal import Decimal
from typing import Any


# ============================================================
# APPLICATION FOUNDATIONS
# ============================================================

PRICING_CATALOG = {

    # --------------------------------------------------------
    # APPLICATION FOUNDATIONS
    # --------------------------------------------------------

    "static_website": {
        "name": "Static Website",
        "category": "application_foundation",
        "min": 150000,
        "max": 400000,
    },

    "static_web_application": {
        "name": "Web Application",
        "category": "application_foundation",
        "min": 250000,
        "max": 500000,
    },

    "web_application": {
        "name": "Web Application",
        "category": "application_foundation",
        "min": 250000,
        "max": 500000,
    },

    

    "mobile_application": {
        "name": "Mobile Application",
        "category": "application_foundation",
        "min": 200000,
        "max": 700000,
    },

    

    "saas_application": {
        "name": "SaaS Application",
        "category": "application_foundation",
        "min": 750000,
        "max": 2500000,
    },


    # ========================================================
    # CORE APPLICATION
    # ========================================================

    "authentication": {
        "name": "Authentication",
        "category": "core",
        "min": 30000,
        "max": 120000,
    },

    "authorization": {
        "name": "Authorization",
        "category": "core",
        "min": 20000,
        "max": 70000,
    },

    "user_management": {
        "name": "User Management",
        "category": "core",
        "min": 30000,
        "max": 70000,
    },

    "role_permission_management": {
        "name": "Role & Permission Management",
        "category": "core",
        "min": 30000,
        "max": 100000,
    },

    "user_profiles": {
        "name": "User Profiles",
        "category": "core",
        "min": 10000,
        "max": 50000,
    },

    "organization_management": {
        "name": "Organization Management",
        "category": "core",
        "min": 25000,
        "max": 150000,
    },

    "multi_tenancy": {
        "name": "Multi-Tenancy",
        "category": "core",
        "min": 100000,
        "max": 300000,
    },

    "dashboard": {
        "name": "Dashboard",
        "category": "core",
        "min": 50000,
        "max": 100000,
    },

    "admin_dashboard": {
        "name": "Admin Dashboard",
        "category": "core",
        "min": 75000,
        "max": 200000,
    },


    # ========================================================
    # API / BACKEND / DATABASE
    # ========================================================

    "api_development": {
        "name": "API Development",
        "category": "backend",
        "min": 100000,
        "max": 300000,
    },

    "api_integration": {
        "name": "API Integration",
        "category": "backend",
        "min": 30000,
        "max": 100000,
    },

    "backend_development": {
        "name": "Backend Development",
        "category": "backend",
        "min": 50000,
        "max": 150000,
    },

    "database_development": {
        "name": "Database Development",
        "category": "backend",
        "min": 50000,
        "max": 150000,
    },

    "database_integration": {
        "name": "Database Integration",
        "category": "backend",
        "min": 20000,
        "max": 100000,
    },

    "database_migration": {
        "name": "Database Migration",
        "category": "backend",
        "min": 100000,
        "max": 300000,
    },

    "webhooks": {
        "name": "Webhooks",
        "category": "backend",
        "min": 20000,
        "max": 100000,
    },

    "api_authentication": {
        "name": "API Authentication",
        "category": "backend",
        "min": 20000,
        "max": 100000,
    },

    "api_rate_limiting": {
        "name": "API Rate Limiting",
        "category": "backend",
        "min": 10000,
        "max": 50000,
    },

    "api_documentation": {
        "name": "API Documentation",
        "category": "backend",
        "min": 30000,
        "max": 100000,
    },

    "microservices": {
        "name": "Microservices",
        "category": "architecture",
        "min": 250000,
        "max": 1000000,
    },


    # ========================================================
    # DATA
    # ========================================================

    "search": {
        "name": "Search",
        "category": "data",
        "min": 10000,
        "max": 50000,
    },

    "advanced_search": {
        "name": "Advanced Search",
        "category": "data",
        "min": 10000,
        "max": 100000,
    },

    "filtering": {
        "name": "Filtering",
        "category": "data",
        "min": 20000,
        "max": 70000,
    },

    "data_import": {
        "name": "Data Import",
        "category": "data",
        "min": 20000,
        "max": 100000,
    },

    "data_export": {
        "name": "Data Export",
        "category": "data",
        "min": 10000,
        "max": 70000,
    },

    "data_synchronization": {
        "name": "Data Synchronization",
        "category": "data",
        "min": 50000,
        "max": 200000,
    },

    "data_visualization": {
        "name": "Data Visualization",
        "category": "data",
        "min": 10000,
        "max": 100000,
    },

    "advanced_analytics": {
        "name": "Advanced Analytics",
        "category": "data",
        "min": 50000,
        "max": 200000,
    },

    "reporting": {
        "name": "Reporting",
        "category": "data",
        "min": 20000,
        "max": 100000,
    },

    "custom_reporting": {
        "name": "Custom Reporting",
        "category": "data",
        "min": 50000,
        "max": 200000,
    },


    # ========================================================
    # COMMUNICATION
    # ========================================================

    "notifications": {
        "name": "Notifications",
        "category": "communication",
        "min": 30000,
        "max": 80000,
    },

    "email_integration": {
        "name": "Email Integration",
        "category": "communication",
        "min": 20000,
        "max": 80000,
    },

    "sms_integration": {
        "name": "SMS Integration",
        "category": "communication",
        "min": 20000,
        "max": 80000,
    },

    "push_notifications": {
        "name": "Push Notifications",
        "category": "communication",
        "min": 20000,
        "max": 100000,
    },

    "in_app_notifications": {
        "name": "In-App Notifications",
        "category": "communication",
        "min": 10000,
        "max": 80000,
    },

    "chat_messaging": {
        "name": "Chat & Messaging",
        "category": "communication",
        "min": 50000,
        "max": 200000,
    },

    "real_time_features": {
        "name": "Real-Time Features",
        "category": "communication",
        "min": 50000,
        "max": 250000,
    },

    "websockets": {
        "name": "WebSockets",
        "category": "communication",
        "min": 50000,
        "max": 150000,
    },

    "video_audio_calling": {
        "name": "Video & Audio Calling",
        "category": "communication",
        "min": 50000,
        "max": 350000,
    },


    # ========================================================
    # PAYMENTS / FINANCE
    # ========================================================

    "payment_integration": {
        "name": "Payment Integration",
        "category": "payments",
        "min": 50000,
        "max": 100000,
    },

    "payment_processing": {
        "name": "Payment Processing",
        "category": "payments",
        "min": 50000,
        "max": 100000,
    },

    "subscription_management": {
        "name": "Subscription Management",
        "category": "payments",
        "min": 50000,
        "max": 100000,
    },

    "billing": {
        "name": "Billing",
        "category": "payments",
        "min": 50000,
        "max": 100000,
    },

    "invoicing": {
        "name": "Invoicing",
        "category": "payments",
        "min": 20000,
        "max": 100000,
    },

    "payment_tracking": {
        "name": "Payment Tracking",
        "category": "payments",
        "min": 10000,
        "max": 50000,
    },

    "wallet_management": {
        "name": "Wallet Management",
        "category": "payments",
        "min": 30000,
        "max": 200000,
    },

    "multi_currency": {
        "name": "Multi-Currency",
        "category": "payments",
        "min": 20000,
        "max": 100000,
    },

    "tax_calculation": {
        "name": "Tax Calculation",
        "category": "payments",
        "min": 10000,
        "max": 100000,
    },

    "discount_promo_system": {
        "name": "Discount & Promo System",
        "category": "payments",
        "min": 10000,
        "max": 100000,
    },


    # ========================================================
    # FILES / DOCUMENTS
    # ========================================================

    "file_upload": {
        "name": "File Upload",
        "category": "files",
        "min": 10000,
        "max": 80000,
    },

    "file_management": {
        "name": "File Management",
        "category": "files",
        "min": 20000,
        "max": 100000,
    },

    "document_management": {
        "name": "Document Management",
        "category": "files",
        "min": 25000,
        "max": 150000,
    },

    "file_versioning": {
        "name": "File Versioning",
        "category": "files",
        "min": 20000,
        "max": 100000,
    },

    "document_approval": {
        "name": "Document Approval",
        "category": "files",
        "min": 20000,
        "max": 100000,
    },

    "digital_signature": {
        "name": "Digital Signature",
        "category": "files",
        "min": 25000,
        "max": 150000,
    },

    "document_generation": {
        "name": "Document Generation",
        "category": "files",
        "min": 20000,
        "max": 100000,
    },

    "pdf_generation": {
        "name": "PDF Generation",
        "category": "files",
        "min": 20000,
        "max": 80000,
    },

    "excel_csv_processing": {
        "name": "Excel / CSV Processing",
        "category": "files",
        "min": 20000,
        "max": 100000,
    },


    # ========================================================
    # BUSINESS OPERATIONS
    # ========================================================

    "customer_management": {
        "name": "Customer Management",
        "category": "business_operations",
        "min": 20000,
        "max": 100000,
    },

    "crm": {
        "name": "CRM",
        "category": "business_operations",
        "min": 100000,
        "max": 300000,
    },

    "lead_management": {
        "name": "Lead Management",
        "category": "business_operations",
        "min": 25000,
        "max": 150000,
    },

    "vendor_management": {
        "name": "Vendor Management",
        "category": "business_operations",
        "min": 20000,
        "max": 100000,
    },

    "employee_management": {
        "name": "Employee Management",
        "category": "business_operations",
        "min": 20000,
        "max": 100000,
    },

    "inventory_management": {
        "name": "Inventory Management",
        "category": "business_operations",
        "min": 50000,
        "max": 200000,
    },

    "product_management": {
        "name": "Product Management",
        "category": "business_operations",
        "min": 20000,
        "max": 100000,
    },

    "order_management": {
        "name": "Order Management",
        "category": "business_operations",
        "min": 25000,
        "max": 150000,
    },

    "procurement_management": {
        "name": "Procurement Management",
        "category": "business_operations",
        "min": 50000,
        "max": 200000,
    },

    "asset_management": {
        "name": "Asset Management",
        "category": "business_operations",
        "min": 25000,
        "max": 150000,
    },

    "fleet_management": {
        "name": "Fleet Management",
        "category": "business_operations",
        "min": 70000,
        "max": 300000,
    },

    "logistics_management": {
        "name": "Logistics Management",
        "category": "business_operations",
        "min": 100000,
        "max": 300000,
    },


    # ========================================================
    # WORKFLOW / AUTOMATION
    # ========================================================

    "workflow_automation": {
        "name": "Workflow Automation",
        "category": "automation",
        "min": 50000,
        "max": 200000,
    },

    "business_process_automation": {
        "name": "Business Process Automation",
        "category": "automation",
        "min": 70000,
        "max": 350000,
    },

    "task_management": {
        "name": "Task Management",
        "category": "automation",
        "min": 20000,
        "max": 100000,
    },

    "project_management": {
        "name": "Project Management",
        "category": "automation",
        "min": 50000,
        "max": 200000,
    },

    "approval_workflows": {
        "name": "Approval Workflows",
        "category": "automation",
        "min": 25000,
        "max": 150000,
    },

    "custom_business_logic": {
        "name": "Custom Business Logic",
        "category": "automation",
        "min": 50000,
        "max": 200000,
    },

    "custom_calculations": {
        "name": "Custom Calculations",
        "category": "automation",
        "min": 20000,
        "max": 100000,
    },

    "rules_engine": {
        "name": "Rules Engine",
        "category": "automation",
        "min": 50000,
        "max": 200000,
    },

    "background_jobs": {
        "name": "Background Jobs",
        "category": "automation",
        "min": 20000,
        "max": 100000,
    },

    "queue_processing": {
        "name": "Queue Processing",
        "category": "automation",
        "min": 25000,
        "max": 100000,
    },

    "scheduled_jobs": {
        "name": "Scheduled Jobs",
        "category": "automation",
        "min": 10000,
        "max": 70000,
    },


    # ========================================================
    # BOOKING / SCHEDULING
    # ========================================================

    "scheduling": {
        "name": "Scheduling",
        "category": "booking",
        "min": 20000,
        "max": 100000,
    },

    "appointment_booking": {
        "name": "Appointment Booking",
        "category": "booking",
        "min": 25000,
        "max": 150000,
    },

    "calendar_integration": {
        "name": "Calendar Integration",
        "category": "booking",
        "min": 20000,
        "max": 100000,
    },

    "booking_system": {
        "name": "Booking System",
        "category": "booking",
        "min": 50000,
        "max": 200000,
    },

    "availability_management": {
        "name": "Availability Management",
        "category": "booking",
        "min": 20000,
        "max": 100000,
    },

    "reservation_management": {
        "name": "Reservation Management",
        "category": "booking",
        "min": 25000,
        "max": 150000,
    },


    # ========================================================
    # MARKETPLACE / COMMERCE
    # ========================================================

    "marketplace": {
        "name": "Marketplace",
        "category": "commerce",
        "min": 100000,
        "max": 500000,
    },

    "shopping_cart": {
        "name": "Shopping Cart",
        "category": "commerce",
        "min": 20000,
        "max": 80000,
    },

    "checkout": {
        "name": "Checkout",
        "category": "commerce",
        "min": 20000,
        "max": 100000,
    },

    "wishlist": {
        "name": "Wishlist",
        "category": "commerce",
        "min": 10000,
        "max": 50000,
    },

    "product_catalog": {
        "name": "Product Catalog",
        "category": "commerce",
        "min": 20000,
        "max": 100000,
    },

    "reviews_ratings": {
        "name": "Reviews & Ratings",
        "category": "commerce",
        "min": 20000,
        "max": 100000,
    },

    "seller_management": {
        "name": "Seller Management",
        "category": "commerce",
        "min": 25000,
        "max": 100000,
    },

    "buyer_management": {
        "name": "Buyer Management",
        "category": "commerce",
        "min": 20000,
        "max": 100000,
    },

    "commission_management": {
        "name": "Commission Management",
        "category": "commerce",
        "min": 20000,
        "max": 100000,
    },

    "affiliate_referral_system": {
        "name": "Affiliate / Referral System",
        "category": "commerce",
        "min": 25000,
        "max": 100000,
    },

    "loyalty_rewards": {
        "name": "Loyalty & Rewards",
        "category": "commerce",
        "min": 25000,
        "max": 100000,
    },


    # ========================================================
    # PORTALS
    # ========================================================

    "client_portal": {
        "name": "Client Portal",
        "category": "portal",
        "min": 50000,
        "max": 200000,
    },

    "customer_portal": {
        "name": "Customer Portal",
        "category": "portal",
        "min": 50000,
        "max": 200000,
    },

    "vendor_portal": {
        "name": "Vendor Portal",
        "category": "portal",
        "min": 50000,
        "max": 200000,
    },

    "staff_portal": {
        "name": "Staff Portal",
        "category": "portal",
        "min": 50000,
        "max": 200000,
    },

    "admin_portal": {
        "name": "Admin Portal",
        "category": "portal",
        "min": 50000,
        "max": 200000,
    },

    "self_service_portal": {
        "name": "Self-Service Portal",
        "category": "portal",
        "min": 50000,
        "max": 200000,
    },


    # ========================================================
    # AI
    # ========================================================

    "ai_integration": {
        "name": "AI Integration",
        "category": "ai",
        "min": 50000,
        "max": 200000,
    },

    "ai_chatbot": {
        "name": "AI Chatbot",
        "category": "ai",
        "min": 50000,
        "max": 200000,
    },

    "ai_assistant": {
        "name": "AI Assistant",
        "category": "ai",
        "min": 50000,
        "max": 200000,
    },

    "ai_content_generation": {
        "name": "AI Content Generation",
        "category": "ai",
        "min": 50000,
        "max": 200000,
    },

    "ai_document_processing": {
        "name": "AI Document Processing",
        "category": "ai",
        "min": 70000,
        "max": 350000,
    },

    "ai_search": {
        "name": "AI Search",
        "category": "ai",
        "min": 70000,
        "max": 350000,
    },

    "ai_recommendation": {
        "name": "AI Recommendation",
        "category": "ai",
        "min": 70000,
        "max": 350000,
    },

    "ai_prediction": {
        "name": "AI Prediction",
        "category": "ai",
        "min": 200000,
        "max": 750000,
    },

    "machine_learning_integration": {
        "name": "Machine Learning Integration",
        "category": "ai",
        "min": 250000,
        "max": 1000000,
    },

    "ocr": {
        "name": "OCR",
        "category": "ai",
        "min": 25000,
        "max": 150000,
    },

    "speech_to_text": {
        "name": "Speech to Text",
        "category": "ai",
        "min": 25000,
        "max": 150000,
    },

    "text_to_speech": {
        "name": "Text to Speech",
        "category": "ai",
        "min": 25000,
        "max": 150000,
    },

    "translation": {
        "name": "Translation",
        "category": "ai",
        "min": 20000,
        "max": 100000,
    },

    "image_processing": {
        "name": "Image Processing",
        "category": "ai",
        "min": 25000,
        "max": 150000,
    },

    "video_processing": {
        "name": "Video Processing",
        "category": "ai",
        "min": 50000,
        "max": 250000,
    },


    # ========================================================
    # LOCATION / MOBILE / DEVICES
    # ========================================================

    "maps_geolocation": {
        "name": "Maps & Geolocation",
        "category": "location",
        "min": 25000,
        "max": 100000,
    },

    "location_tracking": {
        "name": "Location Tracking",
        "category": "location",
        "min": 50000,
        "max": 250000,
    },

    "route_optimization": {
        "name": "Route Optimization",
        "category": "location",
        "min": 100000,
        "max": 300000,
    },

    "qr_code": {
        "name": "QR Code",
        "category": "mobile",
        "min": 10000,
        "max": 50000,
    },

    "barcode": {
        "name": "Barcode",
        "category": "mobile",
        "min": 10000,
        "max": 50000,
    },

    "camera_integration": {
        "name": "Camera Integration",
        "category": "mobile",
        "min": 30000,
        "max": 70000,
    },

    "bluetooth_integration": {
        "name": "Bluetooth Integration",
        "category": "mobile",
        "min": 25000,
        "max": 150000,
    },

    "nfc_integration": {
        "name": "NFC Integration",
        "category": "mobile",
        "min": 25000,
        "max": 100000,
    },

    "iot_integration": {
        "name": "IoT Integration",
        "category": "devices",
        "min": 70000,
        "max": 250000,
    },

    "offline_functionality": {
        "name": "Offline Functionality",
        "category": "mobile",
        "min": 50000,
        "max": 250000,
    },

    "mobile_device_features": {
        "name": "Mobile Device Features",
        "category": "mobile",
        "min": 20000,
        "max": 150000,
    },


    # ========================================================
    # CONTENT / COMMUNITY
    # ========================================================

    "content_management": {
        "name": "Content Management",
        "category": "content",
        "min": 25000,
        "max": 100000,
    },

    "blog_cms": {
        "name": "Blog CMS",
        "category": "content",
        "min": 20000,
        "max": 100000,
    },

    "knowledge_base": {
        "name": "Knowledge Base",
        "category": "content",
        "min": 25000,
        "max": 150000,
    },

    "forum": {
        "name": "Forum",
        "category": "community",
        "min": 50000,
        "max": 200000,
    },

    "community_management": {
        "name": "Community Management",
        "category": "community",
        "min": 50000,
        "max": 200000,
    },

    "comments": {
        "name": "Comments",
        "category": "community",
        "min": 10000,
        "max": 50000,
    },

    "user_generated_content": {
        "name": "User Generated Content",
        "category": "content",
        "min": 25000,
        "max": 100000,
    },

    "content_moderation": {
        "name": "Content Moderation",
        "category": "content",
        "min": 25000,
        "max": 150000,
    },

    "surveys": {
        "name": "Surveys",
        "category": "content",
        "min": 20000,
        "max": 100000,
    },

    "forms": {
        "name": "Forms",
        "category": "content",
        "min": 20000,
        "max": 100000,
    },

    "form_builder": {
        "name": "Form Builder",
        "category": "content",
        "min": 50000,
        "max": 200000,
    },


    # ========================================================
    # EDUCATION
    # ========================================================

    "learning_management": {
        "name": "Learning Management",
        "category": "education",
        "min": 100000,
        "max": 350000,
    },

    "course_management": {
        "name": "Course Management",
        "category": "education",
        "min": 50000,
        "max": 1000000,
    },

    "lesson_management": {
        "name": "Lesson Management",
        "category": "education",
        "min": 20000,
        "max": 100000,
    },

    "enrollment": {
        "name": "Enrollment",
        "category": "education",
        "min": 20000,
        "max": 100000,
    },

    "progress_tracking": {
        "name": "Progress Tracking",
        "category": "education",
        "min": 20000,
        "max": 100000,
    },

    "assessment_quiz_system": {
        "name": "Assessment & Quiz System",
        "category": "education",
        "min": 25000,
        "max": 100000,
    },

    "exam_system": {
        "name": "Exam System",
        "category": "education",
        "min": 50000,
        "max": 200000,
    },

    "certificate_generation": {
        "name": "Certificate Generation",
        "category": "education",
        "min": 20000,
        "max": 100000,
    },

    "attendance_management": {
        "name": "Attendance Management",
        "category": "education",
        "min": 20000,
        "max": 100000,
    },

    "grade_management": {
        "name": "Grade Management",
        "category": "education",
        "min": 20000,
        "max": 100000,
    },


    # ========================================================
    # HR
    # ========================================================

    "recruitment_system": {
        "name": "Recruitment System",
        "category": "hr",
        "min": 50000,
        "max": 200000,
    },

    "job_posting": {
        "name": "Job Posting",
        "category": "hr",
        "min": 20000,
        "max": 100000,
    },

    "job_application": {
        "name": "Job Application",
        "category": "hr",
        "min": 20000,
        "max": 100000,
    },

    "applicant_tracking": {
        "name": "Applicant Tracking",
        "category": "hr",
        "min": 25000,
        "max": 100000,
    },

    "interview_scheduling": {
        "name": "Interview Scheduling",
        "category": "hr",
        "min": 20000,
        "max": 100000,
    },

    "employee_onboarding": {
        "name": "Employee Onboarding",
        "category": "hr",
        "min": 20000,
        "max": 100000,
    },

    "leave_management": {
        "name": "Leave Management",
        "category": "hr",
        "min": 20000,
        "max": 100000,
    },

    "payroll_integration": {
        "name": "Payroll Integration",
        "category": "hr",
        "min": 25000,
        "max": 150000,
    },


    # ========================================================
    # SECURITY
    # ========================================================

    "security_hardening": {
        "name": "Security Hardening",
        "category": "security",
        "min": 15000,
        "max": 150000,
    },

    "security_monitoring": {
        "name": "Security Monitoring",
        "category": "security",
        "min": 50000,
        "max": 250000,
    },

    "audit_logs": {
        "name": "Audit Logs",
        "category": "security",
        "min": 20000,
        "max": 100000,
    },

    "activity_logs": {
        "name": "Activity Logs",
        "category": "security",
        "min": 10000,
        "max": 80000,
    },

    "fraud_detection": {
        "name": "Fraud Detection",
        "category": "security",
        "min": 70000,
        "max": 350000,
    },

    "identity_verification": {
        "name": "Identity Verification",
        "category": "security",
        "min": 25000,
        "max": 150000,
    },

    "data_encryption": {
        "name": "Data Encryption",
        "category": "security",
        "min": 20000,
        "max": 150000,
    },

    "access_control": {
        "name": "Access Control",
        "category": "security",
        "min": 20000,
        "max": 100000,
    },

    "rate_limiting": {
        "name": "Rate Limiting",
        "category": "security",
        "min": 20000,
        "max": 80000,
    },


    # ========================================================
    # INFRASTRUCTURE / DEVOPS
    # ========================================================

    "cloud_infrastructure": {
        "name": "Cloud Infrastructure",
        "category": "devops",
        "min": 50000,
        "max": 200000,
    },

    "devops": {
        "name": "DevOps",
        "category": "devops",
        "min": 50000,
        "max": 200000,
    },

    "ci_cd": {
        "name": "CI/CD",
        "category": "devops",
        "min": 25000,
        "max": 100000,
    },

    "automated_testing": {
        "name": "Automated Testing",
        "category": "testing",
        "min": 25000,
        "max": 150000,
    },

    "monitoring_logging": {
        "name": "Monitoring & Logging",
        "category": "devops",
        "min": 25000,
        "max": 100000,
    },

    "error_tracking": {
        "name": "Error Tracking",
        "category": "devops",
        "min": 20000,
        "max": 100000,
    },

    "backup_recovery": {
        "name": "Backup & Recovery",
        "category": "devops",
        "min": 25000,
        "max": 100000,
    },

    "disaster_recovery": {
        "name": "Disaster Recovery",
        "category": "devops",
        "min": 70000,
        "max": 350000,
    },

    "load_balancing": {
        "name": "Load Balancing",
        "category": "devops",
        "min": 50000,
        "max": 200000,
    },

    "auto_scaling": {
        "name": "Auto Scaling",
        "category": "devops",
        "min": 50000,
        "max": 200000,
    },

    "caching": {
        "name": "Caching",
        "category": "devops",
        "min": 20000,
        "max": 100000,
    },

    "performance_optimization": {
        "name": "Performance Optimization",
        "category": "devops",
        "min": 25000,
        "max": 200000,
    },

    "scalability": {
        "name": "Scalability",
        "category": "architecture",
        "min": 80000,
        "max": 350000,
    },


    # ========================================================
    # TESTING / QUALITY
    # ========================================================

    "qa_testing": {
        "name": "QA Testing",
        "category": "testing",
        "min": 20000,
        "max": 100000,
    },

    "unit_testing": {
        "name": "Unit Testing",
        "category": "testing",
        "min": 10000,
        "max": 100000,
    },

    "integration_testing": {
        "name": "Integration Testing",
        "category": "testing",
        "min": 25000,
        "max": 100000,
    },

    "api_testing": {
        "name": "API Testing",
        "category": "testing",
        "min": 20000,
        "max": 100000,
    },

    "end_to_end_testing": {
        "name": "End-to-End Testing",
        "category": "testing",
        "min": 25000,
        "max": 150000,
    },

    "load_testing": {
        "name": "Load Testing",
        "category": "testing",
        "min": 50000,
        "max": 200000,
    },

    "security_testing": {
        "name": "Security Testing",
        "category": "testing",
        "min": 50000,
        "max": 200000,
    },


    # ========================================================
    # MIGRATION
    # ========================================================

    "system_migration": {
        "name": "System Migration",
        "category": "migration",
        "min": 70000,
        "max": 350000,
    },

    "legacy_system_integration": {
        "name": "Legacy System Integration",
        "category": "migration",
        "min": 70000,
        "max": 350000,
    },

    "legacy_data_migration": {
        "name": "Legacy Data Migration",
        "category": "migration",
        "min": 70000,
        "max": 350000,
    },

    "data_cleanup": {
        "name": "Data Cleanup",
        "category": "migration",
        "min": 20000,
        "max": 150000,
    },

    "data_deduplication": {
        "name": "Data Deduplication",
        "category": "migration",
        "min": 20000,
        "max": 150000,
    },


    # ========================================================
    # UI / UX
    # ========================================================

    "custom_ui_ux": {
        "name": "Custom UI/UX",
        "category": "ui_ux",
        "min": 50000,
        "max": 200000,
    },

    "custom_design_system": {
        "name": "Custom Design System",
        "category": "ui_ux",
        "min": 50000,
        "max": 200000,
    },

    "responsive_application": {
        "name": "Responsive Application",
        "category": "ui_ux",
        "min": 20000,
        "max": 100000,
    },

    "dark_mode": {
        "name": "Dark Mode",
        "category": "ui_ux",
        "min": 10000,
        "max": 50000,
    },

    "accessibility": {
        "name": "Accessibility",
        "category": "ui_ux",
        "min": 20000,
        "max": 150000,
    },

    "multi_language": {
        "name": "Multi-Language",
        "category": "ui_ux",
        "min": 20000,
        "max": 150000,
    },

    "localization": {
        "name": "Localization",
        "category": "ui_ux",
        "min": 20000,
        "max": 150000,
    },


    # ========================================================
    # SAAS / LICENSING
    # ========================================================

    "saas_functionality": {
        "name": "SaaS Functionality",
        "category": "saas",
        "min": 50000,
        "max": 250000,
    },

    "licensing": {
        "name": "Licensing",
        "category": "saas",
        "min": 25000,
        "max": 100000,
    },

    "feature_entitlements": {
        "name": "Feature Entitlements",
        "category": "saas",
        "min": 25000,
        "max": 100000,
    },

    "usage_tracking": {
        "name": "Usage Tracking",
        "category": "saas",
        "min": 20000,
        "max": 150000,
    },

    "usage_based_billing": {
        "name": "Usage-Based Billing",
        "category": "saas",
        "min": 20000,
        "max": 100000,
    },


    # ========================================================
    # CONTRACTS / BUSINESS DOCUMENTS
    # ========================================================

    "contract_management": {
        "name": "Contract Management",
        "category": "contracts",
        "min": 50000,
        "max": 200000,
    },

    "contract_generation": {
        "name": "Contract Generation",
        "category": "contracts",
        "min": 20000,
        "max": 100000,
    },

    "contract_approval": {
        "name": "Contract Approval",
        "category": "contracts",
        "min": 20000,
        "max": 100000,
    },

    "compliance_features": {
        "name": "Compliance Features",
        "category": "security",
        "min": 50000,
        "max": 200000,
    },


    # ========================================================
    # DELIVERY / LOGISTICS
    # ========================================================

    "delivery_tracking": {
        "name": "Delivery Tracking",
        "category": "logistics",
        "min": 50000,
        "max": 200000,
    },

    "dispatch_management": {
        "name": "Dispatch Management",
        "category": "logistics",
        "min": 50000,
        "max": 200000,
    },

    "driver_management": {
        "name": "Driver Management",
        "category": "logistics",
        "min": 25000,
        "max": 100000,
    },

    "vehicle_management": {
        "name": "Vehicle Management",
        "category": "logistics",
        "min": 25000,
        "max": 100000,
    },

    "fuel_tracking": {
        "name": "Fuel Tracking",
        "category": "logistics",
        "min": 20000,
        "max": 100000,
    },


    # ========================================================
    # CUSTOMIZATION
    # ========================================================

    "custom_admin_panel": {
        "name": "Custom Admin Panel",
        "category": "customization",
        "min": 50000,
        "max": 200000,
    },

    "custom_portal": {
        "name": "Custom Portal",
        "category": "customization",
        "min": 50000,
        "max": 200000,
    },

    "custom_business_rules": {
        "name": "Custom Business Rules",
        "category": "customization",
        "min": 25000,
        "max": 150000,
    },

    "custom_workflows": {
        "name": "Custom Workflows",
        "category": "customization",
        "min": 50000,
        "max": 200000,
    },

    "custom_permissions": {
        "name": "Custom Permissions",
        "category": "customization",
        "min": 20000,
        "max": 100000,
    },


    # ========================================================
    # ARCHITECTURE / CONSULTING
    # ========================================================

    "software_architecture": {
        "name": "Software Architecture",
        "category": "architecture",
        "min": 50000,
        "max": 200000,
    },

    "technical_consulting": {
        "name": "Technical Consulting",
        "category": "consulting",
        "min": 20000,
        "max": 100000,
    },

    "system_design": {
        "name": "System Design",
        "category": "architecture",
        "min": 50000,
        "max": 200000,
    },


    # ========================================================
    # MAINTENANCE / SUPPORT
    # ========================================================

    "maintenance_support": {
        "name": "Maintenance & Support",
        "category": "maintenance",
        "min": 50000,
        "max": 200000,
    },

    "application_monitoring": {
        "name": "Application Monitoring",
        "category": "maintenance",
        "min": 25000,
        "max": 100000,
    },

    "ongoing_maintenance": {
        "name": "Ongoing Maintenance",
        "category": "maintenance",
        "min": 50000,
        "max": 200000,
    },
}


# ============================================================
# HELPERS
# ============================================================

def get_pricing(feature_key: str) -> dict | None:
    """
    Return pricing information for a recognized feature.
    """

    return PRICING_CATALOG.get(feature_key)


def feature_exists(feature_key: str) -> bool:
    """
    Check whether a feature is recognized by the backend.
    """

    return feature_key in PRICING_CATALOG


def get_feature_name(feature_key: str) -> str | None:
    """
    Return the human-readable name of a recognized feature.
    """

    feature = PRICING_CATALOG.get(feature_key)

    if not feature:
        return None

    return feature["name"]


def get_price_range(feature_key: str) -> tuple[int, int] | None:
    """
    Return (minimum, maximum) pricing for a feature.
    """

    feature = PRICING_CATALOG.get(feature_key)

    if not feature:
        return None

    return feature["min"], feature["max"]


def calculate_price(
    feature_key: str,
    complexity: str = "medium",
) -> Decimal:
    """
    Calculate a price inside the feature's configured range.

    Complexity determines where the price sits inside the range.

    low    -> minimum
    medium -> midpoint
    high   -> maximum
    """

    feature = PRICING_CATALOG.get(feature_key)

    if not feature:
        raise ValueError(
            f"Unknown feature key: {feature_key}"
        )

    minimum = Decimal(str(feature["min"]))
    maximum = Decimal(str(feature["max"]))

    complexity = complexity.lower()

    if complexity == "low":
        return minimum

    if complexity == "high":
        return maximum

    # Medium
    return (minimum + maximum) / Decimal("2")


def calculate_feature_total(
    feature_key: str,
    complexity: str = "medium",
    quantity: int = 1,
) -> Decimal:
    """
    Calculate total price for a feature.
    """

    if quantity < 1:
        raise ValueError("Quantity must be at least 1.")

    unit_price = calculate_price(
        feature_key=feature_key,
        complexity=complexity,
    )

    return unit_price * quantity


def get_features_by_category(category: str) -> dict:
    """
    Return all features belonging to a category.
    """

    return {
        key: value
        for key, value in PRICING_CATALOG.items()
        if value.get("category") == category
    }


def get_all_feature_keys() -> list[str]:
    """
    Return every recognized feature key.
    """

    return list(PRICING_CATALOG.keys())


def validate_feature_keys(feature_keys: list[str]) -> list[str]:
    """
    Return feature keys that are NOT recognized.
    """

    return [
        key
        for key in feature_keys
        if key not in PRICING_CATALOG
    ]