# Flatpak packaging

This directory describes the Fedora-first, x86_64-only Flatpak package. The
application uses portals for selected files and folders and does not request
unrestricted home access or network access.

The release repository will be signed and hosted through GitHub Pages. The
checked-in descriptors intentionally have no `GPGKey` until the owner creates
the dedicated release key; they are not installable release artifacts before
that key is embedded and the repository is published.
