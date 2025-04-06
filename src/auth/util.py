from datetime import timedelta, datetime
from typing import Any
from src.config import Config
from passlib.context import CryptContext
import jwt
import uuid

passwd_context = CryptContext(schemes=["bcrypt"])


def generate_password_hash(password: str) -> str:
    return passwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return passwd_context.verify(password, password_hash)


def create_access_token(
    user_data: dict, expiry: timedelta = timedelta(Config.JWT_ACCESS_TOKEN_EXPIRY)
):
    payload = {
        "user": user_data,
        "exp": datetime.now() + expiry,
        "jti": str(uuid.uuid4()),
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
        "jti": str(uuid.uuid4()),
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
