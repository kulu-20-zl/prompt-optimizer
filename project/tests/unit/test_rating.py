from backend.models import PolishRecord
from backend.services.rating import calculate_avg_rating, validate_rating


def test_validate_rating_valid():
    assert validate_rating(1) is True
    assert validate_rating(5) is True
    assert validate_rating(3) is True


def test_validate_rating_invalid():
    assert validate_rating(0) is False
    assert validate_rating(6) is False
    assert validate_rating("abc") is False
    assert validate_rating(None) is False


def test_calculate_avg_rating(db_session, logged_in_user):
    records = [
        PolishRecord(
            user_id=logged_in_user.id,
            original_text="a",
            polished_text="b",
            rating=5,
        ),
        PolishRecord(
            user_id=logged_in_user.id,
            original_text="c",
            polished_text="d",
            rating=3,
        ),
        PolishRecord(
            user_id=logged_in_user.id,
            original_text="e",
            polished_text="f",
            rating=None,
        ),
    ]
    for r in records:
        db_session.add(r)
    db_session.commit()

    avg = calculate_avg_rating(logged_in_user.id)
    assert avg == 4.0


def test_calculate_avg_no_ratings(db_session, logged_in_user):
    db_session.add(
        PolishRecord(
            user_id=logged_in_user.id,
            original_text="a",
            polished_text="b",
        )
    )
    db_session.commit()
    assert calculate_avg_rating(logged_in_user.id) == 0.0


def test_calculate_avg_single_rating(db_session, logged_in_user):
    db_session.add(
        PolishRecord(
            user_id=logged_in_user.id,
            original_text="a",
            polished_text="b",
            rating=4,
        )
    )
    db_session.commit()
    assert calculate_avg_rating(logged_in_user.id) == 4.0
