from datetime import timedelta, datetime
from src.config import Config
from passlib.context import CryptContext
import jwt
import uuid
import logging

JWT_ACCESS_TOKEN_EXPIRY = Config.JWT_ACCESS_TOKEN_EXPIRY

passwd_context = CryptContext(schemes=["bcrypt"])


def generate_password_hash(password: str) -> str:
    return passwd_context.hash(password)


def verify_password(password: str, hash: str) -> bool:
    return passwd_context.verify(password, hash)


def create_access_token(
    user_data: dict, expiry: timedelta = None, refresh: bool = False
):
    payload = {
        "user": user_data,
        "exp": datetime.now()
        + (
            expiry if expiry is not None else timedelta(seconds=JWT_ACCESS_TOKEN_EXPIRY)
        ),
        "jti": str(uuid.uuid4()),
        "refresh": refresh,
    }

    token = jwt.encode(
        payload=payload, key=Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM
    )

    return token


def decode_token(token: str) -> dict:
    try:
        token_data = jwt.decode(
            jwt=token, key=Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM]
        )
        return token_data

    except jwt.PyJWTError as e:
        logging.exception(e)
        return None
