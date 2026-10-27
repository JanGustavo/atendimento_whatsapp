from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(user_id: int, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": expire}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> tuple[int, str] | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id, role = payload.get("sub"), payload.get("role")
        if not isinstance(user_id, str) or not user_id.isdecimal() or role not in {"vendedor", "responsavel", "gestor"}:
            return None
        return int(user_id), role
    except JWTError:
        return None
