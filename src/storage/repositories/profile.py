from typing import List
from datetime import datetime
from collections import Counter
from pydantic import UUID4
from sqlalchemy import select, extract, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import logger
from src.errors import DatabaseException, BadRequestException
from src.handler.schemas import (
    MatchHistoryEntry,
    ContributionCalendar,
    ContributionCalendarEntry,
    RatingHistory,
    RatingHistoryEntry,
    TopicStats,
    TopicStatEntry,
)
from src.storage.models import Match, MatchStatus, User, Problem

profile_logger = logger.getChild("profile")


async def get_user_match_history(
    db: AsyncSession, user_id: UUID4, limit: int = 10, offset: int = 0
) -> tuple[List[MatchHistoryEntry], int]:
    """
    Get match history for a specific user.

    Args:
        db: Database session
        user_id: ID of the user to get match history for
        limit: Maximum number of matches to return
        offset: Number of matches to skip

    Returns:
        Tuple containing:
        - List of match history entries
        - Total number of matches for the user
    """
    try:
        # Get the total count of matches for the user
        total_count_result = await db.execute(
            select(Match).where(
                ((Match.player1_id == user_id) | (Match.player2_id == user_id)),
                Match.status == MatchStatus.COMPLETED,
                Match.winner_id.isnot(None),
            )
        )
        total_count = len(total_count_result.scalars().all())

        # Get completed matches for the user with pagination
        result = await db.execute(
            select(Match)
            .where(
                ((Match.player1_id == user_id) | (Match.player2_id == user_id)),
                Match.status == MatchStatus.COMPLETED,
                Match.winner_id.isnot(None),
            )
            .order_by(Match.end_time.desc())
            .offset(offset)
            .limit(limit)
        )
        matches = result.scalars().all()

        # Convert matches to match history entries
        match_history = []
        for match in matches:
            # Determine if the user won or lost
            is_winner = match.winner_id == user_id
            status = "win" if is_winner else "loss"

            # Get the enemy user ID
            enemy_id = (
                match.player2_id if match.player1_id == user_id else match.player1_id
            )

            # Get the enemy user
            enemy_result = await db.execute(select(User).where(User.id == enemy_id))
            enemy = enemy_result.scalar_one_or_none()

            if not enemy:
                profile_logger.warning(f"Enemy user not found: ID {enemy_id}")
                continue

            # Create match history entry
            # Get the user's old and new ratings from the match
            if match.player1_id == user_id:
                old_rating = match.player1_old_rating or enemy.rating
                new_rating = match.player1_new_rating or enemy.rating
            else:
                old_rating = match.player2_old_rating or enemy.rating
                new_rating = match.player2_new_rating or enemy.rating

            match_history.append(
                MatchHistoryEntry(
                    enemy_name=enemy.username,
                    status=status,
                    old_rating=old_rating,
                    new_rating=new_rating,
                    finished_at=match.end_time,
                )
            )

        return match_history, total_count
    except Exception as e:
        profile_logger.error(
            f"Error retrieving match history for user {user_id}: {str(e)}"
        )
        raise DatabaseException(
            detail="Failed to retrieve match history due to database error"
        )


async def get_user_contribution_calendar(
    db: AsyncSession, user_id: UUID4, year: int
) -> ContributionCalendar:
    """
    Get contribution calendar storage for a specific user for a given year.

    Args:
        db: Database session
        user_id: ID of the user to get contribution calendar for
        year: Year to get contribution calendar for

    Returns:
        Contribution calendar storage
    """
    try:
        # Validate year
        current_year = datetime.now().year
        if year < 2020 or year > current_year:
            raise BadRequestException(
                detail=f"Year must be between 2020 and {current_year}"
            )

        # Get all matches for the user in the specified year
        result = await db.execute(
            select(
                Match,
                extract("day", Match.start_time).label("day"),
                extract("month", Match.start_time).label("month"),
            ).where(
                ((Match.player1_id == user_id) | (Match.player2_id == user_id)),
                extract("year", Match.start_time) == year,
            )
        )
        matches = result.all()

        entries = []
        for match, day, month in matches:
            # Create datetime object for the date
            date_obj = datetime(year, int(month), int(day))

            # Check if we already have an entry for this date
            existing_entry = next(
                (e for e in entries if e.date.date() == date_obj.date()), None
            )
            if existing_entry:
                existing_entry.count += 1
            else:
                entries.append(ContributionCalendarEntry(date=date_obj, count=1))

        return ContributionCalendar(entries=entries)
    except BadRequestException as e:
        raise e
    except Exception as e:
        profile_logger.error(
            f"Error retrieving contribution calendar for user {user_id} for year {year}: {str(e)}"
        )
        raise DatabaseException(
            detail="Failed to retrieve contribution calendar due to database error"
        )


