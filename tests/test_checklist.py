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
        FieldUpdate(field=FieldName.LOCATION, status=FieldStatus.CONFIRMED, value="Laureles")
    )
    assert checklist.fields[FieldName.LOCATION].status == FieldStatus.CONFIRMED
    assert FieldName.LOCATION not in [f.field for f in checklist.open_fields()]


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
