"""Conversation transcript and lifecycle state."""

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field

from fr_agent.domain.validation import FieldName


class Role(StrEnum):
    AGENT = "agent"    # us
    SELLER = "seller"  # them


class Message(BaseModel):
    role: Role
    text: str
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationState(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"        # checklist fully validated
    OPTED_OUT = "opted_out"        # seller asked to stop
    TURN_LIMIT = "turn_limit"      # budget exhausted before completion
    UNRESPONSIVE = "unresponsive"  # seller kept not addressing what was asked


class Conversation(BaseModel):
    messages: list[Message] = Field(default_factory=list)
    state: ConversationState = ConversationState.ACTIVE
    # Fields the agent's LAST message actually asked about — set right
    # after generating a reply, read on the NEXT inbound turn to check
    # whether the seller's answer addressed any of them.
    pending_fields: list[FieldName] = Field(default_factory=list)
    # Consecutive turns where the seller's reply didn't address any
    # pending_fields. Reset to 0 the moment a real answer lands.
    off_topic_streak: int = 0

    def add(self, role: Role, text: str) -> None:
        self.messages.append(Message(role=role, text=text))

    @property
    def agent_turns(self) -> int:
        return sum(1 for m in self.messages if m.role == Role.AGENT)

    def is_open(self) -> bool:
        return self.state == ConversationState.ACTIVE
