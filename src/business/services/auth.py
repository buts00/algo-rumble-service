from fastapi import Depends
from pydantic import UUID4
from sqlmodel import select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from src.business.services.auth_util import generate_password_hash
from src.data.repositories import get_session
from src.data.schemas import User, UserCreateModel


class UserService:
    @staticmethod
    async def get_user_by_id(user_id: UUID4, session: AsyncSession) -> User | None:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_username(username: str, session: AsyncSession) -> User | None:
        result = await session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(user_data: UserCreateModel, session: AsyncSession) -> User:
        user_data_dict = user_data.model_dump()
        password = user_data_dict.pop("password")

        new_user = User(
            **user_data_dict,
            password_hash=generate_password_hash(password),
            rating=1000,
        )

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        return new_user

    @staticmethod
    async def update_refresh_token(
        user_id: UUID4, refresh_token: str, session: AsyncSession
    ) -> None:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(refresh_token=refresh_token)
            .execution_options(synchronize_session="fetch")
        )
        await session.execute(stmt)
        await session.commit()

def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService()