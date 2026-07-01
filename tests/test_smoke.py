def test_package_imports():
    import schoolapp

    assert hasattr(schoolapp, "__version__")
