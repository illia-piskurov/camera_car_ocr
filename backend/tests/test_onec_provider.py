from __future__ import annotations

from app.normalization import normalize_plate
from app.onec_provider import StubFileWhitelistProvider, TEST_PLATE


def test_stub_whitelist_provider_always_includes_test_plate(tmp_path) -> None:
    stub_file = tmp_path / "onec_whitelist_stub.txt"
    stub_file.write_text("AA0001AA\n# comment\nAA1234ZE\n", encoding="utf-8")

    provider = StubFileWhitelistProvider(str(stub_file))

    rows = provider.full_sync()

    assert ("AA0001AA", "AA0001AA") in rows
    expected = normalize_plate(TEST_PLATE)
    assert rows.count((expected.normalized, expected.fuzzy)) == 1