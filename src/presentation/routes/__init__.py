from .auth import auth_router
from .match import router as match_router
from .problem import problem_router, testcase_router
from .submission import submission_router
from .profile import router as profile_router
from .standing import router as standing_router

__all__ = [
    "auth_router",
    "match_router",
    "problem_router",
    "testcase_router",
    "submission_router",
    "profile_router",
    "standing_router",
]
