from enum import Enum


class RoleEnum(str, Enum):
    STUDENT = "STUDENT"
    LECTURER = "LECTURER"
    ADMIN = "ADMIN"


class AuthMethodEnum(str, Enum):
    PASSWORD = "PASSWORD"
    FACE = "FACE"
    WEBAUTHN = "WEBAUTHN"