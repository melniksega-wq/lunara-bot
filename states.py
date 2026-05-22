from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    name = State()
    date = State()
    time = State()
    place = State()


class Partner(StatesGroup):
    name = State()
    date = State()


class Ask(StatesGroup):
    waiting = State()


class AdminBroadcast(StatesGroup):
    waiting = State()
