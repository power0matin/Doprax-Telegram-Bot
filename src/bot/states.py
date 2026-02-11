from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class State(str, Enum):
    """Finite states persisted per user."""

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


@dataclass(frozen=True)
class Transition:
    from_state: State
    to_state: State


_ALLOWED: set[Transition] = set()

# Idle entry points
_ALLOWED.add(Transition(State.IDLE, State.STATUS_WAIT_CODE))
_ALLOWED.add(Transition(State.IDLE, State.CREATE_PROVIDER))

# Status -> Idle
_ALLOWED.add(Transition(State.STATUS_WAIT_CODE, State.IDLE))

# Create wizard linear
for a, b in zip(CREATE_FLOW, CREATE_FLOW[1:], strict=True):
    _ALLOWED.add(Transition(a, b))

# Back transitions in wizard
for a, b in zip(CREATE_FLOW[1:], CREATE_FLOW[:-1], strict=True):
    _ALLOWED.add(Transition(a, b))

# Cancel/reset from anywhere
for s in State:
    if s != State.IDLE:
        _ALLOWED.add(Transition(s, State.IDLE))


def can_transition(from_state: State, to_state: State) -> bool:
    """Check transition validity."""
    return Transition(from_state, to_state) in _ALLOWED


def previous_state(state: State) -> State:
    """Get previous state in create wizard (or IDLE fallback)."""
    if state in CREATE_FLOW:
        idx = CREATE_FLOW.index(state)
        return CREATE_FLOW[idx - 1] if idx > 0 else State.IDLE
    return State.IDLE


def next_state(state: State) -> State:
    """Get next state in create wizard (or IDLE fallback)."""
    if state in CREATE_FLOW:
        idx = CREATE_FLOW.index(state)
        return CREATE_FLOW[idx + 1] if idx < len(CREATE_FLOW) - 1 else State.IDLE
    return State.IDLE


def is_create_state(state: State) -> bool:
    """Return True if state is within create flow."""
    return state in CREATE_FLOW


def all_states() -> Iterable[State]:
    """Return all states."""
    return list(State)
