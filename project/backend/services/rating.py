from backend.models import PolishRecord


def validate_rating(rating) -> bool:
    """Check if rating is a valid integer between 1 and 5."""
    try:
        value = int(rating)
    except (TypeError, ValueError):
        return False
    return 1 <= value <= 5


def calculate_avg_rating(user_id: int) -> float:
    """Calculate average rating across all rated records for a user."""
    rated = (
        PolishRecord.query.filter_by(user_id=user_id)
        .filter(PolishRecord.rating.isnot(None))
        .all()
    )
    if not rated:
        return 0.0
    return round(sum(r.rating for r in rated) / len(rated), 2)
