from .models import (
    KnowledgeArticle,
    Service,
    Product,
    TrainingCourse,
)


def search_knowledge(query, limit=5):
    """
    Search AB Technologies knowledge.
    """

    query = (query or "").strip()

    if not query:
        return {
            "articles": [],
            "services": [],
            "products": [],
            "courses": [],
        }

    terms = query.lower().split()

    articles = []
    services = []
    products = []
    courses = []

    active_articles = KnowledgeArticle.objects.filter(
        is_active=True
    )

    for article in active_articles:
        searchable = " ".join([
            article.title,
            article.content,
            article.keywords,
            article.category,
        ]).lower()

        score = sum(
            1 for term in terms
            if term in searchable
        )

        if score:
            articles.append(
                (score, article)
            )

    articles.sort(
        key=lambda item: item[0],
        reverse=True
    )

    active_services = Service.objects.filter(
        is_active=True
    )

    for service in active_services:
        searchable = " ".join([
            service.name,
            service.short_description,
            service.description,
            service.category,
            service.industries,
            service.features,
        ]).lower()

        score = sum(
            1 for term in terms
            if term in searchable
        )

        if score:
            services.append(
                (score, service)
            )

    services.sort(
        key=lambda item: item[0],
        reverse=True
    )

    active_products = Product.objects.filter(
        is_active=True
    )

    for product in active_products:
        searchable = " ".join([
            product.name,
            product.short_description,
            product.description,
            product.features,
            product.product_type,
        ]).lower()

        score = sum(
            1 for term in terms
            if term in searchable
        )

        if score:
            products.append(
                (score, product)
            )

    products.sort(
        key=lambda item: item[0],
        reverse=True
    )

    active_courses = TrainingCourse.objects.filter(
        is_active=True
    )

    for course in active_courses:
        searchable = " ".join([
            course.name,
            course.description,
            course.level,
            course.duration,
        ]).lower()

        score = sum(
            1 for term in terms
            if term in searchable
        )

        if score:
            courses.append(
                (score, course)
            )

    courses.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return {
        "articles": [
            {
                "title": article.title,
                "category": article.category,
                "content": article.content,
            }
            for _, article in articles[:limit]
        ],

        "services": [
            {
                "name": service.name,
                "category": service.category,
                "description": service.short_description,
                "details": service.description,
                "features": service.features,
            }
            for _, service in services[:limit]
        ],

        "products": [
            {
                "name": product.name,
                "type": product.product_type,
                "description": product.short_description,
                "details": product.description,
                "features": product.features,
                "price": str(product.price)
                if product.price is not None
                else None,
                "currency": product.currency,
            }
            for _, product in products[:limit]
        ],

        "courses": [
            {
                "name": course.name,
                "description": course.description,
                "level": course.level,
                "duration": course.duration,
                "price": str(course.price)
                if course.price is not None
                else None,
                "currency": course.currency,
            }
            for _, course in courses[:limit]
        ],
    }