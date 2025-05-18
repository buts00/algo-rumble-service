import asyncio
import logging
import sys

from src.data.repositories.database import get_session
from src.business.services.match import process_match_queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


async def run_consumer():
    """
    Run the match queue consumer continuously.
    This should be run as a separate process or service.
    """
    logger.info("Starting match queue consumer")

    while True:
        try:
            # Use async context manager to get AsyncSession
            async for db in get_session():
                logger.info("Processing match queue...")
                matches = await process_match_queue(db)
                logger.info(f"Matches created in this cycle: {len(matches)}")
                # Debug: Warn if any match has None as match_id or problem_id
                for m in matches:
                    logger.info(
                        f"Match debug: id={getattr(m, 'id', None)}, "
                        f"problem_id={getattr(m, 'problem_id', None)}, "
                        f"player1_id={getattr(m, 'player1_id', None)}, "
                        f"player2_id={getattr(m, 'player2_id', None)}"
                    )
                    if not getattr(m, "id", None) or not getattr(m, "problem_id", None):
                        logger.warning(
                            f"Match with missing id/problem_id: {m} "
                            f"(id={getattr(m, 'id', None)}, problem_id={getattr(m, 'problem_id', None)})"
                        )
                break  # Only need one session per cycle

            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error in match queue consumer: {str(e)}")
            await asyncio.sleep(5)  # Sleep longer on error


if __name__ == "__main__":
    # Run the consumer
    asyncio.run(run_consumer())
