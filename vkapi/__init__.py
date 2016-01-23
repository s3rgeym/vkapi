# Автоимпорт есть только у packages (например, у urllib __init__.py которого
# пуст). Для обычных смертных все нужно вручную делать.

from . import errors
from . import structures
from .client import *
