from bot.states import State, can_transition, previous_state


def test_transition_cancel_allowed() -> None:
    assert can_transition(State.CREATE_PLAN, State.IDLE)


def test_transition_back_allowed() -> None:
    assert can_transition(State.CREATE_LOCATION, State.CREATE_PLAN)


def test_previous_state() -> None:
    assert previous_state(State.CREATE_NAME) == State.CREATE_LOCATION
