# Color And Codec Pipeline

The standalone codec layer uses libpng, libjpeg-turbo, and Little CMS 2. Sorting code has no codec
or profile knowledge.

## Import

1. Detect PNG/JPEG from its signature and decode at native supported depth.
2. Expand grayscale/RGB to canonical RGBA without changing 8/16-bit depth.
3. Parse focused TIFF EXIF orientation metadata and apply orientations 1 through 8.
4. Read embedded ICC data. Untagged input is treated as sRGB. Tagged non-sRGB input is converted by
   Little CMS using relative colorimetric intent, black-point compensation, and copied alpha.
5. Keep canonical pixels in sRGB RGBA8 or RGBA16.

Untagged input and PNGs carrying the standard sRGB chunk bypass an unnecessary transform. Embedded
ICC profiles are validated as RGB and transformed through Little CMS, including tagged sRGB. The
working profile is a generated Little CMS sRGB profile; the original non-sRGB profile is not attached
to converted pixels.

## PNG

RGB, RGBA, grayscale, and grayscale-alpha decode to canonical RGBA at 8 or 16 bits. Palette and tRNS
inputs are expanded safely. PNG network byte order is swapped explicitly on little-endian hosts.
Exports preserve native depth and emit standard sRGB gamma/chromaticity metadata. JPEG exports embed
the working sRGB ICC profile.

## JPEG

JPEG decodes to RGBA8 with opaque alpha. ICC APP2 chunks are reassembled in sequence. Export quality
is validated in `[1,100]`; output is always RGB8 with an sRGB ICC profile. Each channel is first
flattened onto black as `round(channel * alpha * 255 / channel_max^2)`. U16 conversion uses 64-bit
intermediates and a separate scratch buffer, leaving the U16 render unchanged.

## EXIF And Auxiliaries

The focused parser accepts little- or big-endian TIFF orientation entries and safely falls back to
orientation 1 for malformed metadata. Auxiliary files follow the same decode/orientation/color
pipeline, must exactly match canonical source dimensions, convert to Rec.601 grayscale, and become
one byte per binary sample. U8 uses the V1-compatible `>=128` boundary; U16 uses `>=32768`.

## Atomic Output

Encoders write and close a uniquely named sibling temporary file. POSIX rename or Windows
`MoveFileExW(REPLACE_EXISTING|WRITE_THROUGH)` then replaces the destination. Failure removes the
temporary and leaves the destination untouched where platform semantics permit.
