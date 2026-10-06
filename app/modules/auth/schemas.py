from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Password = Annotated[str, Field(min_length=12, max_length=72)]
Token = Annotated[str, Field(min_length=32, max_length=128)]


def validate_password(value):
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Senha excede 72 bytes UTF-8")
    return value


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailInput(Input):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class RegisterInput(EmailInput):
    name: str = Field(min_length=1, max_length=120)
    password: Password
    accepted_terms: Literal[True]
    privacy_policy_version: str = Field(min_length=1, max_length=40)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    _password = field_validator("password")(validate_password)


class VerifyInput(Input):
    registration_token: Token
    code: str = Field(pattern=r"^[0-9]{6}$")
    password: str = Field(min_length=1, max_length=72)
    _password = field_validator("password")(validate_password)


class ResendInput(Input):
    registration_token: Token


class LoginInput(EmailInput):
    password: str = Field(min_length=1, max_length=72)
    _password = field_validator("password")(validate_password)


class RefreshInput(Input):
    refresh_token: Token


class ResetInput(Input):
    reset_token: Token
    new_password: Password
    _password = field_validator("new_password")(validate_password)


class DeleteInput(Input):
    password: str = Field(min_length=1, max_length=72)
    _password = field_validator("password")(validate_password)


class UserOutput(BaseModel):
    id: str
    name: str
    email: EmailStr
    email_verified: bool


class SessionOutput(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOutput


class ChallengeOutput(BaseModel):
    registration_token: str
    expires_in: int
    resend_after: int
