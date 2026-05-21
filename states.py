from aiogram.fsm.state import State, StatesGroup


class BirthForm(StatesGroup):
    name = State()
    birth_date = State()
    birth_time = State()
    birth_place = State()
    custom_question = State()


class CompatibilityForm(StatesGroup):
    partner_name = State()
    partner_birth_date = State()
