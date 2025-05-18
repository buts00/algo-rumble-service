from .auth import auth_router
from .match import router as match_router
from .problem import problem_router, testcase_router
from .submission import submission_router

__all__ = ["auth_router", "match_router", "problem_router", "testcase_router", "submission_router"]
