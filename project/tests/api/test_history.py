from backend.models import PolishRecord, User


def test_history_default_pagination(logged_in_client, db_session, logged_in_user):
    for i in range(15):
        db_session.add(
            PolishRecord(
                user_id=logged_in_user.id,
                original_text=f"orig{i}",
                polished_text=f"pol{i}",
            )
        )
    db_session.commit()

    response = logged_in_client.get("/api/history")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["items"]) == 10
    assert data["total"] == 15
    assert data["page"] == 1
    assert data["pages"] == 2


def test_history_not_logged_in(client):
    response = client.get("/api/history")
    assert response.status_code == 401


def test_history_negative_page(logged_in_client):
    response = logged_in_client.get("/api/history?page=-1")
    assert response.status_code == 400


def test_history_invalid_page_param(logged_in_client):
    response = logged_in_client.get("/api/history?page=abc")
    assert response.status_code == 400


def test_history_per_page_limit(logged_in_client, db_session, logged_in_user):
    for i in range(5):
        db_session.add(
            PolishRecord(
                user_id=logged_in_user.id,
                original_text=f"t{i}",
                polished_text=f"p{i}",
            )
        )
    db_session.commit()

    response = logged_in_client.get("/api/history?per_page=1000")
    assert response.status_code == 200
    assert len(response.get_json()["items"]) == 5


def test_delete_record(logged_in_client, db_session, logged_in_user):
    record = PolishRecord(
        user_id=logged_in_user.id,
        original_text="del",
        polished_text="deleted",
    )
    db_session.add(record)
    db_session.commit()
    rid = record.id

    response = logged_in_client.delete(f"/api/record/{rid}")
    assert response.status_code == 200
    assert PolishRecord.query.get(rid) is None


def test_delete_record_not_owner(logged_in_client, db_session):
    other = User(username="other")
    other.set_password("pass")
    db_session.add(other)
    db_session.commit()

    record = PolishRecord(
        user_id=other.id, original_text="other", polished_text="text"
    )
    db_session.add(record)
    db_session.commit()

    response = logged_in_client.delete(f"/api/record/{record.id}")
    assert response.status_code == 403


def test_delete_record_not_found(logged_in_client):
    response = logged_in_client.delete("/api/record/99999")
    assert response.status_code == 404
