# Release and hosted Flatpak repository

The stable distribution is a project-controlled, signed Flatpak repository
published through GitHub Pages. Flathub is intentionally not used.

## One-time owner setup

1. Create a dedicated GPG signing key for the Flatpak repository.
2. Keep the private key outside the repository and store it in the GitHub
   Actions secret `FLATPAK_GPG_PRIVATE_KEY`.
3. Store the passphrase in `FLATPAK_GPG_PASSPHRASE` and the public key in the
   Pages repository as `repo/gnome.gpg`.
4. Set `PAGES_REPOSITORY` to the GitHub Pages repository that will host the
   generated `repo/` directory.

Never commit the private key. The release workflow refuses to publish a stable
release when the signing material is absent.

## Tagged release

Push a signed `v1.0.0` tag after CI passes. The release workflow builds the
x86_64 Flatpak, exports the signed repository, generates static deltas, creates
the standalone bundle and SHA-256 checksum, and attaches the bundle,
checksum, release notes, and `.flatpakref` to the GitHub release.

## Local checks

```bash
flatpak-builder --force-clean --user --install build-dir flatpak/io.github.the_blue_blurr.ChromaSunder.yml
flatpak run io.github.the_blue_blurr.ChromaSunder
```

