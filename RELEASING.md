# Releasing

This describes how to cut an aimbat release. It's aimed at maintainers with
push access and Actions permissions on this repository.

## Prerequisites

- Everything intended for the release is already merged into `master`.
- `CHANGELOG.md`'s `## [Unreleased]` section (kept current on every push to
  `master` by the `changelog` workflow) reflects what you expect to ship.
  Note history before `v1.0.7` is deliberately excluded from generation
  (`cliff.toml`'s config has no such cutoff — it's applied via a `v1.0.7..`
  range argument at every git-cliff invocation) since that predates the
  project's conventional-commit convention.

## 1. Decide the version

There's no automated bump — pick `vX.Y.Z` (or `vX.Y.ZrcN` / `vX.Y.Z.devN`
for a pre-release) by eye from the conventional-commit types in
`Unreleased`: `feat` → minor, `fix` → patch, a breaking change footer →
major.

If the next release is a minor or major bump (not a patch), consider
tagging a `.dev0` marker for that target version once work begins (e.g.
`v2.0.0.dev0`) — without it, `hatch-vcs`'s default version-guessing only
ever assumes the next release is a patch, so locally-built dev versions
would show a misleading `X.Y.(Z+1).devN` until the real tag exists.
`hatch-vcs` only accepts `.dev0` for a manually created tag — any other
`.devN` number is rejected outright when it tries to compute a version.

## 2. Run the `release-prep` workflow

From the Actions tab, select **release-prep** → **Run workflow**, and enter
the version. Or via the CLI:

```sh
gh workflow run release-prep.yml -f version=v2.0.0
```

This is the *only* manual trigger. It runs as one ordered job:

1. Validates the version format and confirms the tag doesn't already exist.
2. For a full release (not `rc`/`.dev`): regenerates `CHANGELOG.md` labelled
   `## [2.0.0] - date` and pushes it to `master` as an ordinary commit.
3. Creates and pushes the annotated tag on top of that commit.

Concurrent dispatches are serialized, so it's safe to trigger without
checking whether another run is in flight.

## 3. What happens automatically

- The `CHANGELOG.md` push to `master` triggers the docs site (GitHub Pages)
  to redeploy, already showing the correct version heading — it was
  committed before the tag existed.
- The tag push triggers `release.yml`: builds the sdist/wheel, publishes to
  TestPyPI, publishes to PyPI (skipped for `.dev` pre-releases), and
  creates the GitHub Release with the built artifacts attached.

## 4. Verify

Check the Actions tab for both the `release-prep` and `release` runs, then
confirm the GitHub Release and the PyPI page look right.

## Do not tag manually

Always cut releases via `release-prep.yml`, not `git tag` + `git push` by
hand. `release.yml` triggers on any matching tag regardless of origin, so
the build/publish/release steps still work — but a manually-created tag
skips the changelog commit, so it carries whichever `CHANGELOG.md` heading
was last on `master` (typically still `## [Unreleased]`).

This self-heals on GitHub Pages the next time an ordinary commit lands on
`master`, since the `changelog` workflow picks up the tag from git history
on its own. It does **not** self-heal on Read the Docs if it's building
that tag as its own pinned version — that build stays wrong permanently,
since it's tied to a fixed git ref.

If this happens, there's no automated recovery (`release-prep.yml` refuses
to re-run against a tag that already exists). Fix it manually:

```sh
git checkout v2.0.0
uv run git-cliff v1.0.7.. --config cliff.toml --tag v2.0.0 --output CHANGELOG.md
git checkout master
# apply the regenerated CHANGELOG.md, commit, and push to master
```
