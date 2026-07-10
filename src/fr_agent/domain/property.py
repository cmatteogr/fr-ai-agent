"""Property and seller entities.

These carry the information we already have *before* the conversation starts
(e.g. scraped from a listing). The conversation's job is to validate and
complete it — the validated facts live in the ValidationChecklist, not here.
"""

from pydantic import BaseModel, Field


class Seller(BaseModel):
    name: str = ""
    phone: str = Field(description="E.164 phone number, e.g. +573001234567")


class Property(BaseModel):
    id: str
    seller: Seller
    # Whatever we already know about the listing, keyed by free-form labels
    # (e.g. "listed_price", "address", "source_url"). Used to seed the
    # conversation with context, never treated as validated truth.
    known_facts: dict[str, str] = Field(default_factory=dict)
