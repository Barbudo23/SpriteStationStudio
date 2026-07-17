def test_import():
    import assetforge


def test_runner_is_available():
    from assetforge.runner import main

    assert callable(main)
