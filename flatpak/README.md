# Flatpak packaging

This directory describes the Fedora-first, x86_64-only Flatpak package. The
application uses portals for selected files and folders and does not request
unrestricted home access or network access.

The repository is signed and hosted through GitHub Pages. The final public
repository URL is filled into the generated `.flatpakrepo` and `.flatpakref`
files by the release workflow.

