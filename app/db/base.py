from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models here so that Alembic or metadata.create_all can discover them
try:
    from app.models.account import Account  # noqa: F401
    from app.models.activation_code import ActivationCode  # noqa: F401
    from app.models.cookie import Cookie  # noqa: F401
except Exception:
    # During certain tooling, model import may fail; ignore to avoid import-time errors
    pass
