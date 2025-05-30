from pydantic import BaseModel, Field, field_validator, UUID4


class UserBase(BaseModel):
    """Base schema for user storage."""

    username: str = Field(
        ...,
        max_length=50,
        min_length=3,
        examples=["algo_champ"],
        description="Unique username for the user.",
    )
    country_code: str = Field(
        ...,
        max_length=2,
        min_length=2,
        examples=["UA"],
        description="ISO 3166-1 alpha-2 country code.",
    )

    @classmethod
    @field_validator("country_code")
    def validate_country_code(cls, value: str) -> str:
        if not value.isalpha() or len(value) != 2:
            raise ValueError("Country code must be a 2-letter ISO code.")
        return value.upper()


class UserModel(UserBase):
    """Schema for user storage with additional fields."""

    id: UUID4
    rating: int = Field(default=1000, ge=0)

    model_config = {"from_attributes": True}


class UserCreateModel(UserBase):
    """Schema for creating a new user."""

    password: str = Field(
        ...,
        min_length=8,
        max_length=64,
        examples=["Str0ngP@ss!"],
        description="Password with at least 8 characters, including letters, numbers, and symbols.",
    )

    @classmethod
    @field_validator("password")
    def validate_password(cls, value: str) -> str:
        if not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError(
                "Password must contain at least one uppercase letter and one digit."
            )
        return value


class UserLoginModel(BaseModel):
    """Schema for user login."""

    username: str = Field(
        ...,
        max_length=50,
        min_length=3,
        examples=["algo_champ"],
        description="Username for login.",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=64,
        examples=["Str0ngP@ss!"],
        description="User password.",
    )


class UserBaseResponse(BaseModel):
    """Base schema for user response."""

    id: UUID4
    username: str

    model_config = {"from_attributes": True}


class UserResponseModel(UserBaseResponse):
    """Schema for detailed user response."""

    rating: int
    country_code: str

    model_config = {"from_attributes": True}
