from fr_agent.domain.validation import (
    NUMERIC_FIELDS,
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
        FieldUpdate(field=FieldName.MOTIVATION, status=FieldStatus.CONFIRMED, value="Divorcio")
    )
    checklist.apply(
        FieldUpdate(field=FieldName.MOTIVATION, status=FieldStatus.CONFIRMED, value="Herencia")
    )
    assert checklist.fields[FieldName.MOTIVATION].status == FieldStatus.CONFLICTING


def test_complete_when_all_confirmed():
    checklist = ValidationChecklist()
    for name in FieldName:
        if name in NUMERIC_FIELDS:
            update = FieldUpdate(field=name, status=FieldStatus.CONFIRMED, number=1)
        elif name == FieldName.ADDRESS:
            update = FieldUpdate(field=name, status=FieldStatus.CONFIRMED, value="Calle 1 #2-3")
        elif name == FieldName.CITY:
            update = FieldUpdate(field=name, status=FieldStatus.CONFIRMED, value="Medellín")
        else:
            update = FieldUpdate(field=name, status=FieldStatus.CONFIRMED, value="ok")
        checklist.apply(update)
    assert checklist.is_complete()


def test_a_different_min_price_conflicts():
    checklist = ValidationChecklist()
    checklist.apply(FieldUpdate(field=FieldName.MIN_PRICE, status=FieldStatus.CONFIRMED, number=350000000))
    checklist.apply(FieldUpdate(field=FieldName.MIN_PRICE, status=FieldStatus.CONFIRMED, number=300000000))
    assert checklist.fields[FieldName.MIN_PRICE].status == FieldStatus.CONFLICTING
    assert checklist.fields[FieldName.MIN_PRICE].number == 300000000


def test_min_price_never_stores_text():
    checklist = ValidationChecklist()
    checklist.apply(
        FieldUpdate(field=FieldName.MIN_PRICE, status=FieldStatus.PARTIAL, value="no ha pensado en un número")
    )
    assert checklist.fields[FieldName.MIN_PRICE].status == FieldStatus.PENDING
    assert checklist.fields[FieldName.MIN_PRICE].value == ""


def test_address_without_a_number_is_rejected():
    checklist = ValidationChecklist()
    checklist.apply(FieldUpdate(field=FieldName.ADDRESS, status=FieldStatus.CONFIRMED, value="laurles medellin"))
    assert checklist.fields[FieldName.ADDRESS].status == FieldStatus.PENDING


def test_address_with_letters_and_numbers_is_kept():
    checklist = ValidationChecklist()
    checklist.apply(FieldUpdate(field=FieldName.ADDRESS, status=FieldStatus.CONFIRMED, value="Calle 45B #12-30"))
    assert checklist.fields[FieldName.ADDRESS].status == FieldStatus.CONFIRMED


def test_free_text_written_in_selection_is_moved_to_value():
    checklist = ValidationChecklist.seeded_from({FieldName.NEIGHBORHOOD: "Belén"})
    checklist.apply(
        FieldUpdate(field=FieldName.NEIGHBORHOOD, status=FieldStatus.CONFIRMED, selection=["Belén La Mota"])
    )
    field = checklist.fields[FieldName.NEIGHBORHOOD]
    assert field.status == FieldStatus.CONFLICTING
    assert field.value == "Belén La Mota"


def test_city_cannot_be_the_barrio_name():
    checklist = ValidationChecklist.seeded_from({FieldName.NEIGHBORHOOD: "Belén La Mota"})
    checklist.apply(FieldUpdate(field=FieldName.CITY, status=FieldStatus.CONFIRMED, value="Belén"))
    assert checklist.fields[FieldName.CITY].status == FieldStatus.PENDING


def test_partial_answer_out_of_attempts_stays_partial_and_is_not_asked():
    checklist = ValidationChecklist()
    checklist.apply(FieldUpdate(field=FieldName.OCCUPANCY, status=FieldStatus.PARTIAL, selection=["Desocupada"]))
    field = checklist.fields[FieldName.OCCUPANCY]
    field.attempts = field.max_attempts
    open_names = [f.field for f in checklist.open_fields()]
    assert field.status == FieldStatus.PARTIAL
    assert FieldName.OCCUPANCY not in open_names


def test_skipped_with_a_real_option_becomes_partial():
    checklist = ValidationChecklist()
    checklist.apply(FieldUpdate(field=FieldName.OCCUPANCY, status=FieldStatus.SKIPPED, selection=["Desocupada"]))
    assert checklist.fields[FieldName.OCCUPANCY].status == FieldStatus.PARTIAL


def test_skipped_with_unknown_option_stays_skipped():
    checklist = ValidationChecklist()
    checklist.apply(FieldUpdate(field=FieldName.OCCUPANCY, status=FieldStatus.SKIPPED, selection=["Desconocida"]))
    assert checklist.fields[FieldName.OCCUPANCY].status == FieldStatus.SKIPPED


def test_option_written_in_value_is_still_recognized():
    checklist = ValidationChecklist()
    checklist.apply(FieldUpdate(field=FieldName.OCCUPANCY, status=FieldStatus.SKIPPED, value="Desocupada"))
    field = checklist.fields[FieldName.OCCUPANCY]
    assert field.status == FieldStatus.PARTIAL
    assert field.selection == ["Desocupada"]
