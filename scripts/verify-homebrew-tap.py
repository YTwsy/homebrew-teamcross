#!/usr/bin/env python3
"""Validate Team Cross tap metadata and install both public channels in isolation."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import tarfile
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
UPSTREAM = "YTwsy/Team-Cross"
TAP_URL = "https://github.com/YTwsy/homebrew-teamcross.git"
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
CHANNELS = {
    "stable": {
        "formula_token": "teamcross",
        "formula_class": "Teamcross",
        "formula_path": "Formula/teamcross.rb",
        "cask_token": "team-cross",
        "cask_path": "Casks/team-cross.rb",
    },
    "rc": {
        "formula_token": "teamcross-rc",
        "formula_class": "TeamcrossRc",
        "formula_path": "Formula/teamcross-rc.rb",
        "cask_token": "team-cross@rc",
        "cask_path": "Casks/team-cross@rc.rb",
    },
}


def digest(path: pathlib.Path) -> str:
    import hashlib

    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def download(url: str, destination: pathlib.Path) -> None:
    subprocess.run(
        [
            "/usr/bin/curl",
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--proto",
            "=https",
            "--tlsv1.2",
            "--retry",
            "3",
            "--retry-all-errors",
            "--user-agent",
            "Team-Cross-Homebrew-CI",
            "--output",
            str(destination),
            url,
        ],
        check=True,
        timeout=120,
    )


def load_channel(repository: pathlib.Path, channel: str) -> tuple[dict[str, object], dict[str, str]]:
    config = CHANNELS[channel]
    metadata = json.loads((repository / f"Versions/{channel}.json").read_text())
    version = metadata.get("version")
    tag = metadata.get("tag")
    source = metadata.get("source")
    artifacts = metadata.get("artifacts")
    definitions = metadata.get("definitions")
    if metadata.get("schemaVersion") != 1 or metadata.get("channel") != channel:
        raise ValueError(f"invalid {channel} metadata schema or channel")
    if not isinstance(version, str) or tag != f"v{version}":
        raise ValueError(f"invalid {channel} version or tag")
    if channel == "stable" and not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("stable metadata contains a non-stable version")
    if channel == "rc" and not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-rc\.[1-9][0-9]*", version):
        raise ValueError("RC metadata contains a non-RC version")
    if not isinstance(source, dict) or source.get("repository") != UPSTREAM or not COMMIT.fullmatch(str(source.get("commit", ""))):
        raise ValueError(f"invalid {channel} source provenance")
    if metadata.get("architecture") != "arm64" or metadata.get("minimumMacOS") != "14.0":
        raise ValueError(f"invalid {channel} platform")
    if not isinstance(artifacts, dict) or not isinstance(definitions, dict):
        raise ValueError(f"invalid {channel} artifact or definition map")
    if definitions != {"formula": config["formula_path"], "cask": config["cask_path"]}:
        raise ValueError(f"invalid {channel} definition paths")

    cli = artifacts.get("cli")
    dmg = artifacts.get("dmg")
    if not isinstance(cli, dict) or not isinstance(dmg, dict):
        raise ValueError(f"invalid {channel} artifacts")
    expected_names = {
        "cli": f"teamcross-{version}-darwin-arm64.tar.gz",
        "dmg": f"Team-Cross-{version}-arm64.dmg",
    }
    for kind, artifact in (("cli", cli), ("dmg", dmg)):
        name = expected_names[kind]
        expected_url = f"https://github.com/{UPSTREAM}/releases/download/{tag}/{name}"
        if artifact.get("name") != name or artifact.get("url") != expected_url or not SHA256.fullmatch(str(artifact.get("sha256", ""))):
            raise ValueError(f"invalid {channel} {kind} metadata")

    formula = (repository / config["formula_path"]).read_text()
    cask = (repository / config["cask_path"]).read_text()
    for line in (
        f'class {config["formula_class"]} < Formula',
        f'url "{cli["url"]}"',
        f'version "{version}"',
        f'sha256 "{cli["sha256"]}"',
    ):
        if line not in formula:
            raise ValueError(f"{channel} Formula is missing: {line}")
    for line in (
        f'cask "{config["cask_token"]}" do',
        f'url "{dmg["url"]}"',
        f'version "{version}"',
        f'sha256 "{dmg["sha256"]}"',
    ):
        if line not in cask:
            raise ValueError(f"{channel} Cask is missing: {line}")
    return metadata, config


def fetch_release(metadata: dict[str, object], destination: pathlib.Path) -> bytes:
    version = str(metadata["version"])
    tag = str(metadata["tag"])
    artifacts = metadata["artifacts"]
    assert isinstance(artifacts, dict)
    destination.mkdir(parents=True)
    for artifact in artifacts.values():
        assert isinstance(artifact, dict)
        target = destination / str(artifact["name"])
        download(str(artifact["url"]), target)
        if digest(target) != artifact["sha256"]:
            raise ValueError(f"public artifact checksum mismatch: {target.name}")

    manifest_path = destination / "release.json"
    sums_path = destination / "SHA256SUMS"
    base = f"https://github.com/{UPSTREAM}/releases/download/{tag}"
    download(f"{base}/release.json", manifest_path)
    download(f"{base}/SHA256SUMS", sums_path)
    manifest = json.loads(manifest_path.read_text())
    source = metadata["source"]
    assert isinstance(source, dict)
    expected_artifacts = {
        str(artifact["name"]): str(artifact["sha256"])
        for artifact in artifacts.values()
        if isinstance(artifact, dict)
    }
    if manifest.get("version") != version or manifest.get("commit") != source["commit"] or manifest.get("dirty") is not False:
        raise ValueError("public release manifest does not match tap provenance")
    if manifest.get("artifacts") != expected_artifacts:
        raise ValueError("public release manifest artifacts do not match tap metadata")
    sums: dict[str, str] = {}
    for line in sums_path.read_text().splitlines():
        checksum, name = line.split(None, 1)
        sums[name.strip()] = checksum
    if sums != expected_artifacts:
        raise ValueError("public SHA256SUMS does not match tap metadata")

    cli_name = f"teamcross-{version}-darwin-arm64.tar.gz"
    with tarfile.open(destination / cli_name) as archive:
        member = archive.getmember("teamcross")
        handle = archive.extractfile(member)
        if handle is None:
            raise ValueError("CLI archive has no teamcross executable")
        return handle.read()


class IsolatedHomebrew:
    def __init__(self, repository: pathlib.Path, root: pathlib.Path):
        self.repository = repository
        self.root = root
        self.prefix = root / "brew"
        self.apps = root / "Applications"
        self.apps.mkdir()
        source = pathlib.Path(subprocess.check_output(["/opt/homebrew/bin/brew", "--repository"], text=True).strip())
        subprocess.run(["git", "clone", "--quiet", "--local", "--shared", str(source), str(self.prefix)], check=True)
        ruby_source = source / "Library/Homebrew/vendor/portable-ruby"
        ruby_target = self.prefix / "Library/Homebrew/vendor/portable-ruby"
        ruby_target.mkdir(exist_ok=True)
        for path in ruby_source.iterdir():
            target = ruby_target / path.name
            if not target.exists():
                target.symlink_to(path.resolve(), target_is_directory=path.is_dir())
        self.tap = self.prefix / "Library/Taps/teamcross/homebrew-install-test"
        shutil.copytree(repository, self.tap, ignore=shutil.ignore_patterns("__pycache__"))
        if not (self.tap / ".git").exists():
            subprocess.run(["git", "init", "-q", str(self.tap)], check=True)
            subprocess.run(["git", "-C", str(self.tap), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(self.tap), "-c", "user.name=Tap Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Tap fixture"],
                check=True,
            )
        self.env = os.environ.copy()
        self.env.update(
            XDG_CONFIG_HOME=str(root / "config"),
            HOMEBREW_NO_AUTO_UPDATE="1",
            HOMEBREW_NO_INSTALL_FROM_API="1",
            HOMEBREW_NO_ANALYTICS="1",
            HOMEBREW_NO_INSTALL_CLEANUP="1",
            HOMEBREW_NO_AUTOREMOVE="1",
            HOMEBREW_NO_ENV_HINTS="1",
            HOMEBREW_CACHE=str(root / "cache"),
            HOMEBREW_LOGS=str(root / "logs"),
            HOMEBREW_TEMP=str(root / "tmp"),
        )
        (root / "tmp").mkdir()
        self.env.pop("HOMEBREW_NO_INSTALL_FROM_API", None)
        api_cache = pathlib.Path.home() / "Library/Caches/Homebrew/api"
        if api_cache.exists():
            shutil.copytree(api_cache, root / "cache/api")
        self.env["HOMEBREW_API_AUTO_UPDATE_SECS"] = "864000"
        self.brew = self.prefix / "bin/brew"

    def run(self, *arguments: str, expect_failure: bool = False) -> subprocess.CompletedProcess[str]:
        process = subprocess.Popen(
            [str(self.brew), *arguments],
            env=self.env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            process.communicate(timeout=10)
            raise
        if expect_failure:
            if process.returncode == 0:
                raise AssertionError(f"conflicting installation unexpectedly succeeded: {arguments}")
            if not any(word in stdout + stderr for word in ("请先运行", "conflict", "Conflict", "already a Binary")):
                raise AssertionError(stdout + stderr)
        elif process.returncode:
            raise RuntimeError(
                f"Homebrew command failed ({process.returncode}): {' '.join(process.args)}\n{stdout}\n{stderr}"
            )
        return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def verify_install(repository: pathlib.Path, channel: str, expected_cli: bytes, *, cross_channel: bool) -> dict[str, object]:
    config = CHANNELS[channel]
    other_name = "stable" if channel == "rc" else "rc"
    other = CHANNELS[other_name]
    with tempfile.TemporaryDirectory(prefix=f"teamcross-tap-{channel}-") as temporary:
        homebrew = IsolatedHomebrew(repository, pathlib.Path(temporary).resolve())
        formula = f'teamcross/install-test/{config["formula_token"]}'
        cask = f'teamcross/install-test/{config["cask_token"]}'
        installed_formula: str | None = None
        installed_cask: str | None = None
        try:
            homebrew.run("trust", "--formula", formula)
            homebrew.run("trust", "--cask", cask)
            homebrew.run("install", "--formula", formula)
            installed_formula = formula
            homebrew.run("test", formula)
            cli = homebrew.prefix / "bin/teamcross"
            if cli.read_bytes() != expected_cli:
                raise AssertionError("Formula executable differs from the public CLI artifact")
            homebrew.run("install", "--cask", f"--appdir={homebrew.apps}", cask, expect_failure=True)
            homebrew.run("uninstall", "--force", "--ignore-dependencies", "--formula", formula)
            installed_formula = None

            homebrew.run("install", "--cask", f"--appdir={homebrew.apps}", cask)
            installed_cask = cask
            helper = homebrew.apps / "Team Cross.app/Contents/Resources/teamcross"
            if not cli.is_symlink() or cli.resolve() != helper.resolve() or helper.read_bytes() != expected_cli:
                raise AssertionError("Cask command does not resolve to the public App helper")
            homebrew.run("install", "--formula", formula, expect_failure=True)
            homebrew.run("uninstall", "--cask", cask)
            installed_cask = None

            if cross_channel:
                other_formula = f'teamcross/install-test/{other["formula_token"]}'
                other_cask = f'teamcross/install-test/{other["cask_token"]}'
                homebrew.run("trust", "--formula", other_formula)
                homebrew.run("trust", "--cask", other_cask)
                homebrew.run("install", "--formula", other_formula)
                installed_formula = other_formula
                homebrew.run("install", "--formula", formula, expect_failure=True)
                homebrew.run("install", "--cask", f"--appdir={homebrew.apps}", cask, expect_failure=True)
                homebrew.run("uninstall", "--force", "--ignore-dependencies", "--formula", other_formula)
                installed_formula = None
                homebrew.run("install", "--cask", f"--appdir={homebrew.apps}", other_cask)
                installed_cask = other_cask
                homebrew.run("install", "--formula", formula, expect_failure=True)
                homebrew.run("install", "--cask", f"--appdir={homebrew.apps}", cask, expect_failure=True)
                homebrew.run("uninstall", "--cask", other_cask)
                installed_cask = None
            return {
                "channel": channel,
                "formulaInstallAndTest": True,
                "caskInstall": True,
                "formulaCaskMutualExclusion": True,
                "crossChannelMutualExclusion": cross_channel,
                "publicArtifacts": True,
                "isolatedPrefix": True,
            }
        finally:
            if installed_cask:
                homebrew.run("uninstall", "--cask", installed_cask)
            if installed_formula:
                homebrew.run("uninstall", "--force", "--ignore-dependencies", "--formula", installed_formula)


def verify_repository(repository: pathlib.Path) -> list[dict[str, object]]:
    actual_metadata = {path.name for path in (repository / "Versions").glob("*.json")}
    if "stable.json" not in actual_metadata or not actual_metadata <= {"stable.json", "rc.json"}:
        raise ValueError(f"tap must contain stable metadata and may contain RC metadata, found {sorted(actual_metadata)}")
    if any(path.is_symlink() for path in repository.rglob("*") if ".git" not in path.parts):
        raise ValueError("tap contents must not contain symlinks")
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="teamcross-public-assets-") as temporary:
        downloads = pathlib.Path(temporary)
        executables: dict[str, bytes] = {}
        channels = ["stable"] + (["rc"] if "rc.json" in actual_metadata else [])
        for channel in channels:
            metadata, _ = load_channel(repository, channel)
            executables[channel] = fetch_release(metadata, downloads / channel)
        results.append(verify_install(repository, "stable", executables["stable"], cross_channel=False))
        if "rc" in executables:
            results.append(verify_install(repository, "rc", executables["rc"], cross_channel=True))
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", action="store_true", help="Clone and verify the public tap main branch")
    args = parser.parse_args()
    if args.remote:
        with tempfile.TemporaryDirectory(prefix="teamcross-public-tap-") as temporary:
            repository = pathlib.Path(temporary) / "tap"
            subprocess.run(["git", "clone", "--quiet", "--depth", "1", TAP_URL, str(repository)], check=True)
            expected = os.environ.get("GITHUB_SHA")
            actual = subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip()
            if expected and actual != expected:
                raise ValueError(f"public tap main is {actual}, expected workflow commit {expected}")
            results = verify_repository(repository)
            tap_commit = actual
    else:
        results = verify_repository(ROOT)
        tap_commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    print(json.dumps({"tapCommit": tap_commit, "channels": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
