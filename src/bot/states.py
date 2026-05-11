from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise


class State(StrEnum):
    """Finite, persisted user-session states for the Telegram bot."""

    IDLE = "IDLE"
    STATUS_WAIT_CODE = "STATUS_WAIT_CODE"
    CREATE_PROVIDER = "CREATE_PROVIDER"
    CREATE_PLAN = "CREATE_PLAN"
    CREATE_LOCATION = "CREATE_LOCATION"
    CREATE_NAME = "CREATE_NAME"
    CREATE_OS = "CREATE_OS"
    CREATE_CONFIRM = "CREATE_CONFIRM"


CREATE_FLOW: tuple[State, ...] = (
    State.CREATE_PROVIDER,
    State.CREATE_PLAN,
    State.CREATE_LOCATION,
    State.CREATE_NAME,
    State.CREATE_OS,
    State.CREATE_CONFIRM,
)

_CREATE_FLOW_INDEX = {state: index for index, state in enumerate(CREATE_FLOW)}


@dataclass(frozen=True, slots=True)
class Transition:
    """Allowed state movement inside a finite-state workflow."""

    from_state: State
    to_state: State


_ALLOWED: frozenset[Transition] = frozenset(
    {
        Transition(State.IDLE, State.STATUS_WAIT_CODE),
        Transition(State.IDLE, State.CREATE_PROVIDER),
        Transition(State.STATUS_WAIT_CODE, State.IDLE),
        *(Transition(current, next_) for current, next_ in pairwise(CREATE_FLOW)),
        *(Transition(next_, current) for current, next_ in pairwise(CREATE_FLOW)),
        *(Transition(state, State.IDLE) for state in State if state is not State.IDLE),
    }
)


def can_transition(from_state: State, to_state: State) -> bool:
    """Return True when the requested state transition is valid."""
    return Transition(from_state, to_state) in _ALLOWED


def previous_state(state: State) -> State:
    """Return the previous create-flow state, or IDLE outside the wizard."""
    index = _CREATE_FLOW_INDEX.get(state)
    if index is None or index == 0:
        return State.IDLE
    return CREATE_FLOW[index - 1]


def next_state(state: State) -> State:
    """Return the next create-flow state, or IDLE at the end/outside the wizard."""
    index = _CREATE_FLOW_INDEX.get(state)
    if index is None or index == len(CREATE_FLOW) - 1:
        return State.IDLE
    return CREATE_FLOW[index + 1]


def is_create_state(state: State) -> bool:
    """Return True when the state belongs to the VM creation wizard."""
    return state in _CREATE_FLOW_INDEX


def all_states() -> Iterable[State]:
    """Return every persisted session state."""
    return tuple(State)
