"""ValidationSession: the aggregate root persisted by the repository.

One session = one property + one seller conversation + one checklist.
Everything the orchestrator needs to make a decision lives here.
"""

from uuid import uuid4

from pydantic import BaseModel, Field

from fr_agent.domain.conversation import Conversation
from fr_agent.domain.property import Property
from fr_agent.domain.validation import ValidationChecklist


class ValidationSession(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    property: Property
    conversation: Conversation = Field(default_factory=Conversation)
    checklist: ValidationChecklist = Field(default_factory=ValidationChecklist)

    @property
    def seller_phone(self) -> str:
        return self.property.seller.phone
