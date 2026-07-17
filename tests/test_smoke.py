def test_import():
    import assetforge


def test_runner_is_available():
    from assetforge.runner import main

    assert callable(main)


def test_success_message_uses_runtime_stack_revision():
    from assetforge.runner import success_message

    assert success_message("Stack_03_Rev00", "mock") == (
        "Stack_03_Rev00 completed successfully with provider: mock."
    )
