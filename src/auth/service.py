from random import randint

from pydantic import UUID4
from sqlmodel import select, update
from .model import User
from sqlmodel.ext.asyncio.session import AsyncSession
from .schemas import UserCreateModel, UserRole
from .util import generate_password_hash


class UserService:
    @staticmethod
    async def get_user_by_id(id: UUID4, session: AsyncSession):
        statement = select(User).where(User.id == id)
        result = await session.execute(statement)

        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_username(username: str, session: AsyncSession):
        statement = select(User).where(User.username == username)
        result = await session.execute(statement)

        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(user_data: UserCreateModel, session: AsyncSession):
        user_data_dict = user_data.model_dump()
        password = user_data_dict.pop("password")

        new_user = User(
            **user_data_dict,
            password_hash=generate_password_hash(password),
            role=UserRole.USER,
            rating=randint(0, 1000),
        )

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        return new_user

    @staticmethod
    async def update_refresh_token(
            user_id: UUID4, refresh_token: str, session: AsyncSession
    ):
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(refresh_token=refresh_token)
            .execution_options(synchronize_session="fetch")
        )

        result = await session.execute(stmt)
        await session.commit()

        return result
