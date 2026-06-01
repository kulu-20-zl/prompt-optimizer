from backend.models import PolishRecord


def paginate_records(user_id: int, page: int = 1, per_page: int = 10):
    """Return paginated polish records for a user (newest first)."""
    page = max(1, page)
    per_page = max(1, min(per_page, 50))

    query = (
        PolishRecord.query.filter_by(user_id=user_id)
        .order_by(PolishRecord.created_at.desc())
    )
    total = query.count()
    pages = max(1, (total + per_page - 1) // per_page)

    if page > pages:
        page = pages

    offset = (page - 1) * per_page
    items = query.offset(offset).limit(per_page).all()
    return items, total, pages
