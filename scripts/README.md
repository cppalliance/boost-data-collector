# scripts/

Repository **maintenance** scripts (not Django app code).

| Script | Purpose |
| --- | --- |
| [`clean-macos.sh`](clean-macos.sh) | Delete macOS AppleDouble (`._*`) resource-fork files under the repo (skips `.git`). Use when Docker builds fail with `failed to xattr … operation not permitted` on network/external volumes. Optional arg: root directory (defaults to project root). |
| [`list_cross_app_imports.py`](list_cross_app_imports.py) | Cross-app import report (Markdown/CSV). |

See the root [README](../README.md) for how to run tests and Celery. Command-line collectors live under each app’s `management/commands/`.
