from fr_agent.domain.validation import (
    FieldName,
    FieldStatus,
    FieldUpdate,
    ValidationChecklist,
)


def test_starts_with_all_fields_pending():
    checklist = ValidationChecklist()
    assert not checklist.is_complete()
    assert len(checklist.open_fields()) == len(FieldName)


def test_confirmed_update_closes_field():
    checklist = ValidationChecklist()
    checklist.apply(
        FieldUpdate(field=FieldName.NEIGHBORHOOD, status=FieldStatus.CONFIRMED, value="Laureles")
    )
    assert checklist.fields[FieldName.NEIGHBORHOOD].status == FieldStatus.CONFIRMED
    assert FieldName.NEIGHBORHOOD not in [f.field for f in checklist.open_fields()]


def test_seeded_from_confirms_only_the_fields_the_listing_has():
    checklist = ValidationChecklist.seeded_from(
        {FieldName.NEIGHBORHOOD: "Laureles", FieldName.CITY: "Medellín"}
    )
    assert checklist.fields[FieldName.NEIGHBORHOOD].status == FieldStatus.CONFIRMED
    assert checklist.fields[FieldName.CITY].status == FieldStatus.CONFIRMED
    # Not in the listing -> still open, still gets asked.
    assert checklist.fields[FieldName.ADDRESS].status == FieldStatus.PENDING
    assert checklist.fields[FieldName.LEGAL_STATUS].status == FieldStatus.PENDING


def test_restating_a_seeded_value_with_a_typo_is_not_a_conflict():
    checklist = ValidationChecklist.seeded_from({FieldName.NEIGHBORHOOD: "Laureles"})
    checklist.apply(
        FieldUpdate(field=FieldName.NEIGHBORHOOD, status=FieldStatus.CONFIRMED, value="laurles")
    )
    assert checklist.fields[FieldName.NEIGHBORHOOD].status == FieldStatus.CONFIRMED


def test_a_genuinely_different_value_still_conflicts():
    checklist = ValidationChecklist.seeded_from({FieldName.NEIGHBORHOOD: "Belén"})
    checklist.apply(
        FieldUpdate(
            field=FieldName.NEIGHBORHOOD, status=FieldStatus.CONFIRMED, value="Belén La Mota"
        )
    )
    assert checklist.fields[FieldName.NEIGHBORHOOD].status == FieldStatus.CONFLICTING


def test_contradicting_a_confirmed_field_flags_conflict():
    checklist = ValidationChecklist()
    checklist.apply(
        FieldUpdate(field=FieldName.MIN_PRICE, status=FieldStatus.CONFIRMED, value="300M")
    )
    checklist.apply(
        FieldUpdate(field=FieldName.MIN_PRICE, status=FieldStatus.CONFIRMED, value="350M")
    )
    assert checklist.fields[FieldName.MIN_PRICE].status == FieldStatus.CONFLICTING


def test_complete_when_all_confirmed():
    checklist = ValidationChecklist()
    for name in FieldName:
        checklist.apply(FieldUpdate(field=name, status=FieldStatus.CONFIRMED, value="ok"))
    assert checklist.is_complete()
