import hashlib
import binascii
from typing import Union, Callable, Any
import pyscrypt
import itertools

def _check(digest: bytes, difficulty: int) -> bool:
    full, rem = divmod(difficulty, 8)
    if digest[:full] != b"\x00" * full:
        return False
    if rem and (digest[full] >> (8 - rem)):
        return False
    return True

def hash_pow(challenge_input, checksum, difficulty):
    combined_bytes = (challenge_input + checksum).encode('utf-8')
    for nonce in itertools.count(0):
        data = combined_bytes + str(nonce).encode()
        digest = hashlib.sha256(data).digest()
        if _check(digest, difficulty):
            return str(nonce)
    return None


def scrypt_func(input_str, salt_str, memory_cost):
    return binascii.hexlify(
        pyscrypt.hash(
            password=input_str.encode(),
            salt=salt_str.encode(),
            N=memory_cost, r=8, p=1, dkLen=16
        )
    ).decode()

def compute_scrypt_nonce(challenge_input, checksum, difficulty):
    combined = challenge_input + checksum
    salt = checksum
    memory = 128
    for nonce in itertools.count(0):
        result = scrypt_func(f"{combined}{nonce}", salt, memory)
        if _check(binascii.unhexlify(result), difficulty):
            return str(nonce)
    return None


CHALLENGE_TYPES: dict[str, Union[Callable[[Any, Any, Any], str], str]] = {
    'h72f957df656e80ba55f5d8ce2e8c7ccb59687dba3bfb273d54b08a261b2f3002': compute_scrypt_nonce,
    'h7b0c470f0cfe3a80a9e26526ad185f484f6817d0832712a4a37a908786a6a67f': hash_pow,
    'ha9faaffd31b4d5ede2a2e19d2d7fd525f66fee61911511960dcbb52d3c48ce25': "mp_verify"
}
