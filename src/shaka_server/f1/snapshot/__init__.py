"""F1-T04 frozen AC fixture snapshot (synthetic, in-repo)."""

from shaka_server.f1.snapshot.pack import (
    FIXTURE_PART_ABSENT,
    FIXTURE_PART_IMPELLER,
    FIXTURE_SERIALS,
    FixtureSnapshot,
    build_ac_fixture_snapshot,
    default_snapshot,
)

__all__ = [
    "FIXTURE_SERIALS",
    "FIXTURE_PART_IMPELLER",
    "FIXTURE_PART_ABSENT",
    "FixtureSnapshot",
    "build_ac_fixture_snapshot",
    "default_snapshot",
]
