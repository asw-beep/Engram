from uuid import UUID

import pytest

TENANT = UUID("11111111-1111-4111-8111-111111111111")


def test_same_content_gets_same_key(store):
    assert store.put(TENANT, b"x") == store.put(TENANT, b"x")


def test_get_returns_what_was_put(store):
    assert store.get(store.put(TENANT, b"hello")) == b"hello"


@pytest.mark.parametrize("key", ["../secret", f"{TENANT}/../../x", "a/b/c", f"{TENANT}/nothex"])
def test_key_outside_the_store_layout_is_rejected(store, key):
    with pytest.raises(ValueError):
        store.get(key)
