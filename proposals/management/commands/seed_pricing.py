from decimal import Decimal

from django.core.management.base import BaseCommand

from proposals.models import (
    PricingRegion,
    PricingRule,
)


class Command(BaseCommand):

    help = "Create AB Technologies default pricing rules."

    def handle(self, *args, **options):

        region, _ = PricingRegion.objects.update_or_create(
            country_code="NG",
            defaults={
                "name": "Nigeria",
                "currency": "NGN",
                "is_active": True,
            },
        )

        rules = [
            # ------------------------------------------------
            # BASE PROJECTS
            # ------------------------------------------------

            {
                "name": "Standard Website",
                "code": "website_base",
                "rule_type": "base",
                "base_price": "500000",
            },

            {
                "name": "Mobile Application",
                "code": "mobile_base",
                "rule_type": "mobile",
                "base_price": "1500000",
            },

            {
                "name": "Web Application",
                "code": "webapp_base",
                "rule_type": "base",
                "base_price": "1000000",
            },

            {
                "name": "Custom Software",
                "code": "software_base",
                "rule_type": "base",
                "base_price": "1000000",
            },

            {
                "name": "Custom Project",
                "code": "custom_base",
                "rule_type": "custom",
                "base_price": "500000",
            },

            # ------------------------------------------------
            # AUTHENTICATION
            # ------------------------------------------------

            {
                "name": "Basic Authentication",
                "code": "auth_basic",
                "rule_type": "authentication",
                "base_price": "0",
            },

            {
                "name": "Intermediate Authentication",
                "code": "auth_intermediate",
                "rule_type": "authentication",
                "base_price": "100000",
            },

            {
                "name": "Advanced Authentication",
                "code": "auth_advanced",
                "rule_type": "authentication",
                "base_price": "250000",
            },

            {
                "name": "Enterprise Authentication",
                "code": "auth_enterprise",
                "rule_type": "authentication",
                "base_price": "500000",
            },

            # ------------------------------------------------
            # BACKEND
            # ------------------------------------------------

            {
                "name": "Backend Development",
                "code": "backend",
                "rule_type": "backend",
                "base_price": "300000",
            },

            # ------------------------------------------------
            # DATABASE
            # ------------------------------------------------

            {
                "name": "Database Architecture",
                "code": "database",
                "rule_type": "database",
                "base_price": "150000",
            },

            # ------------------------------------------------
            # DEVOPS
            # ------------------------------------------------

            {
                "name": "DevOps & Deployment",
                "code": "devops",
                "rule_type": "devops",
                "base_price": "150000",
            },

            # ------------------------------------------------
            # EXTERNAL SERVICES
            # ------------------------------------------------

            {
                "name": "Email Integration",
                "code": "email_integration",
                "rule_type": "integration",
                "base_price": "100000",
            },

            {
                "name": "SMS Integration",
                "code": "sms_integration",
                "rule_type": "integration",
                "base_price": "150000",
            },

            {
                "name": "Payment Integration",
                "code": "payment_integration",
                "rule_type": "integration",
                "base_price": "200000",
            },

            {
                "name": "Maps Integration",
                "code": "maps_integration",
                "rule_type": "integration",
                "base_price": "200000",
            },

            {
                "name": "AI Integration",
                "code": "ai_integration",
                "rule_type": "integration",
                "base_price": "300000",
            },

            {
                "name": "Storage Integration",
                "code": "storage_integration",
                "rule_type": "integration",
                "base_price": "150000",
            },

            {
                "name": "WhatsApp Integration",
                "code": "whatsapp_integration",
                "rule_type": "integration",
                "base_price": "200000",
            },
        ]

        for item in rules:

            PricingRule.objects.update_or_create(
                region=region,
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "rule_type": item["rule_type"],
                    "base_price": Decimal(
                        item["base_price"]
                    ),
                    "is_active": True,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "AB Technologies pricing rules created successfully."
            )
        )