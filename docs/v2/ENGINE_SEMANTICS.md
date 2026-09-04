# Deterministic Engine Semantics

## Pixels And Settings

Canonical pixels are contiguous row-major `RgbaPixel<uint8_t>` or `RgbaPixel<uint16_t>`. RGBA moves
as one value; alpha never contributes to a sorting key. There is no implicit precision conversion.
Settings accept finite angles, normalized thresholds in `[0,1]`, randomness in `[0,100]`,
characteristic length at least one, and a 64-bit unsigned seed. File interval modes require exact
dimension interval data.

## Sorting Keys

All modes sort ascending and use `std::stable_sort` over keys precomputed once per selected set.

- Lightness: `max(R,G,B) + min(R,G,B)`.
- Intensity: `R + G + B` in a 64-bit intermediate.
- Minimum: `min(R,G,B)`.
- Hue: exact HLS sector numerator normalized to `[0,1)`, then truncated to unsigned Q40.
- Saturation: HLS `delta/(max+min)` below/equal half lightness and
  `delta/(2*channel_max-max-min)` above half, then truncated to unsigned Q40.

Q40 has scale `2^40`. It distinguishes all relevant U8/U16 key steps while avoiding floating-point
comparators. Equal Q40 keys retain incoming path order.

## Thresholds And Intervals

Lightness is the exact rational `(max+min)/(2*channel_max)`. API thresholds are converted once to
Q40. Lower bounds round upward and upper bounds round downward, then comparisons use wide integer
cross-products. This preserves inclusive comparisons without platform floating-point drift.

Intervals are half-open and lengths below two are discarded:

- None emits the complete path.
- Threshold emits connected pixels inclusively inside lower/upper HLS lightness.
- Edges starts at zero, adds a boundary for adjacent lightness difference `>= lower`, appends the
  path end, and discards resulting singleton regions.
- Random repeatedly uses `max(1, floor(characteristic_length * uniform_unit()))`.
- Waves repeatedly uses `characteristic_length + bounded_integer(11)`.
- File emits connected enabled runs.
- File Edges compares the first sample with artificial false, preserves transitions, deduplicates
  boundary zero, appends the path end, and also emits disabled regions between transitions.

For each emitted interval, interval-skip randomness is consumed before mask cardinality is checked.
The mask then selects positions inside the interval. Mask gaps never split intervals, so enabled
pixels can cross disabled gaps. Disabled positions remain byte-identical.

## Direction Convention

Angles normalize modulo 360. `0` is left-to-right, `90` bottom-to-top, `180` right-to-left, and
`270` top-to-bottom. Values within `1e-9` degrees of a cardinal direction use exact row/column paths.

Other angles use `dx=cos(theta)`, `dy=-sin(theta)`. The larger absolute component is the major axis.
The minor/major slope is quantized once with round-away-from-zero at half to signed Q32. Per primary
step, secondary offset also uses explicit nearest rounding, and `path_id = secondary-offset`.
Descriptors cover every source coordinate exactly once and never resample pixels.

## Compatibility

The frozen matrix covers 400 exact V1 cases: five sorting modes, None/Threshold/Edges/File/File
Edges, four cardinal directions, and none/all-on/all-off/gapped masks. As approved, V2 Random/Waves
streams and non-cardinal direct paths intentionally differ from V1. Q40 threshold comparison also
removes V1's operand-dependent floating-point behavior at mathematically equal edge boundaries;
this deterministic boundary behavior follows the V2 milestone contract and is tested explicitly.
