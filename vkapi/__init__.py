# Автоимпорт есть только у packages (например, у urllib __init__.py у которого
# пуст). Для обычных смертных все нужно вручную делать.
from . import defaults
from . import errors
from .auths import AuthDirect, AuthStandalone
from .client import Client, ClientError, ApiError
from .structures import AttrDict
