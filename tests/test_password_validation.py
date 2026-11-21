"""UTF-8 boundaries shared by registration and password reset validation."""

import pytest

from auth import hash_password, validate_password, verify_password


@pytest.mark.parametrize("password", ["a" * 72, "é" * 36, "😀" * 18])
def test_password_utf8_byte_boundary(password):
    assert len(password.encode("utf-8")) == 72
    assert validate_password(password) is None
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert validate_password(password + "a") == "Password must be 72 bytes or fewer"
    with pytest.raises(ValueError, match="max 72 bytes"):
        hash_password(password + "a")
    assert not verify_password(password + "a", hashed)


def test_password_minimum_counts_unicode_characters():
    assert validate_password("😀" * 7) == "Password must be at least 8 characters"
    assert validate_password("😀" * 8) is None
