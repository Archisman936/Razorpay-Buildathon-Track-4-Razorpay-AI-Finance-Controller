"""Import graph smoke tests — fail on circular imports."""


def test_import_backend_modules():
    import backend.app.core.config  # noqa: F401
    import backend.app.database.connection  # noqa: F401
    import backend.app.ml.model_loader  # noqa: F401
    import backend.app.ml.reconciliation_model  # noqa: F401
    import backend.app.ml.exception_classifier  # noqa: F401
    import backend.app.services.reconciliation.deterministic  # noqa: F401
    import backend.app.services.reconciliation.feature_builder  # noqa: F401
    import backend.app.services.reconciliation.ml_reconciliation  # noqa: F401
    import backend.app.services.reconciliation.exception_classification  # noqa: F401
    import backend.app.services.reconciliation.reconciliation_service  # noqa: F401
    import backend.app.services.orchestration.pipeline  # noqa: F401
    import backend.app.main  # noqa: F401
    from backend.app.services.normalization.pipeline import NormalizationPipeline

    assert NormalizationPipeline is not None
