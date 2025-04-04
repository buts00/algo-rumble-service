from pydantic import EmailStr

from .model import User
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from .schema import UserCreateModel, UserRole
from .util import generate_password_hash


class UserService:
    @staticmethod
    async def get_user_by_email(email: EmailStr, session: AsyncSession):
        statement = select(User).where(User.email == email)
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def user_exists(self, email: EmailStr, session: AsyncSession):
        return await self.get_user_by_email(email, session) is not None

    @staticmethod
    async def create_user(user_data: UserCreateModel, session: AsyncSession):
        user_data_dict = user_data.model_dump()
        password = user_data_dict.pop("password")

        new_user = User(
            **user_data_dict,
            password_hash=generate_password_hash(password),
            role=UserRole.USER,
            rating=0.0
        )

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        return new_user
