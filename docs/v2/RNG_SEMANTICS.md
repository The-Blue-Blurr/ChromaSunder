# V2 RNG Semantics

RNG semantics version is `1`. Persistent output does not use C++ standard-library distributions.

## SplitMix64

State and arithmetic are unsigned 64-bit with modulo `2^64` wraparound.

1. Add `0x9E3779B97F4A7C15` to state.
2. `z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9`.
3. `z = (z ^ (z >> 27)) * 0x94D049BB133111EB`.
4. Return `z ^ (z >> 31)`.

`uniform_unit()` takes the upper 53 output bits and multiplies by hexadecimal floating constant
`0x1.0p-53`, producing `[0,1)`. `bounded(n)` rejects values below `(-n) % n`, then returns `value %
n`; this removes modulo bias. A percentage test is `uniform_unit()*100 < percentage`, with exact
shortcuts for zero and 100.

## Path Seeds And Consumption

`mix_seed` is the SplitMix64 finalizer without its state increment. A path seed is:

```text
versioned = stable_path_id XOR (rng_semantics_version * 0xD6E8FEB86659FD93)
path_seed = mix_seed(global_seed XOR mix_seed(versioned))
```

Stable path IDs come from geometric path order, never worker identity. Each path owns one generator.
Interval generation consumes first, in path order; emitted intervals then consume one skip decision
each from left to right when randomness is nonzero. Scheduling and worker count cannot affect this
sequence.
