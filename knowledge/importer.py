import json
import re
from pathlib import Path

from django.db import transaction
from django.utils.text import slugify



SUPPORTED_EXTENSIONS = {
    ".json",
    ".md",
    ".markdown",
    ".txt",
}


def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def ensure_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, str):
        lines = [
            line.strip("- •* \t")
            for line in value.splitlines()
            if line.strip()
        ]

        return lines

    return [value]


def ensure_dict(value):
    if isinstance(value, dict):
        return value

    return {}


def unique_slug(model, value, current=None):
    base = slugify(value)

    if not base:
        base = "item"

    slug = base
    counter = 2

    while True:
        queryset = model.objects.filter(slug=slug)

        if current:
            queryset = queryset.exclude(pk=current.pk)

        if not queryset.exists():
            return slug

        slug = f"{base}-{counter}"
        counter += 1


def normalize_type(value):
    value = clean_text(value).lower()

    aliases = {
        "knowledge": "knowledge",
        "article": "knowledge",
        "articles": "knowledge",
        "knowledge_article": "knowledge",
        "knowledge-article": "knowledge",

        "service": "service",
        "services": "service",

        "product": "product",
        "products": "product",

        "course": "course",
        "courses": "course",
        "training": "course",
        "training_course": "course",
        "training-course": "course",
    }

    return aliases.get(value, value)


def detect_item_type(item):
    explicit = item.get("type") or item.get("content_type")

    if explicit:
        normalized = normalize_type(explicit)

        if normalized in {
            "knowledge",
            "service",
            "product",
            "course",
        }:
            return normalized

    keys = {
        str(key).lower()
        for key in item.keys()
    }

    if {
        "capabilities",
        "problems_solved",
        "deliverables",
    } & keys:
        return "service"

    if {
        "features",
        "specifications",
        "product_type",
    } & keys:
        return "product"

    if {
        "curriculum",
        "learning_outcomes",
        "prerequisites",
    } & keys:
        return "course"

    return "knowledge"


def load_json(content):
    parsed = json.loads(content)

    if isinstance(parsed, list):
        return {
            "items": parsed
        }

    if not isinstance(parsed, dict):
        raise ValueError("JSON root must be an object or array.")

    return parsed


def normalize_json_payload(payload):
    """
    Accepts both:

    {
        "knowledge": [],
        "services": [],
        "products": [],
        "courses": []
    }

    and:

    {
        "items": [
            {"type": "service", ...}
        ]
    }
    """

    records = []

    mapping = {
        "knowledge": "knowledge",
        "articles": "knowledge",
        "knowledge_articles": "knowledge",

        "services": "service",

        "products": "product",

        "courses": "course",
        "training": "course",
        "training_courses": "course",
    }

    for key, item_type in mapping.items():

        values = payload.get(key)

        if not values:
            continue

        if not isinstance(values, list):
            values = [values]

        for value in values:

            if not isinstance(value, dict):
                continue

            record = dict(value)
            record["type"] = item_type

            records.append(record)

    generic_items = payload.get("items", [])

    if isinstance(generic_items, dict):
        generic_items = [generic_items]

    for item in generic_items:

        if not isinstance(item, dict):
            continue

        records.append(item)

    return records


def parse_markdown(content):
    """
    Supports structured markdown sections.

    Example:

    ## SERVICE
    ### Name
    Custom Software Development

    ### Category
    Software Engineering

    ### Description
    ...

    ### Capabilities
    - Web applications
    - APIs

    """

    records = []

    blocks = re.split(
        r"(?=^##\s+)",
        content,
        flags=re.MULTILINE
    )

    for block in blocks:

        block = block.strip()

        if not block:
            continue

        header_match = re.match(
            r"^##\s+(.+)",
            block
        )

        if not header_match:
            continue

        header = header_match.group(1).strip()

        header_upper = header.upper()

        if "SERVICE" in header_upper:
            item_type = "service"

        elif "PRODUCT" in header_upper:
            item_type = "product"

        elif "TRAINING" in header_upper or "COURSE" in header_upper:
            item_type = "course"

        elif "KNOWLEDGE" in header_upper or "ARTICLE" in header_upper:
            item_type = "knowledge"

        else:
            item_type = "knowledge"

        fields = {}

        field_matches = list(
            re.finditer(
                r"^###\s+(.+?)\s*$",
                block,
                flags=re.MULTILINE
            )
        )

        for index, match in enumerate(field_matches):

            field_name = match.group(1).strip()

            start = match.end()

            if index + 1 < len(field_matches):
                end = field_matches[index + 1].start()
            else:
                end = len(block)

            value = block[start:end].strip()

            key = slugify(field_name).replace("-", "_")

            fields[key] = value

        if not fields:

            fields = {
                "title": header,
                "content": block,
            }

        fields["type"] = item_type

        records.append(fields)

    return records


