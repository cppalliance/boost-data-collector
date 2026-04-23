"""Ensure DiscordChatExporter CLI exists: local tools/, legacy script/, zip (Windows), or git + dotnet build."""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from ..workspace import get_script_dir, get_tools_dir, get_workspace_root

logger = logging.getLogger(__name__)

DCE_GITHUB_REPO = "Tyrrrz/DiscordChatExporter"
DCE_GIT_URL = f"https://github.com/{DCE_GITHUB_REPO}.git"
# Pinned release: https://github.com/Tyrrrz/DiscordChatExporter/releases — default 2.47
DEFAULT_PINNED_VERSION = "2.47"

USER_AGENT = "boost-data-collector/dce_cli (DiscordChatExporter bootstrap)"

# Full RID zip (e.g. 2.47) extracts here so the .exe sits next to its DLLs
DCE_CLI_BUNDLE_SUBDIR = "DiscordChatExporter-cli"


def _pinned_release_tag() -> str:
    """Git tag for releases API and git clone (e.g. ``2.47``)."""
    env_val = (os.environ.get("DISCORD_CHAT_EXPORTER_VERSION") or "").strip()
    if env_val:
        return env_val
    try:
        from django.conf import settings

        if getattr(settings, "configured", False):
            v = (getattr(settings, "DISCORD_CHAT_EXPORTER_VERSION", "") or "").strip()
            if v:
                return v
    except Exception:
        pass
    return DEFAULT_PINNED_VERSION


def _release_api_url(tag: str) -> str:
    return f"https://api.github.com/repos/{DCE_GITHUB_REPO}/releases/tags/{tag}"


class DiscordChatExporterCliNotFoundError(RuntimeError):
    """Raised when the CLI cannot be downloaded or built."""


def _win32() -> bool:
    return sys.platform == "win32"


def _cli_exe_name() -> str:
    return "DiscordChatExporter.Cli.exe" if _win32() else "DiscordChatExporter.Cli"


def _find_executable_in_dir(directory: Path, name: str) -> Path | None:
    """Return path if file exists and is a file."""
    p = directory / name
    if p.is_file():
        return p
    return None


def _find_cli_anywhere(tools: Path, script: Path) -> Path | None:
    name = _cli_exe_name()
    for base in (tools, script):
        if not base.exists():
            continue
        found = _find_executable_in_dir(base, name)
        if found:
            return found
    bundle = tools / DCE_CLI_BUNDLE_SUBDIR / name
    if bundle.is_file():
        return bundle
    return None


def _dotnet_rid() -> str:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "win-x64"
    if system == "Darwin":
        return "osx-arm64" if machine in ("arm64", "aarch64") else "osx-x64"
    return "linux-x64"


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=600) as resp:
        dest.write_bytes(resp.read())


def _extract_cli_zip_bundle(zip_path: Path, tools_dir: Path) -> Path:
    """
    Extract a RID-specific CLI zip (flat layout) so DiscordChatExporter.Cli.exe
    sits next to its dependencies under tools/DiscordChatExporter-cli/.
    """
    bundle = tools_dir / DCE_CLI_BUNDLE_SUBDIR
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True, exist_ok=True)
    target_name = "DiscordChatExporter.Cli.exe"
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(bundle)
    exe = bundle / target_name
    if not exe.is_file():
        raise DiscordChatExporterCliNotFoundError(
            f"No {target_name} found inside {zip_path} after extract"
        )
    return exe


