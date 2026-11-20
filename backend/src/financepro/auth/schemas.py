from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
# Upper bound: Argon2 would happily hash a megabyte, and the hash is the expensive part of a sign-in.
NewPassword = Annotated[str, Field(min_length=10, max_length=128)]
Password = Annotated[str, Field(min_length=1, max_length=128)]


class SignupIn(BaseModel):
    name: Name
    email: EmailStr
    password: NewPassword

    @model_validator(mode="after")
    def password_is_not_the_email(self) -> Self:
        if self.password.strip().lower() == self.email.lower():
            raise ValueError("A senha não pode ser o seu e-mail.")
        return self


class LoginIn(BaseModel):
    email: EmailStr
    password: Password


class DeleteAccountIn(BaseModel):
    password: Password | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    is_sandbox: bool
