from aiogram.fsm.state import State, StatesGroup

class Verification(StatesGroup):
    waiting_email = State()
    waiting_confirm = State()
    waiting_code = State()
    verified = State()
    blocked = State()