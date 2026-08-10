from synthetic_ops_generator.core.identifiers import IdFactory


def test_change_ids_are_unique() -> None:
    factory = IdFactory()

    first = factory.change_id()
    second = factory.change_id()

    assert first == "CHG0000001"
    assert second == "CHG0000002"
    assert first != second