from enum import Enum


class UserRole(str, Enum):
    """User roles in the system."""
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class MatchStatus(str, Enum):
    """Match statuses in the system."""
    CREATED = "created"
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"