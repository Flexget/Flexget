import hashlib
import time

import pytest

from flexget.utils.waf import is_waf_challenge, verify


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


# Reference vector produced by pyscrypt 1.6.2, which `hashlib.scrypt` replaced. This is the
# check that fails if the swap ever stops being bit-identical.
def test_scrypt_func_matches_reference_vector():
    assert (
        verify.scrypt_func('challengeinput123', 'saltysalt', 128)
        == '1896b519cc5906810cf9b33112ba13f5'
    )


def test_hash_pow_solves_low_difficulty():
    nonce = verify.hash_pow('abc', 'def', 8)
    digest = hashlib.sha256(f'abcdef{nonce}'.encode()).digest()
    assert verify._check(digest, 8)


@pytest.mark.parametrize('solver', [verify.hash_pow, verify.compute_scrypt_nonce])
def test_solvers_give_up_instead_of_hanging(solver, monkeypatch):
    """A server-supplied difficulty must never wedge the single-threaded task queue."""
    monkeypatch.setattr(verify, 'SOLVE_TIMEOUT', 0.1)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        solver('a', 'b', 64)  # unsatisfiable
    assert time.monotonic() - started < 30
