from sqlalchemy import Enum



class MatchStatus(str, Enum):
    """Match statuses in the system."""
    CREATED = "created"
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"