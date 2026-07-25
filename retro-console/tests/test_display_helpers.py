from rwt_rconsole import FrameTickResult
from rwt_rconsole.display import should_present


def test_should_present():
    assert should_present(True) is True
    assert should_present(False) is False
    assert should_present(FrameTickResult.PRESENT) is True
    assert should_present(FrameTickResult.SKIP) is False
