# SunChJ Homebrew tap

This tap distributes the public macOS binaries for
[Gloss](https://github.com/SunChJ/gloss-releases).

## Install

```bash
brew tap sunchj/tap
brew install --cask gloss
```

The fully qualified one-command form is:

```bash
brew install --cask sunchj/tap/gloss
```

Upgrade an existing installation with:

```bash
brew update
brew upgrade --cask gloss
```

Gloss requires macOS 14 Sonoma or later. The cask is intentionally absent until
the first complete, validated `v0.8.0` release is available in
`SunChJ/gloss-releases`.

## Release updates

The `Update Gloss cask` workflow accepts a public release tag, downloads the
Apple silicon and Intel archives plus their published metadata, and verifies:

- both archive SHA-256 values against `SHA256SUMS`;
- GitHub release immutability and the release attestation;
- the cask version and architecture-specific checksums;
- both cask URLs exactly match anonymous public assets for that release;
- the complete cask matches the reviewed deterministic template, with no extra
  Ruby statements;
- the fixed postflight steps re-sign `Gloss.app` ad-hoc, remove quarantine, and
  verify the resulting signature without `sudo`;
- the cask is valid Ruby syntax.

After validation, the workflow updates an `automation/gloss-*` branch and opens
or refreshes a pull request. It records `Cask validation` on the exact pushed
commit. `main` requires that status, an up-to-date branch, and one approving
review; stale approvals are dismissed. The workflow never writes a new cask
directly to `main`.

Repository settings must allow GitHub Actions to create pull requests. The
workflow uses only this repository's short-lived `GITHUB_TOKEN`.

## Trust model

Release checksums protect download integrity. During installation, this custom
cask re-signs `Gloss.app` locally with an ad-hoc identity, removes
`com.apple.quarantine`, and verifies the local signature. Gloss is not
Apple-notarized, and these steps do not provide an Apple Developer ID identity
or Apple approval. See the
[binary release policy](https://github.com/SunChJ/gloss-releases#signing-policy)
before installing.
