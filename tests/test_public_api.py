def test_public_client_export():
    from schoolapp import SchoolAppClient

    assert SchoolAppClient is not None


def test_version_still_exposed():
    import schoolapp

    assert isinstance(schoolapp.__version__, str)


def test_models_module_accessible():
    from schoolapp import models

    assert hasattr(models, "ElementGrade")
