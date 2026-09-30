"""Property and seller entities.

These carry the information we already have *before* the conversation starts
(from the listing database). The agent's job is to extract whatever the
listing DIDN'T give us — the fields below are the ones a listing can
actually supply and are trusted as already-confirmed (see
ValidationChecklist.seeded_from). Anything a listing never has (legal_status,
occupancy, motivation, min_price, ...) is left for the conversation to ask.
"""

from pydantic import BaseModel, Field

from fr_agent.domain.validation import FieldName


class Seller(BaseModel):
    name: str = ""
    phone: str = Field(description="E.164 phone number, e.g. +573001234567")


class Property(BaseModel):
    id: str
    seller: Seller
    # Structured, per-listing: present when the listing/database has it,
    # None when it doesn't (that specific field still gets asked). These
    # three are named because almost every listing has them; maps 1:1 to
    # FieldName.ADDRESS / NEIGHBORHOOD / CITY.
    address: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    # Any OTHER checklist field this specific listing happens to supply
    # (e.g. a pre-construction listing stating legal_status="Sobre planos",
    # or renovations="A estrenar"). Deliberately NOT auto-derived from raw
    # listing data (e.g. asking price != seller's min_price) — whoever loads
    # a real listing decides, field by field, which values are trustworthy
    # enough to seed as CONFIRMED here.
    extra_known_fields: dict[FieldName, str] = Field(default_factory=dict)
    # Anything else worth mentioning in the opener (listed price, url,
    # description...) that does NOT map to a checklist field and is never
    # treated as confirmed truth.
    known_facts: dict[str, str] = Field(default_factory=dict)

    def known_checklist_fields(self) -> dict[FieldName, str]:
        """Everything this listing supplies that maps onto a checklist
        field — the input to ValidationChecklist.seeded_from()."""
        base = {
            FieldName.ADDRESS: self.address,
            FieldName.NEIGHBORHOOD: self.neighborhood,
            FieldName.CITY: self.city,
        }
        return {**base, **self.extra_known_fields}
