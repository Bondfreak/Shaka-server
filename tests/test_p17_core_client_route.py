from shaka_server.core_client import CoreClient


def test_core_client_exposes_diagnostic_route() -> None:
    client = CoreClient("https://example.invalid")
    assert hasattr(client, "cog_diagnostic")
