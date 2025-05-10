import asyncio
import logging
import sys

from src.db.main import get_session
from src.match.service import process_match_queue

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
            # Get a database session
            db = next(get_session())

            # Process the match queue
            await process_match_queue(db)

            # Sleep for a short time before processing again
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error in match queue consumer: {str(e)}")
            await asyncio.sleep(5)  # Sleep longer on error


if __name__ == "__main__":
    # Run the consumer
    asyncio.run(run_consumer())
