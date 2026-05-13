"""Write ``discord_activity_tracker/schemas/discord_staging_v1.json``.

Run from the repository root::

    python -m discord_activity_tracker.scripts.write_staging_json_schema

See ``docs/discord-tracker-schema.md`` (section *JSON Schema artifact vs runtime validation*).
"""

from __future__ import annotations

from discord_activity_tracker.staging_schema import write_staging_json_schema


def main() -> None:
    path = write_staging_json_schema()
    print(path)


if __name__ == "__main__":
    main()