def parse_text(content):
    """
    Simple fallback parser.
    """

    return [{
        "type": "knowledge",
        "title": "Imported Knowledge",
        "content": content,
    }]


def parse_content(content, filename=""):
    extension = Path(filename).suffix.lower()

    if extension == ".json":

        payload = load_json(content)

        return normalize_json_payload(payload)

    if extension in {".md", ".markdown"}:

        return parse_markdown(content)

    return parse_text(content)


def get_title(item, default="Untitled"):
    return clean_text(
        item.get("title")
        or item.get("name")
        or item.get("service_name")
        or item.get("product_name")
        or item.get("course_name")
        or default
    )


@transaction.atomic
def import_article(item, source=""):
    title = get_title(item)

    slug = clean_text(
        item.get("slug")
    )

    if not slug:
        slug = slugify(title)

    existing = KnowledgeArticle.objects.filter(
        slug=slug
    ).first()

    if existing:

        existing.title = title
        existing.category = clean_text(item.get("category"))
        existing.summary = clean_text(
            item.get("summary")
            or item.get("short_description")
        )
        existing.content = clean_text(
            item.get("content")
            or item.get("description")
        )
        existing.keywords = ensure_list(
            item.get("keywords")
        )
        existing.source = source

        existing.save()

        return existing, False

    article = KnowledgeArticle.objects.create(
        title=title,
        slug=unique_slug(
            KnowledgeArticle,
            slug
        ),
        category=clean_text(
            item.get("category")
        ),
        summary=clean_text(
            item.get("summary")
            or item.get("short_description")
        ),
        content=clean_text(
            item.get("content")
            or item.get("description")
        ),
        keywords=ensure_list(
            item.get("keywords")
        ),
        source=source,
    )

    return article, True


@transaction.atomic
def import_service(item):
    name = get_title(item)

    slug = clean_text(item.get("slug"))

    if not slug:
        slug = slugify(name)

    existing = Service.objects.filter(
        slug=slug
    ).first()

    values = {
        "name": name,
        "category": clean_text(
            item.get("category")
        ),
        "short_description": clean_text(
            item.get("short_description")
        ),
        "description": clean_text(
            item.get("description")
        ),
        "capabilities": ensure_list(
            item.get("capabilities")
        ),
        "problems_solved": ensure_list(
            item.get("problems_solved")
        ),
        "use_cases": ensure_list(
            item.get("use_cases")
        ),
        "industries": ensure_list(
            item.get("industries")
        ),
        "deliverables": ensure_list(
            item.get("deliverables")
        ),
        "technologies": ensure_list(
            item.get("technologies")
        ),
        "faqs": ensure_list(
            item.get("faqs")
        ),
        "related_services": ensure_list(
            item.get("related_services")
        ),
        "keywords": ensure_list(
            item.get("keywords")
        ),
        "client_inputs": ensure_list(
            item.get("client_inputs")
        ),
        "ai_guidance": clean_text(
            item.get("ai_guidance")
        ),
    }

    if existing:

        for key, value in values.items():
            setattr(existing, key, value)

        existing.save()

        return existing, False

    service = Service.objects.create(
        slug=unique_slug(
            Service,
            slug
        ),
        **values
    )

    return service, True


