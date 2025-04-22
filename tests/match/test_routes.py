from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from fastapi import status

from src.match.models.match import Match, MatchStatus


# Test find match endpoint
@patch("src.match.route.add_player_to_queue")
@patch("src.match.route.process_match_queue")
def test_find_match_success(
    mock_process_queue, mock_add_to_queue, client, test_user, test_db
):
    # Setup mocks
    mock_add_to_queue.return_value = AsyncMock(return_value={"status": "added"})
    mock_process_queue.return_value = None

    # Make request
    response = client.post(f"/api/v1/match/find?user_id={test_user.id}")

    # Check response
    assert response.status_code == status.HTTP_200_OK
    assert "Added to match queue" in response.json()["message"]

    # Check mocks
    mock_add_to_queue.assert_called_once_with(test_user.id, test_user.rating)
    mock_process_queue.assert_called_once()


def test_find_match_user_not_found(client, test_db):
    # Make request with non-existent user ID
    response = client.post("/api/v1/match/find?user_id=999")

    # Check response
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "User not found" in response.json()["detail"]


def test_find_match_existing_match(client, test_match, test_db):
    match, opponent = test_match

    # Make request
    response = client.post(f"/api/v1/match/find?user_id={match.player1_id}")

    # Check response
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already have an active or pending match" in response.json()["detail"]


# Test queue status endpoint
def test_queue_status_in_match(client, test_match, test_db):
    match, opponent = test_match

    # Make request
    response = client.get(f"/api/v1/match/queue/status?user_id={match.player1_id}")

    # Check response
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["in_match"] is True
    assert data["match_id"] == match.id
    assert data["status"] == match.status
    assert data["opponent_id"] == str(opponent.id)


def test_queue_status_not_in_match(client, test_user):
    # Make request
    response = client.get(f"/api/v1/match/queue/status?user_id={test_user.id}")

    # Check response
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["in_match"] is False
    assert "Still in queue" in data["message"]


# Test active matches endpoint
def test_get_active_matches_success(client, test_match, test_db):
    match, opponent = test_match

    # Update match to active status
    match.status = MatchStatus.ACTIVE
    test_db.commit()

    # Make request
    response = client.get(f"/api/v1/match/active?user_id={match.player1_id}")

    # Check response
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == match.id
    assert data[0]["player1_id"] == str(match.player1_id)
    assert data[0]["player2_id"] == str(match.player2_id)
    assert data[0]["status"] == MatchStatus.ACTIVE


def test_get_active_matches_none(client, test_user):
    # Make request
    response = client.get(f"/api/v1/match/active?user_id={test_user.id}")

    # Check response
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 0


# Test accept match endpoint
def test_accept_match_success(client, test_match, test_db):
    match, opponent = test_match

    # Make request as player2
    response = client.post(f"/api/v1/match/accept/{match.id}?user_id={opponent.id}")

    # Check response
    assert response.status_code == status.HTTP_200_OK
    assert "Match accepted" in response.json()["message"]

    # Refresh the session to get the latest data
    test_db.expire_all()

    # Check database
    updated_match = test_db.query(Match).filter(Match.id == match.id).first()
    assert updated_match.status == MatchStatus.ACTIVE


def test_accept_match_not_found(client, test_user):
    # Make request with non-existent match ID
    response = client.post(f"/api/v1/match/accept/999?user_id={test_user.id}")

    # Check response
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Match not found" in response.json()["detail"]


def test_accept_match_unauthorized(client, test_match):
    match, opponent = test_match

    # Make request as player1 (not authorized to accept)
    response = client.post(
        f"/api/v1/match/accept/{match.id}?user_id={match.player1_id}"
    )

    # Check response
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Not authorized" in response.json()["detail"]


def test_accept_match_timeout(client, test_match, test_db):
    match, opponent = test_match

    # Set match start time to more than 15 seconds ago
    match.start_time = datetime.utcnow() - timedelta(seconds=20)
    test_db.commit()

    # Make request as player2
    response = client.post(f"/api/v1/match/accept/{match.id}?user_id={opponent.id}")

    # Check response
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "timed out" in response.json()["detail"]

    # Refresh the session to get the latest data
    test_db.expire_all()

    # Check database
    updated_match = test_db.query(Match).filter(Match.id == match.id).first()
    assert updated_match.status == MatchStatus.DECLINED
    assert updated_match.end_time is not None
