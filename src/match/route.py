from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from src.db.main import get_session
from .models.match import Match, MatchStatus
from src.auth.model import User
from .schemas.match import  MatchResponse
from .service import add_player_to_queue, process_match_queue
from .websocket import manager

router = APIRouter(prefix="/match", tags=["match"])


@router.post("/find")
async def find_match(
    user_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_session)
):
    """
    Add a user to the match queue.
    The user will be matched with another user with a similar rating when available.
    Players can only have one active or pending match at a time.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if the user already has an active or pending match
    existing_match = (
        db.query(Match)
        .filter(
            ((Match.player1_id == user_id) | (Match.player2_id == user_id))
            & (
                (Match.status == MatchStatus.PENDING)
                | (Match.status == MatchStatus.ACTIVE)
            )
        )
        .first()
    )

    if existing_match:
        raise HTTPException(
            status_code=400, detail="You already have an active or pending match"
        )

    # Add the user to the match queue
    result = await add_player_to_queue(user_id, user.rating)

    # Start processing the queue in the background
    background_tasks.add_task(process_match_queue, db)

    return {
        "message": "Added to match queue. You will be matched with a player of similar rating."
    }


@router.get("/queue/status")
async def get_queue_status(user_id: int, db: Session = Depends(get_session)):
    """
    Check if the user has been matched with another player.
    """
    # Check if the user is in a pending or active match
    match = (
        db.query(Match)
        .filter(
            ((Match.player1_id == user_id) | (Match.player2_id == user_id))
            & (
                (Match.status == MatchStatus.PENDING)
                | (Match.status == MatchStatus.ACTIVE)
            )
        )
        .first()
    )

    if match:
        return {
            "in_match": True,
            "match_id": match.id,
            "status": match.status,
            "opponent_id": (
                match.player2_id if match.player1_id == user_id else match.player1_id
            ),
        }

    return {"in_match": False, "message": "Still in queue or not in queue"}


@router.get("/active", response_model=List[MatchResponse])
async def get_active_matches(user_id: int, db: Session = Depends(get_session)):
    matches = (
        db.query(Match)
        .filter(
            ((Match.player1_id == user_id) | (Match.player2_id == user_id))
            & (Match.status == "active")
        )
        .all()
    )

    return matches


@router.post("/accept/{match_id}")
async def accept_match(match_id: int, user_id: int, db: Session = Depends(get_session)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if match.player2_id != user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to accept this match"
        )

    # Check if the match has timed out (15 seconds)
    now = datetime.utcnow()
    timeout_threshold = match.start_time + timedelta(seconds=15)

    if now > timeout_threshold:
        match.status = MatchStatus.DECLINED
        match.end_time = now
        db.commit()
        raise HTTPException(
            status_code=400, detail="Match has timed out and was automatically declined"
        )

    match.status = MatchStatus.ACTIVE
    db.commit()
    db.refresh(match)

    return {"message": "Match accepted"}


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """
    WebSocket endpoint for real-time match notifications.
    Clients can connect to this endpoint to receive real-time updates about their matches.
    """
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Wait for messages from the client (can be used for ping/pong)
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
