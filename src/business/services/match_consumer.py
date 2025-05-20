import asyncio
import logging
import sys

from src.business.services.match import MatchService
from src.data.repositories.database import get_session

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
    """
    logger.info("Starting match queue consumer")
    match_service = MatchService()
    while True:
        try:
            async for db in get_session():
                logger.info("Processing match queue...")
                matches = await match_service.process_match_queue(
                    db,
                    match_service.match_acceptance_timeout,
                    match_service.match_draw_timeout,
                )
                logger.info(f"Matches created in this cycle: {len(matches)}")
                for m in matches:
                    logger.info(
                        f"Match debug: id={m.id}, problem_id={m.problem_id}, "
                        f"player1_id={m.player1_id}, player2_id={m.player2_id}"
                    )
                    if not m.id or not m.problem_id:
                        logger.warning(
                            f"Match with missing id/problem_id: id={m.id}, problem_id={m.problem_id}"
                        )
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in match queue consumer: {str(e)}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_consumer())
