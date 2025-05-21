from datetime import datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext
from pydantic import UUID4

from src.config import Config

passwd_context = CryptContext(schemes=["bcrypt"])


def generate_password_hash(password: str) -> str:
    return passwd_context.hash(password)


# Alias for generate_password_hash to maintain compatibility with tests
get_password_hash = generate_password_hash


def verify_password(password: str, password_hash: str) -> bool:
    return passwd_context.verify(password, password_hash)


def create_access_token(
    user_data: dict, expiry: timedelta = timedelta(Config.JWT_ACCESS_TOKEN_EXPIRY)
):
    payload = {
        "user": user_data,
        "exp": datetime.now() + expiry,
        "jti": str(UUID4()),
        "is_refresh": False,
    }

    token = jwt.encode(
        payload=payload, key=Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM
    )

    return token


def create_refresh_token(
    user_data: dict, expiry: timedelta = timedelta(Config.JWT_REFRESH_TOKEN_EXPIRY)
):
    payload = {
        "user": user_data,
        "exp": datetime.now() + expiry,
        "jti": str(UUID4()),
        "is_refresh": True,
    }

    return encode_token(payload)


def encode_token(payload):
    return jwt.encode(
        payload=payload, key=Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM
    )


def decode_token(token: str) -> Any | None:
    try:
        token_data = jwt.decode(
            jwt=token, key=Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM]
        )
        return token_data

    except jwt.PyJWTError as _:
        return None
