# Ensure model import order for metadata.create_all (auto create tables)
# Categories -> Accounts -> MpAccount/MpArticle depend on others
from app.models.category import Category  # noqa: F401
from app.models.account import Account  # noqa: F401
from app.models.activation_code import ActivationCode  # noqa: F401
from app.models.cookie import Cookie  # noqa: F401
from app.models.mp_account import MpAccount  # noqa: F401
from app.models.mp_article import MpArticle  # noqa: F401
