"""Auth request and response bodies."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ..constants import UserRole
from ..security import MIN_PASSWORD_LENGTH


class LoginRequest(BaseModel):
    email: EmailStr
    # No max length beyond sanity, and no minimum: an existing password that
    # predates the policy must still be able to log in and then be changed.
    password: str = Field(min_length=1, max_length=1024)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: UserRole


class LoginResponse(BaseModel):
    user: UserOut


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    # The policy lives on the schema so it is enforced identically wherever a
    # password is set, and shows up in the OpenAPI document for the client.
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=1024)


__all__ = ["ChangePasswordRequest", "LoginRequest", "LoginResponse", "UserOut"]
