from app.pipeline.deglue import deglue, split_glued_run


def test_split_glued_run():
    run = "restartyourdevice"
    split = split_glued_run(run)
    assert "restart" in split
    assert "device" in split


def test_deglue_punct_and_run():
    text = "reasons.restart your device and clear storage."
    res = deglue(text)
    assert "reasons. restart" in res