@transaction.atomic
def import_product(item):
    name = get_title(item)

    slug = clean_text(item.get("slug"))

    if not slug:
        slug = slugify(name)

    existing = Product.objects.filter(
        slug=slug
    ).first()

    values = {
        "name": name,
        "category": clean_text(
            item.get("category")
        ),
        "product_type": clean_text(
            item.get("product_type")
        ),
        "short_description": clean_text(
            item.get("short_description")
        ),
        "description": clean_text(
            item.get("description")
        ),
        "features": ensure_list(
            item.get("features")
        ),
        "use_cases": ensure_list(
            item.get("use_cases")
        ),
        "industries": ensure_list(
            item.get("industries")
        ),
        "specifications": ensure_dict(
            item.get("specifications")
        ),
        "technologies": ensure_list(
            item.get("technologies")
        ),
        "keywords": ensure_list(
            item.get("keywords")
        ),
        "currency": clean_text(
            item.get("currency")
            or "NGN"
        ),
    }

    if existing:

        for key, value in values.items():
            setattr(existing, key, value)

        if item.get("price") not in (None, ""):
            existing.price = item["price"]

        existing.save()

        return existing, False

    if item.get("price") in (None, ""):
        price = None
    else:
        price = item["price"]

    product = Product.objects.create(
        slug=unique_slug(
            Product,
            slug
        ),
        price=price,
        **values
    )

    return product, True


@transaction.atomic
def import_course(item):
    name = get_title(item)

    slug = clean_text(item.get("slug"))

    if not slug:
        slug = slugify(name)

    existing = TrainingCourse.objects.filter(
        slug=slug
    ).first()

    values = {
        "name": name,
        "category": clean_text(
            item.get("category")
        ),
        "short_description": clean_text(
            item.get("short_description")
        ),
        "description": clean_text(
            item.get("description")
        ),
        "curriculum": ensure_list(
            item.get("curriculum")
        ),
        "learning_outcomes": ensure_list(
            item.get("learning_outcomes")
        ),
        "target_audience": ensure_list(
            item.get("target_audience")
        ),
        "prerequisites": ensure_list(
            item.get("prerequisites")
        ),
        "technologies": ensure_list(
            item.get("technologies")
        ),
        "duration": clean_text(
            item.get("duration")
        ),
        "level": clean_text(
            item.get("level")
        ),
        "keywords": ensure_list(
            item.get("keywords")
        ),
        "currency": clean_text(
            item.get("currency")
            or "NGN"
        ),
    }

    if existing:

        for key, value in values.items():
            setattr(existing, key, value)

        if item.get("price") not in (None, ""):
            existing.price = item["price"]

        existing.save()

        return existing, False

    if item.get("price") in (None, ""):
        price = None
    else:
        price = item["price"]

    course = TrainingCourse.objects.create(
        slug=unique_slug(
            TrainingCourse,
            slug
        ),
        price=price,
        **values
    )

    return course, True


def run_import(
    content,
    filename="",
    content_type="auto",
):
    run = ImportRun.objects.create(
        filename=filename,
        content_type=content_type,
        status="processing",
    )

    try:

        records = parse_content(
            content=content,
            filename=filename,
        )

        run.total_items = len(records)

        for item in records:

            try:

                detected_type = (
                    normalize_type(content_type)
                    if content_type != "auto"
                    else detect_item_type(item)
                )

                if detected_type == "knowledge":

                    _, created = import_article(
                        item,
                        source=filename
                    )

                    if created:
                        run.articles_created += 1
                    else:
                        run.articles_updated += 1

                elif detected_type == "service":

                    _, created = import_service(item)

                    if created:
                        run.services_created += 1
                    else:
                        run.services_updated += 1

                elif detected_type == "product":

                    _, created = import_product(item)

                    if created:
                        run.products_created += 1
                    else:
                        run.products_updated += 1

                elif detected_type == "course":

                    _, created = import_course(item)

                    if created:
                        run.courses_created += 1
                    else:
                        run.courses_updated += 1

                else:

                    raise ValueError(
                        f"Unsupported content type: {detected_type}"
                    )

            except Exception as exc:

                run.errors.append({
                    "item": get_title(
                        item,
                        default="Unknown item"
                    ),
                    "error": str(exc),
                })

        run.status = (
            "completed_with_errors"
            if run.errors
            else "completed"
        )

        run.save()

        return run

    except Exception as exc:

        run.status = "failed"

        run.errors = [{
            "error": str(exc)
        }]

        run.save()

        raise