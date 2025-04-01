import pytest
from utils import generate_short_code
from crud import normalize_url

def test_generate_short_code_length():
    length = 8
    code = generate_short_code(length)
    assert len(code) == length

def test_generate_short_code_characters():
    code = generate_short_code(6)
    for char in code:
        assert char.isalnum()

def test_normalize_url():
    url1 = "http://example.com"
    url2 = "http://example.com/"
    normalized1 = normalize_url(url1)
    normalized2 = normalize_url(url2)
    assert normalized1 == normalized2