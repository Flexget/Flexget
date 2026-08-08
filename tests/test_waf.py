from flexget.utils.waf import is_waf_challenge


class FakeResponse:
    def __init__(self, status_code, text='', headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


def test_is_waf_challenge_status_202():
    assert is_waf_challenge(FakeResponse(202))


def test_is_waf_challenge_header():
    assert is_waf_challenge(FakeResponse(200, headers={'x-amzn-waf-action': 'challenge'}))


def test_is_waf_challenge_goku_props():
    assert is_waf_challenge(FakeResponse(200, text='window.gokuProps = {}'))


def test_is_not_waf_challenge():
    assert not is_waf_challenge(FakeResponse(200, text='<html>normal page</html>'))
