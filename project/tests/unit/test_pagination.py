from backend.models import PolishRecord
from backend.services.pagination import paginate_records


def test_history_pagination(db_session, logged_in_user):
    for i in range(30):
        record = PolishRecord(
            user_id=logged_in_user.id,
            original_text=f"text{i}",
            polished_text=f"p{i}",
        )
        db_session.add(record)
    db_session.commit()

    page2_items, total, pages = paginate_records(
        logged_in_user.id, page=2, per_page=10
    )
    assert len(page2_items) == 10
    # 倒序分页：第1页为 text29~text20，第2页首条为 text19
    assert page2_items[0].original_text == "text19"
    assert total == 30
    assert pages == 3


def test_first_page(db_session, logged_in_user):
    for i in range(5):
        db_session.add(
            PolishRecord(
                user_id=logged_in_user.id,
                original_text=f"t{i}",
                polished_text=f"p{i}",
            )
        )
    db_session.commit()

    items, total, pages = paginate_records(logged_in_user.id, page=1, per_page=10)
    assert len(items) == 5
    assert total == 5
    assert pages == 1


def test_empty_history(db_session, logged_in_user):
    items, total, pages = paginate_records(logged_in_user.id)
    assert items == []
    assert total == 0
    assert pages == 1


def test_per_page_capped_at_50(db_session, logged_in_user):
    for i in range(60):
        db_session.add(
            PolishRecord(
                user_id=logged_in_user.id,
                original_text=f"t{i}",
                polished_text=f"p{i}",
            )
        )
    db_session.commit()

    items, total, pages = paginate_records(
        logged_in_user.id, page=1, per_page=1000
    )
    assert len(items) == 50
    assert total == 60
    assert pages == 2


def test_page_beyond_total(db_session, logged_in_user):
    db_session.add(
        PolishRecord(
            user_id=logged_in_user.id,
            original_text="only",
            polished_text="one",
        )
    )
    db_session.commit()

    items, total, pages = paginate_records(logged_in_user.id, page=99, per_page=10)
    assert len(items) == 1
    assert pages == 1
