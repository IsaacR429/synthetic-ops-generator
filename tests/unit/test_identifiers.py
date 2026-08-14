from synthetic_ops_generator.core.identifiers import IdFactory


def test_change_ids_are_unique() -> None:
    factory = IdFactory()

    first = factory.change_id()
    second = factory.change_id()

    assert first == "CHG0000001"
    assert second == "CHG0000002"
    assert first != second


def test_log_ids_are_generated_centrally() -> None:
    ids = IdFactory()

    assert ids.log_id() == "LOG0000001"
    assert ids.log_id() == "LOG0000002"


def test_history_ids_are_sequential() -> None:
    ids = IdFactory()

    assert ids.history_id() == "HST0000001"
    assert ids.history_id() == "HST0000002"

