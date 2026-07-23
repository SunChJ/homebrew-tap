#!/usr/bin/env python3
"""Validate that a Gloss release manifest and cask describe verified archives."""

from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import re


def require_single(pattern: str, label: str, source: str) -> str:
    matches = re.findall(pattern, source, flags=re.MULTILINE | re.DOTALL)
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {label}; found {len(matches)}.")
    return matches[0]


def normalized(source: str) -> str:
    return "\n".join(line.strip() for line in source.splitlines())


def validate(arguments: argparse.Namespace) -> None:
    cask_text = arguments.cask.read_text(encoding="utf-8")
    manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    version = arguments.release_tag.removeprefix("v")
    base_url = (
        f"https://github.com/{arguments.repository}/releases/download/"
        f"{arguments.release_tag}"
    )

    cask_name = require_single(
        r'^cask "([^"]+)" do$', "cask declaration", cask_text
    )
    cask_version = require_single(
        r'^\s*version "([^"]+)"$', "version", cask_text
    )
    homepage = require_single(
        r'^\s*homepage "([^"]+)"$', "homepage", cask_text
    )
    arm_block = require_single(
        r"^\s*on_arm do\s*$\n(.*?)^\s*end\s*$", "on_arm block", cask_text
    )
    intel_block = require_single(
        r"^\s*on_intel do\s*$\n(.*?)^\s*end\s*$", "on_intel block", cask_text
    )

    def block_values(block: str, label: str) -> tuple[str, str]:
        checksum = require_single(
            r'^\s*sha256 "([0-9a-f]{64})"$', f"{label} checksum", block
        )
        url = require_single(r'^\s*url "([^"]+)"$', f"{label} URL", block)
        return checksum, url

    arm_checksum, arm_url = block_values(arm_block, "arm64")
    intel_checksum, intel_url = block_values(intel_block, "x86_64")
    expected_urls = {
        f"{base_url}/Gloss-macos-arm64.zip",
        f"{base_url}/Gloss-macos-x86_64.zip",
    }
    all_urls = set(
        re.findall(r'^\s*url "([^"]+)"$', cask_text, flags=re.MULTILINE)
    )
    expected_postflight = r'''  postflight do
      app_path = "#{appdir}/Gloss.app"
      extension_path = "#{app_path}/Contents/PlugIns/Gloss Extension.appex"
      entitlement_paths = [extension_path, app_path]
      entitlements_before = entitlement_paths.map do |code_path|
        system_command("/usr/bin/codesign",
                       args:         ["--display", "--entitlements", "-", code_path],
                       sudo:         false,
                       must_succeed: true,
                       print_stderr: false).stdout
      end
      code_paths = [
        extension_path,
        "#{app_path}/Contents/Helpers/gloss-codex-app-server",
        "#{app_path}/Contents/Helpers/gloss-cli",
        app_path,
      ]
      code_paths.each do |code_path|
        system_command "/usr/bin/codesign",
                       args:         [
                         "--force",
                         "--sign",
                         "-",
                         "--preserve-metadata=identifier,entitlements,requirements,flags,runtime",
                         code_path,
                       ],
                       sudo:         false,
                       must_succeed: true
      end
      entitlements_after = entitlement_paths.map do |code_path|
        system_command("/usr/bin/codesign",
                       args:         ["--display", "--entitlements", "-", code_path],
                       sudo:         false,
                       must_succeed: true,
                       print_stderr: false).stdout
      end
      raise "Gloss code-signing entitlements changed during installation" if entitlements_after != entitlements_before

      system_command "/usr/bin/xattr",
                     args:         ["-dr", "com.apple.quarantine", app_path],
                     sudo:         false,
                     must_succeed: true
      remaining_attributes = system_command "/usr/bin/xattr",
                                            args:         ["-lr", app_path],
                                            sudo:         false,
                                            must_succeed: true,
                                            print_stderr: false
      if remaining_attributes.stdout.include?("com.apple.quarantine")
        raise "Gloss quarantine attribute remains after installation"
      end

      system_command "/usr/bin/codesign",
                     args:         ["--verify", "--deep", "--strict", app_path],
                     sudo:         false,
                     must_succeed: true
    end'''
    expected_cask = (
        f'''cask "gloss" do
  version "{version}"

  on_arm do
    sha256 "{arguments.arm64_sha256}"

    url "{base_url}/Gloss-macos-arm64.zip"
  end
  on_intel do
    sha256 "{arguments.x86_64_sha256}"

    url "{base_url}/Gloss-macos-x86_64.zip"
  end

  name "Gloss"
  desc "Context-aware text and document translation"
  homepage "https://github.com/{arguments.repository}"

  depends_on macos: :sonoma

  app "Gloss.app"

'''
        + expected_postflight
        + '''

  uninstall quit: "com.samsoncj.gloss"

  zap trash: [
    "~/Library/Application Support/Gloss",
    "~/Library/Caches/Gloss",
    "~/Library/Logs/Gloss",
    "~/Library/Preferences/com.samsoncj.gloss.plist",
  ]

  caveats <<~EOS
    Gloss uses an ad-hoc code signature and is not Apple-notarized. This custom
    tap re-signs the installed app and removes its quarantine attribute.
  EOS
end
'''
    )

    normalized_expected_cask = normalized(expected_cask)
    normalized_release_cask = normalized(cask_text)
    if normalized_release_cask != normalized_expected_cask:
        difference = "".join(
            difflib.unified_diff(
                normalized_expected_cask.splitlines(keepends=True),
                normalized_release_cask.splitlines(keepends=True),
                fromfile="expected/gloss.rb",
                tofile="release/gloss.rb",
            )
        )
        raise ValueError(
            "Cask differs from the deterministic, reviewed release template:\n"
            f"{difference}"
        )

    checks = [
        (cask_name == "gloss", "Cask name must be gloss."),
        (cask_version == version, "Cask version does not match the release tag."),
        (
            homepage == f"https://github.com/{arguments.repository}",
            "Cask homepage does not match the release repository.",
        ),
        (
            arm_checksum == arguments.arm64_sha256,
            "arm64 cask checksum does not match.",
        ),
        (
            intel_checksum == arguments.x86_64_sha256,
            "x86_64 cask checksum does not match.",
        ),
        (
            arm_url == f"{base_url}/Gloss-macos-arm64.zip",
            "arm64 cask URL does not match the public release asset.",
        ),
        (
            intel_url == f"{base_url}/Gloss-macos-x86_64.zip",
            "x86_64 cask URL does not match the public release asset.",
        ),
        (all_urls == expected_urls, "Cask contains an unexpected download URL."),
        ('app "Gloss.app"' in cask_text, "Cask must install Gloss.app."),
        (
            'desc "Context-aware text and document translation"' in cask_text,
            "Cask description does not match the release contract.",
        ),
        (
            "depends_on macos: :sonoma" in cask_text,
            "Cask must require macOS Sonoma.",
        ),
        (
            normalized(expected_postflight) in normalized(cask_text),
            "Cask is missing the exact ad-hoc signing and quarantine postflight.",
        ),
        (
            cask_text.count("system_command") == 6,
            "Cask must contain exactly the six approved postflight commands.",
        ),
        (
            "Gloss uses an ad-hoc code signature and is not Apple-notarized."
            in cask_text,
            "Cask must disclose its ad-hoc, non-notarized signing policy.",
        ),
        (manifest.get("schemaVersion") == 1, "Unexpected manifest schema."),
        (manifest.get("channel") == "stable", "Manifest channel must be stable."),
        (manifest.get("version") == version, "Manifest version does not match."),
        (
            manifest.get("releaseTag") == arguments.release_tag,
            "Manifest release tag does not match.",
        ),
        (
            manifest.get("minimumMacOSVersion") == "14.0",
            "Manifest must require macOS 14.0.",
        ),
    ]
    for valid, message in checks:
        if not valid:
            raise ValueError(message)

    manifest_assets = {
        asset.get("architecture"): asset for asset in manifest.get("assets", [])
    }
    expected_manifest_assets = {
        "arm64": (
            f"{base_url}/Gloss-macos-arm64.zip",
            arguments.arm64_sha256,
            arguments.arm64_archive.stat().st_size,
        ),
        "x86_64": (
            f"{base_url}/Gloss-macos-x86_64.zip",
            arguments.x86_64_sha256,
            arguments.x86_64_archive.stat().st_size,
        ),
    }
    if set(manifest_assets) != set(expected_manifest_assets):
        raise ValueError("Manifest must contain exactly arm64 and x86_64 assets.")

    for architecture, (expected_url, expected_sha256, expected_size) in (
        expected_manifest_assets.items()
    ):
        asset = manifest_assets[architecture]
        if asset.get("operatingSystem") != "macos":
            raise ValueError(f"{architecture} manifest asset is not for macOS.")
        if asset.get("url") != expected_url:
            raise ValueError(f"{architecture} manifest URL does not match.")
        if asset.get("sha256") != expected_sha256:
            raise ValueError(f"{architecture} manifest checksum does not match.")
        if asset.get("size") != expected_size:
            raise ValueError(f"{architecture} manifest size does not match.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cask", type=pathlib.Path, required=True)
    parser.add_argument("--manifest", type=pathlib.Path, required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--arm64-archive", type=pathlib.Path, required=True)
    parser.add_argument("--arm64-sha256", required=True)
    parser.add_argument("--x86-64-archive", type=pathlib.Path, required=True)
    parser.add_argument("--x86-64-sha256", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    validate(parse_arguments())
