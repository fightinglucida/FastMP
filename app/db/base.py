from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models here so that Alembic or metadata.create_all can discover them
try:
    # enforce import order via models.__init__
    from app.models import Category, Account, ActivationCode, Cookie, MpAccount, MpArticle  # noqa: F401
except Exception:
    # During certain tooling, model import may fail; ignore to avoid import-time errors
    pass
