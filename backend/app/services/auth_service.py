from sqlalchemy.orm import Session

from app.models.user import User
from app.services.auth_service import verify_password


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
