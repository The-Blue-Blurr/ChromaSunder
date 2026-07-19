# Performance measurements

Measurements use synthetic uniform RGBA images and threshold mode on the
Fedora development host. They are smoke baselines, not promises for every
image or machine. Peak memory is the maximum resident set reported by GNU
`time`.

| Case | Elapsed | Peak RSS | Result |
|---|---:|---:|---|
| 1920x1080 | 2.01 s | 49 MiB | Completed at source dimensions |
| 6000x4000 | 23.75 s | 300 MiB | Completed at source dimensions |
| 6000x4000 at 45 degrees | 50.42 s | 1.23 GiB | Completed at source dimensions |

The rotated case has substantially higher peak memory because Pillow retains
expanded source, output, and inverse-rotation images. Cancellation is process
based and is covered separately by the worker integration tests.
