from backend.models import PolishRecord


def test_rate_success(logged_in_client, db_session, logged_in_user):
    record = PolishRecord(
        user_id=logged_in_user.id,
        original_text="rate me",
        polished_text="rated",
    )
    db_session.add(record)
    db_session.commit()

    response = logged_in_client.post(
        f"/api/record/{record.id}/rate", json={"rating": 3}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["new_avg_rating"] == 3.0

    updated = PolishRecord.query.get(record.id)
    assert updated.rating == 3


def test_rate_overwrite(logged_in_client, db_session, logged_in_user):
    record = PolishRecord(
        user_id=logged_in_user.id,
        original_text="a",
        polished_text="b",
        rating=2,
    )
    db_session.add(record)
    db_session.commit()

    response = logged_in_client.post(
        f"/api/record/{record.id}/rate", json={"rating": 5}
    )
    assert response.status_code == 200
    assert PolishRecord.query.get(record.id).rating == 5


def test_rate_invalid(logged_in_client, db_session, logged_in_user):
    record = PolishRecord(
        user_id=logged_in_user.id,
        original_text="a",
        polished_text="b",
    )
    db_session.add(record)
    db_session.commit()

    response = logged_in_client.post(
        f"/api/record/{record.id}/rate", json={"rating": 0}
    )
    assert response.status_code == 400

    response = logged_in_client.post(
        f"/api/record/{record.id}/rate", json={"rating": 6}
    )
    assert response.status_code == 400


def test_rate_not_owner(logged_in_client, db_session):
    from backend.models import User

    other = User(username="rateother")
    other.set_password("pass")
    db_session.add(other)
    db_session.commit()

    record = PolishRecord(
        user_id=other.id, original_text="x", polished_text="y"
    )
    db_session.add(record)
    db_session.commit()

    response = logged_in_client.post(
        f"/api/record/{record.id}/rate", json={"rating": 3}
    )
    assert response.status_code == 403


def test_rate_not_found(logged_in_client):
    response = logged_in_client.post(
        "/api/record/99999/rate", json={"rating": 3}
    )
    assert response.status_code == 404
