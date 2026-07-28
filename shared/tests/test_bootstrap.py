def test_bootstrap_importable():
    from autotools_shared.bootstrap import create_app
    assert callable(create_app)