async def get_user_rating_history(db: AsyncSession, user_id: UUID4) -> RatingHistory:
    """
    Get rating history for a specific user, sorted from oldest to newest.

    Args:
        db: Database session
        user_id: ID of the user to get rating history for

    Returns:
        Rating history storage
    """
    try:
        # Get completed matches for the user
        result = await db.execute(
            select(Match)
            .where(
                or_(Match.player1_id == user_id, Match.player2_id == user_id),
                Match.status == MatchStatus.COMPLETED,
                Match.winner_id.isnot(None),
            )
            .order_by(Match.end_time.asc())  # Sort from oldest to newest
        )
        matches = result.scalars().all()

        # Get the user's initial rating
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        if not user:
            profile_logger.warning(f"User not found: ID {user_id}")
            raise BadRequestException(detail="User not found")

        # Create rating history entries
        history_entries = [RatingHistoryEntry(date=user.created_at, rating=1000)]

        # Process each match to extract rating changes
        for match in matches:
            # Get the user's new rating from the match
            if match.player1_id == user_id:
                new_rating = match.player1_new_rating
            else:
                new_rating = match.player2_new_rating

            # Only add entry if new_rating is not None
            if new_rating is not None:
                history_entries.append(
                    RatingHistoryEntry(date=match.end_time, rating=new_rating)
                )

        return RatingHistory(history=history_entries)
    except BadRequestException as e:
        raise e
    except Exception as e:
        profile_logger.error(
            f"Error retrieving rating history for user {user_id}: {str(e)}"
        )
        raise DatabaseException(
            detail="Failed to retrieve rating history due to database error"
        )


async def get_user_topic_stats(
    db: AsyncSession, user_id: UUID4, limit: int = 5
) -> TopicStats:
    """
    Get statistics about the top topics where the user has won matches.

    Args:
        db: Database session
        user_id: ID of the user to get topic statistics for
        limit: Maximum number of topics to return (default: 5)

    Returns:
        Topic statistics storage
    """
    try:
        profile_logger.info(f"Getting topic statistics for user {user_id}")

        # Get completed matches where the user is the winner
        result = await db.execute(
            select(Match).where(
                Match.winner_id == user_id,
                Match.status == MatchStatus.COMPLETED,
                Match.problem_id.isnot(None),
            )
        )
        matches = result.scalars().all()

        if not matches:
            profile_logger.info(f"No won matches found for user {user_id}")
            return TopicStats(topics=[])

        # Get the problems associated with those matches
        problem_ids = [match.problem_id for match in matches if match.problem_id]

        # Create a dictionary to store topic counts
        topic_counts = Counter()

        # Process each problem to extract topics
        for problem_id in problem_ids:
            problem_result = await db.execute(
                select(Problem).where(Problem.id == problem_id)
            )
            problem = problem_result.scalar_one_or_none()

            if problem and problem.topics:
                # Increment the count for each topic in this problem
                for topic in problem.topics:
                    topic_counts[topic] += 1

        # Get the top N topics
        top_topics = topic_counts.most_common(limit)

        # Create topic stat entries
        topic_stats = [
            TopicStatEntry(topic=topic, win_count=count) for topic, count in top_topics
        ]

        profile_logger.info(
            f"Retrieved {len(topic_stats)} topic statistics for user {user_id}"
        )

        return TopicStats(topics=topic_stats)
    except Exception as e:
        profile_logger.error(
            f"Error retrieving topic statistics for user {user_id}: {str(e)}"
        )
        raise DatabaseException(
            detail="Failed to retrieve topic statistics due to database error"
        )
