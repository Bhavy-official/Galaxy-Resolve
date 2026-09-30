from app.pipeline.mismatch import is_mismatched_article


def test_mismatch_detected():
    query = "Camera app crashes when taking photos"
    article_title = "Washing Machine Error Codes"
    article_content = "To clean the lint filter, disconnect the drain hose. Wipe down the drum with a damp cloth."

    assert is_mismatched_article(query, article_content, article_title) is True


def test_mismatch_not_detected_for_relevant_article():
    query = "Camera app crashes when taking photos"
    article_title = "Camera Settings and App Troubleshooting"
    article_content = "Open Settings, tap Apps, tap Camera, then clear storage and cache."

    assert is_mismatched_article(query, article_content, article_title) is False