def _extract_cli_exe_only_from_zip(zip_path: Path, dest_dir: Path) -> Path:
    """Legacy: single nested or flat zip where copying only the .exe is enough."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_name = "DiscordChatExporter.Cli.exe"
    with zipfile.ZipFile(zip_path, "r") as zf:
        member = None
        for name in zf.namelist():
            if name.endswith(target_name):
                member = name
                break
        if member is None:
            raise DiscordChatExporterCliNotFoundError(
                f"No {target_name} found inside {zip_path}"
            )
        data = zf.read(member)
    out = dest_dir / target_name
    out.write_bytes(data)
    return out


def _clone_repo(vendor_dir: Path, *, tag: str) -> None:
    if vendor_dir.exists():
        return
    vendor_dir.parent.mkdir(parents=True, exist_ok=True)
    git = _which("git")
    if not git:
        raise DiscordChatExporterCliNotFoundError(
            "git not found in PATH; install Git to build DiscordChatExporter from source."
        )
    subprocess.run(
        [
            git,
            "clone",
            "-b",
            tag,
            "--depth",
            "1",
            DCE_GIT_URL,
            str(vendor_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _dotnet_publish(vendor_dir: Path, tools_dir: Path) -> Path:
    dotnet = _which("dotnet")
    if not dotnet:
        raise DiscordChatExporterCliNotFoundError(
            ".NET SDK not found in PATH; install .NET SDK to build DiscordChatExporter, "
            "or place the CLI manually under workspace/discord_activity_tracker/tools/."
        )
    csproj = vendor_dir / "DiscordChatExporter.Cli" / "DiscordChatExporter.Cli.csproj"
    if not csproj.is_file():
        raise DiscordChatExporterCliNotFoundError(
            f"Expected project at {csproj} after clone."
        )
    rid = _dotnet_rid()
    publish_out = tools_dir / "dce_publish"
    if publish_out.exists():
        shutil.rmtree(publish_out)
    publish_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        dotnet,
        "publish",
        str(csproj),
        "-c",
        "Release",
        "-r",
        rid,
        "--self-contained",
        "true",
        "-o",
        str(publish_out),
    ]
    logger.info("Building DiscordChatExporter CLI: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    name = _cli_exe_name()
    exe = publish_out / name
    if exe.is_file():
        return exe
    for p in publish_out.rglob(name):
        if p.is_file():
            return p
    raise DiscordChatExporterCliNotFoundError(
        f"dotnet publish succeeded but {name} not found under {publish_out}"
    )


def _preferred_cli_zip_name() -> str | None:
    """Release asset name for prebuilt CLI (Tyrrrz 2.4x+ ships per-RID zips)."""
    if not _win32():
        return None
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return "DiscordChatExporter.Cli.win-arm64.zip"
    return "DiscordChatExporter.Cli.win-x64.zip"


def _try_download_release_zip(tools_dir: Path) -> Path | None:
    """Download pinned release zip and extract Windows CLI; returns path or None if not applicable."""
    if not _win32():
        return None
    tag = _pinned_release_tag()
    api_url = _release_api_url(tag)
    try:
        data = _http_get_json(api_url)
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        logger.warning("Could not fetch GitHub release %s (%s): %s", tag, api_url, e)
        return None
    assets = data.get("assets") or []
    name_to_url = {
        (a.get("name") or ""): a.get("browser_download_url")
        for a in assets
        if a.get("name") and a.get("browser_download_url")
    }

    zip_url = None
    chosen_asset_name: str | None = None
    preferred = _preferred_cli_zip_name()
    if preferred and preferred in name_to_url:
        zip_url = name_to_url[preferred]
        chosen_asset_name = preferred
    if not zip_url:
        # Older releases: one umbrella .zip containing Cli.exe
        for a in assets:
            an = (a.get("name") or "").lower()
            if an.endswith(".zip") and "discord" in an and "exporter" in an:
                zip_url = a.get("browser_download_url")
                chosen_asset_name = a.get("name")
                break
    if not zip_url:
        for a in assets:
            if (a.get("name") or "").lower().endswith(".zip"):
                zip_url = a.get("browser_download_url")
                chosen_asset_name = a.get("name")
                break
    if not zip_url:
        return None
    tools_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        zpath = Path(tmp) / "dce.zip"
        logger.info(
            "Downloading DiscordChatExporter %s asset %s from GitHub",
            tag,
            chosen_asset_name or "zip",
        )
        _download_file(zip_url, zpath)
        # Per-RID zips (2.4x+) are a flat bundle of exe + DLLs — extract all.
        ca = (chosen_asset_name or "").lower()
        if ca.startswith("discordchatexporter.cli.") and ca.endswith(".zip"):
            return _extract_cli_zip_bundle(zpath, tools_dir)
        return _extract_cli_exe_only_from_zip(zpath, tools_dir)


def ensure_discord_chat_exporter_cli() -> Path:
    """
    Return path to DiscordChatExporter CLI, installing under workspace/tools/ if missing.

    Resolution order:
    1. tools/ or script/ (existing install or symlink)
    2. Windows: pinned GitHub release .zip (see ``DISCORD_CHAT_EXPORTER_VERSION``, default 2.47)
    3. git clone (same tag) + dotnet publish (non-Windows or if zip path unavailable)
    """
    tools_dir = get_tools_dir()
    script_dir = get_script_dir()
    existing = _find_cli_anywhere(tools_dir, script_dir)
    if existing:
        logger.debug("Using existing DiscordChatExporter CLI at %s", existing)
        return existing

    tools_dir.mkdir(parents=True, exist_ok=True)

    if _win32():
        try:
            exe = _try_download_release_zip(tools_dir)
            if exe and exe.is_file():
                logger.info(
                    "Installed DiscordChatExporter CLI from release zip: %s", exe
                )
                return exe
        except Exception as e:
            logger.warning("Release zip install failed: %s", e)

    vendor_dir = get_workspace_root() / "vendor" / "DiscordChatExporter"
    try:
        _clone_repo(vendor_dir, tag=_pinned_release_tag())
        exe = _dotnet_publish(vendor_dir, tools_dir)
        final = tools_dir / _cli_exe_name()
        if exe.resolve() != final.resolve():
            shutil.copy2(exe, final)
            if not _win32():
                final.chmod(final.stat().st_mode | 0o111)
        logger.info("Built DiscordChatExporter CLI: %s", final)
        return final
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "") + (e.stdout or "")
        raise DiscordChatExporterCliNotFoundError(
            f"Failed to build DiscordChatExporter CLI: {stderr[:2000]}"
        ) from e


def get_dce_cli_path() -> Path:
    """Return CLI path, calling ensure_discord_chat_exporter_cli if needed."""
    return ensure_discord_chat_exporter_cli()
