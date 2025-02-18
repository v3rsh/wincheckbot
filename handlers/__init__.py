# handlers/__init__.py

from .start_handler import router as start_handler
from .manual_handler import router as manual_handler
from .general_handler import router as general_handler
# from .callback_handler import router as callback_handler
from .check_handler import router as check_handler
from .group_handler import router as group_handler
from .email_handler import router as email_handler
from .code_handler import router as code_handler
from .block_handler import router as block_handler
from .confirm_handler import router as confirm_handler
from .chat_handler import router as chat_handler


__all__ = [
    "manual_handler",
    "block_handler",
    "start_handler",
    "check_handler",
    # "callback_handler",
    "code_handler",
    "confirm_handler",
    "email_handler",
    "group_handler",
    "general_handler",
    "chat_handler",
]   
