# Native Memory Model

The immutable canonical source, completed render, and candidate render are separate native buffers.
`ImageBuffer<T>` owns contiguous `HeapStorage<RgbaPixel<T>>`; views are non-owning and expose explicit
width, height, and stride. A future storage type can replace heap ownership without changing typed
pixel loops.

Every image allocation checks dimension multiplication and byte multiplication first. Render
estimation uses checked arithmetic and includes:

- canonical source bytes;
- a retained previous full render when present;
- candidate output bytes;
- one byte per mask/interval sample;
- worst-case per-worker pixel/index scratch for the longest dimension;
- operation-specific codec allowance;
- caller-selected safety margin.

The caller supplies `MemoryBudget::allowed_bytes`. An excess returns
`InsufficientMemoryBudget` with estimated and allowed byte counts before candidate allocation. The
engine never responds by downsampling or reducing U16 precision.

Worker tasks read only the source and write disjoint path coordinates in the candidate. There are no
per-pixel locks. Scratch vectors are path-local in Milestone 2; worker-local retained scratch is a
future measured optimization.
