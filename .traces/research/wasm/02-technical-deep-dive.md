# WebAssembly for Compute-Heavy Web Applications
## Technical Deep Dive: Architecture, Runtimes, Toolchains & Performance

**Date:** February 2026 | **Audience:** Technical CEOs & Engineering Leadership
**Scope:** Browser-side Wasm for compute-intensive operations

---

## Executive Summary

WebAssembly (Wasm) delivers **near-native execution speed** inside the browser sandbox,
achieving 95%+ of native performance for CPU-bound workloads across all major engines.
With the **Wasm 3.0 specification** finalized in September 2025 -- bundling GC, Memory64,
SIMD, exception handling, and tail calls -- the platform has crossed the threshold from
experimental to **production infrastructure**. Figma reports **3x load-time improvements**,
Google Sheets runs **2x faster** after migrating formula evaluation from JS to WasmGC,
and browser adoption has grown **28% year-over-year** to 4.5% of Chrome-visited websites.

This document dissects the internals: how Wasm modules compile and execute, where
interop overhead lives, which toolchains produce the best output, and where the
crossover points are between JavaScript and Wasm.

---

## Table of Contents

1. [Compilation Pipeline: How Wasm Executes in the Browser](#1-compilation-pipeline)
2. [JS-to-Wasm Interop: Overhead, Marshaling & Call Costs](#2-js-to-wasm-interop)
3. [Memory Model: Linear Memory, SharedArrayBuffer & GC](#3-memory-model)
4. [Threading: Web Workers + SharedArrayBuffer + Atomics](#4-threading)
5. [SIMD: Operations, Support & Measured Speedups](#5-simd)
6. [Toolchains: Emscripten, wasm-pack, AssemblyScript, TinyGo & More](#6-toolchains)
7. [Language Tradeoffs: Rust vs C++ vs Go vs AssemblyScript vs Zig](#7-language-tradeoffs)
8. [WASI & the Component Model](#8-wasi-and-component-model)
9. [Binary Size Optimization](#9-binary-size-optimization)
10. [Security Model](#10-security-model)
11. [Debugging & Profiling](#11-debugging-and-profiling)
12. [Emerging Proposals](#12-emerging-proposals)
13. [Where Wasm Beats JS -- and Where It Doesn't](#13-wasm-vs-js-crossover)
14. [Integration Patterns](#14-integration-patterns)
15. [Sources](#15-sources)

---

## 1. Compilation Pipeline

### How Wasm Executes in the Browser

Every major browser engine implements a **two-tier compilation strategy** for
WebAssembly. The binary format was designed from the start for streaming
compilation -- the engine can begin compiling bytes as they arrive over the
network, before the full module is downloaded.

```
                        Wasm Compilation Pipeline (All Engines)
 +-----------+
 |  .wasm    |    Network (streaming)
 |  binary   |──────────────────────────────────────────────────────┐
 +-----------+                                                      |
                                                                    v
                                              ┌──────────────────────────┐
                                              │   VALIDATION + DECODE    │
                                              │  (single pass, parallel) │
                                              └────────────┬─────────────┘
                                                           |
                                         ┌─────────────────┴──────────────────┐
                                         v                                    v
                                ┌─────────────────┐                ┌───────────────────┐
                                │ BASELINE COMPILE │                │  OPTIMIZING COMPILE│
                                │ (fast, 1-pass)   │                │  (slow, multi-pass)│
                                │                  │                │  (background thread)│
                                │ V8: Liftoff      │                │  V8: TurboFan      │
                                │ SM: Baseline JIT │                │  SM: IonMonkey/Warp│
                                │ JSC: BBQ         │                │  JSC: OMG          │
                                └───────┬──────────┘                └──────────┬─────────┘
                                        |                                      |
                                        v                                      v
                                ┌─────────────────┐                ┌───────────────────┐
                                │ Execute          │  ── tier up ──>│ Replace hot funcs  │
                                │ immediately      │                │ with optimized code│
                                └─────────────────┘                └───────────────────┘
```

### Engine-Specific Details

| Engine | Browser | Baseline Compiler | Optimizing Compiler | Compilation Rate |
|--------|---------|-------------------|---------------------|------------------|
| **V8** | Chrome, Edge | **Liftoff** -- single-pass, lazy per-function | **TurboFan** -- multi-pass, graph-based IR | Liftoff: tens of MB/s |
| **SpiderMonkey** | Firefox | **Baseline JIT** -- single-pass + validation | **IonMonkey/Warp** -- shared MIR with JS pipeline | Competitive with V8 |
| **JavaScriptCore** | Safari | **BBQ** (Build Bytecode Quickly) | **OMG** (Optimizing Machine-code Generator) | In-place interpreter for large modules (Safari 26.0) |

#### V8 (Chrome/Edge) -- The Most Documented Pipeline

**Liftoff** emits machine code in a single pass, compiling each Wasm instruction
independently. No register allocation optimization, no inlining, no redundant-load
elimination. The tradeoff: **near-instant startup** at the cost of ~30-40% slower
execution vs. optimized code.

**TurboFan** builds multiple intermediate representations (IR), enabling:
- Full register allocation
- Dead-code elimination
- Strength reduction
- Function inlining
- Loop-invariant code motion

**Dynamic tier-up**: V8 monitors call frequency. When a function crosses the "hot"
threshold, TurboFan recompilation is triggered on a **background thread**. The
executing function completes on Liftoff code; the optimized version replaces it on
the next call. No on-stack replacement (OSR) is used for Wasm.

**Code caching**: When using `WebAssembly.compileStreaming()`, TurboFan-generated
code is cached incrementally. Subsequent loads from the same URL skip recompilation
entirely. Liftoff code is never cached because **"Liftoff compilation is nearly as
fast as loading code from the cache"**
([V8 Wasm Pipeline](https://v8.dev/docs/wasm-compilation-pipeline)).

> **Key Insight:** Wasm's binary format is **fundamentally cheaper to parse than JavaScript**.
> JS requires full parsing, AST construction, and bytecode compilation before any
> execution. Wasm validation is a single linear pass. This is why Wasm files compile
> faster per kilobyte than equivalent JS, even before considering execution speed.

#### SpiderMonkey (Firefox)

SpiderMonkey translates Wasm into the same **MIR (Mid-level IR)** used by its
JavaScript JIT (WarpMonkey). This means Wasm benefits from the same backend
optimizations as JS, and the IonBackend generates optimized native code from
MIR. Firefox added an **in-place interpreter** for faster startup of very large
modules in 2025.

#### JavaScriptCore (Safari)

Safari 26.0 (2025) introduced a **new in-place interpreter** for Wasm that
improves startup for large modules by interpreting bytecode directly before
BBQ compilation kicks in. Safari 18.4 added the new Wasm exception spec and
improved execution in JIT-disabled environments.

---

## 2. JS-to-Wasm Interop

### The Boundary Crossing Cost

Every call between JavaScript and WebAssembly crosses an **ABI boundary**. The
engines use different calling conventions -- JS expects boxed values on the stack;
Wasm expects unboxed parameters in registers. The engine must:

1. **Unbox** JS values (extract raw numbers from tagged pointers)
2. **Move** values from the stack to registers (or vice versa)
3. **Set up** the Wasm/JS stack frame
4. **Box** return values back to JS representations

```
   JS Call to Wasm Function
   ┌──────────┐     ┌──────────────┐     ┌──────────────┐
   │ JS Code  │ ──> │ Entry Stub   │ ──> │ Wasm Function│
   │ (boxed   │     │ (unbox args, │     │ (unboxed     │
   │  values) │     │  switch ABI) │     │  registers)  │
   └──────────┘     └──────────────┘     └──────────────┘
                          ^
                          |
                    ~4.5ns per call
                    (Firefox, optimized)
```

### Measured Call Overhead (Firefox, 100M Iterations)

| Call Pattern | Before Optimization | After Optimization | Improvement |
|---|---|---|---|
| JS -> Wasm | ~5,500 ms | **~450 ms** | **12x** |
| Wasm -> JS | ~750 ms | **~450 ms** | 1.7x |
| JS -> Wasm (monomorphic) | ~5,250 ms | **~250 ms** | **21x** |
| Wasm -> Built-in | ~6,000 ms | **~650 ms** | 9x |

*Source: [Mozilla Hacks, 2018](https://hacks.mozilla.org/2018/10/calls-between-javascript-and-webassembly-are-finally-fast-%F0%9F%8E%89/) -- optimizations now standard in all engines.*

After optimization, **JS-to-Wasm calls are faster than non-inlined JS-to-JS
calls** in Firefox. At ~250ms / 100M calls, each monomorphic boundary crossing
costs approximately **2.5 nanoseconds** -- comparable to a virtual function dispatch
in native C++.

### Data Marshaling Costs

The call overhead is minimal for scalar values (numbers, booleans). The real
cost is in **data marshaling** for complex types:

| Data Type | Marshaling Strategy | Overhead |
|---|---|---|
| `i32`, `i64`, `f32`, `f64` | Direct register pass | **~2-5 ns** (negligible) |
| Strings | Copy into linear memory, pass pointer+length | **O(n)** -- significant for large strings |
| Arrays / TypedArrays | Share via linear memory view (zero-copy possible) | **Near-zero** if pre-allocated |
| Complex objects / JSON | Serialize -> copy -> deserialize | **Expensive** -- avoid in hot paths |
| `ArrayBuffer` / `SharedArrayBuffer` | Direct memory view (zero-copy) | **Zero** -- ideal pattern |

> **Key Insight:** The dominant cost is **not the call itself** but **data copying**.
> A Wasm function called 10,000 times per frame with scalar args adds ~25 us of
> overhead (insignificant at 60 fps = 16.6ms budget). But copying a 1MB buffer
> per call destroys any performance gain. **Design APIs to minimize boundary
> crossings with large data** -- pass pointers into shared linear memory, not copies.

### Practical Guidelines

| Call Frequency | Recommendation |
|---|---|
| < 100 calls/frame | Interop overhead is **invisible** |
| 100-10,000 calls/frame | Batch operations, prefer TypedArray views |
| > 10,000 calls/frame | Restructure: move the loop into Wasm, call once per frame |

---

## 3. Memory Model

### Linear Memory

Wasm's primary memory abstraction is a **contiguous, byte-addressable array**
called linear memory. It starts at zero, grows in 64 KiB pages, and is
bounds-checked on every access.

```
   WebAssembly Linear Memory Layout
   ┌────────────────────────────────────────────────────────┐
   │ 0x0000                                        0xFFFF  │
   │ ┌──────┬──────────┬───────────┬──────────────────────┐ │
   │ │ Stack│  Heap    │ Static    │   Unused / Growable  │ │
   │ │ (↓)  │  (↑)     │  Data     │                      │ │
   │ └──────┴──────────┴───────────┴──────────────────────┘ │
   │                                                        │
   │  Exposed to JS as: WebAssembly.Memory.buffer           │
   │  (ArrayBuffer or SharedArrayBuffer)                    │
   └────────────────────────────────────────────────────────┘
```

**Key properties:**
- **Bounds-checked**: Every load/store is validated against the current memory size.
  Out-of-bounds access traps (deterministic failure, not undefined behavior).
- **Isolated**: Each module gets its own linear memory. No pointer arithmetic can
  reach outside it.
- **Growable**: `memory.grow(n)` adds `n` pages (64 KiB each). Growth can fail
  (returns -1) if the engine runs out of address space.
- **JS-accessible**: `WebAssembly.Memory.buffer` exposes it as an `ArrayBuffer`,
  enabling zero-copy data sharing via `TypedArray` views.

### Memory64 (Wasm 3.0)

Wasm 3.0 introduced **Memory64**, changing the address type from `i32` to `i64`.
This expands the theoretical address space from **4 GB to 16 exabytes**, critical
for large AI model inference in the browser and big-data processing.

| Feature | Wasm MVP | Wasm 3.0 (Memory64) |
|---|---|---|
| Address width | 32-bit | 64-bit |
| Max addressable | 4 GB | 16 EB (theoretical) |
| Browser support | All | Chrome 133+, Firefox 134+, Safari 18.4+ |

### Shared Memory (SharedArrayBuffer)

When a `WebAssembly.Memory` is created with `shared: true`, it is backed by a
**SharedArrayBuffer** instead of an ArrayBuffer. This enables:

- Multiple Web Workers reading/writing the same memory
- Atomic operations via `Atomics.*` and Wasm atomic instructions
- True shared-state concurrency (not message-passing)

**Requirements:**
- Cross-Origin Isolation headers (`Cross-Origin-Opener-Policy: same-origin`,
  `Cross-Origin-Embedder-Policy: require-corp`)
- HTTPS (localhost exempt for development)

### WasmGC (Garbage Collection) -- Wasm 3.0

The GC proposal, standardized in Wasm 3.0 and shipping in **Chrome 119+,
Firefox 120+, Safari 18.2+**, adds engine-managed reference types:

| Concept | Description |
|---|---|
| **Struct types** | Define named fields with typed values (like C structs) |
| **Array types** | Homogeneous, length-tracked, GC-managed |
| **Reference types** | Typed pointers to GC-managed objects |
| **Subtyping** | Structural subtype checking |
| **Casts** | Runtime type checks and downcasts |

**Before WasmGC:** Languages like Java, Kotlin, or Dart had to ship their own GC
implementation compiled to Wasm, operating over linear memory. This meant
**duplicating GC logic** already present in the browser engine, resulting in larger
binaries and slower collection.

**After WasmGC:** These languages emit `struct.new`, `array.new`, and `ref.cast`
instructions that use the **browser's native GC** (the same one that manages JS
objects). Google Sheets' migration to WasmGC achieved a **2x speedup** by
eliminating this overhead.

> **Key Insight:** WasmGC is the single biggest enabler for managed languages
> (Java, Kotlin, Dart, C#, OCaml) targeting the browser. It eliminates the "bring
> your own GC" tax that previously made these languages impractical for web Wasm.
> For C/C++/Rust (which manage their own memory), WasmGC is largely irrelevant --
> they continue using linear memory with `malloc`/`free` or ownership semantics.

---

## 4. Threading

### Current Architecture: Web Workers + SharedArrayBuffer + Atomics

Wasm threading in the browser is built on three primitives:

```
   Wasm Threading Architecture
   ┌───────────────────────────────────────────────────────────┐
   │  Main Thread                                              │
   │  ┌─────────────┐                                         │
   │  │ JS + Wasm   │                                         │
   │  │ instance    │                                         │
   │  └──────┬──────┘                                         │
   │         │ postMessage() to create workers                │
   │         │                                                 │
   │    SharedArrayBuffer (shared linear memory)              │
   │    ┌────────────────────────────────────────┐            │
   │    │  0x0000 ──────────────────── 0xFFFF    │            │
   │    │  Atomics.wait() / Atomics.notify()     │            │
   │    └────────┬───────────┬───────────┬───────┘            │
   │             |           |           |                     │
   │   ┌─────────┴──┐ ┌─────┴──────┐ ┌──┴──────────┐        │
   │   │ Worker 1   │ │ Worker 2   │ │ Worker N    │        │
   │   │ Wasm inst. │ │ Wasm inst. │ │ Wasm inst.  │        │
   │   └────────────┘ └────────────┘ └─────────────┘        │
   └───────────────────────────────────────────────────────────┘
```

### Synchronization Primitives

| Primitive | Level | Description |
|---|---|---|
| `Atomics.wait()` | JS | Blocks calling thread until notified (cannot block main thread) |
| `Atomics.notify()` | JS | Wakes waiting threads |
| `Atomics.load/store` | JS | Atomic read/write of shared memory cells |
| `Atomics.compareExchange` | JS | CAS operation for lock-free data structures |
| `i32.atomic.load` / `i32.atomic.store` | Wasm | Wasm-level atomic memory operations |
| `memory.atomic.wait32` | Wasm | Wasm-level futex-like wait |
| `memory.atomic.notify` | Wasm | Wasm-level wake |

### Emscripten pthreads

Emscripten provides a **full pthreads implementation** built on Web Workers +
SharedArrayBuffer. C/C++ code using `pthread_create`, `pthread_mutex_lock`,
`pthread_cond_wait`, etc., compiles to Wasm with no source changes.

Each pthread maps to a Web Worker. The shared Wasm memory is backed by a
SharedArrayBuffer. Mutex/condvar operations compile to `Atomics.wait/notify`.

### Browser Support & Caveats

| Feature | Chrome | Firefox | Safari |
|---|---|---|---|
| SharedArrayBuffer | 68+ | 79+ | 15.2+ |
| Wasm Threads (atomics) | 74+ | 79+ | 15.2+ |
| Cross-origin isolation required | Yes | Yes | Yes |

**Caveats:**
- **Main thread cannot block**: `Atomics.wait()` throws on the main thread.
  Work must be dispatched to workers.
- **Worker startup cost**: Creating a Web Worker has ~5-50ms overhead.
  Pre-create a **worker pool** for latency-sensitive applications.
- **No thread migration**: A worker cannot move to a different core.
  The OS scheduler decides.
- **Memory overhead**: Each worker gets its own JS heap + stack.
  Typical per-worker cost: **2-8 MB**.

> **Key Insight:** True multi-threaded Wasm is production-ready but requires
> **cross-origin isolation headers** that break some third-party integrations
> (iframes, CDN resources without CORP headers). Audit your dependency chain
> before enabling. The headers are: `Cross-Origin-Opener-Policy: same-origin`
> and `Cross-Origin-Embedder-Policy: require-corp`.

---

## 5. SIMD

### What Wasm SIMD Provides

Wasm SIMD (Single Instruction, Multiple Data) operates on **128-bit vectors**,
processing 4x `f32`, 2x `f64`, 4x `i32`, 8x `i16`, or 16x `i8` values in
a single instruction. The instruction set includes:

| Category | Operations | Example |
|---|---|---|
| **Arithmetic** | add, sub, mul, div, neg, abs, sqrt | `f32x4.mul` -- 4 floats multiplied simultaneously |
| **Comparison** | eq, ne, lt, gt, le, ge | `i32x4.gt_s` -- 4 signed 32-bit compares |
| **Bitwise** | and, or, xor, not, andnot | `v128.and` -- 128-bit AND |
| **Shuffle** | swizzle, shuffle | `i8x16.shuffle` -- arbitrary lane reordering |
| **Conversion** | extend, narrow, trunc, convert | `f32x4.convert_i32x4_s` -- int to float |
| **Load/Store** | load, store, splat, extract, replace | `v128.load` -- 128-bit aligned load |
| **Dot product** | `i32x4.dot_i16x8_s` | 16-bit packed integer dot product |

### Browser Support

| Feature | Chrome | Firefox | Safari | Standardized |
|---|---|---|---|---|
| **Fixed-width SIMD (128-bit)** | 91+ | 89+ | 16.4+ | Wasm 3.0 |
| **Relaxed SIMD** | 114+ | Unflagged 2025 | Behind flag | Phase 4 |

**Relaxed SIMD** adds operations that are allowed to differ between architectures
(e.g., fused multiply-add, relaxed swizzle), enabling better mapping to native
SIMD instructions at the cost of strict determinism.

### Measured Performance Gains

| Workload | JS Baseline | Wasm + SIMD | Speedup | Source |
|---|---|---|---|---|
| Array operations | 1.4 ms | 0.231 ms | **6x** | [byteiota, 2025](https://byteiota.com/rust-webassembly-performance-8-10x-faster-2025-benchmarks/) |
| Matrix multiplication | Baseline | +SIMD | **9.5x** | [byteiota, 2025](https://byteiota.com/rust-webassembly-performance-8-10x-faster-2025-benchmarks/) |
| Game engine (Godot) | Baseline | +Wasm SIMD | **1.5-2x** (frame resilience) | [Godot Engine](https://godotengine.org/article/upcoming-serious-web-performance-boost/) |
| Scientific computing (Node 22) | Baseline | +SIMD | **10x** | [markaicode, 2025](https://markaicode.com/nodejs-22-webassembly-simd-scientific-computing/) |
| Image processing | Baseline | +SIMD | **4-8x** | Various benchmarks |

> **Key Insight:** Peak SIMD benchmarks (10-15x) represent best-case scenarios
> on perfectly vectorizable code. **Real-world applications typically see 1.5-4x**
> from SIMD alone because not all code paths vectorize, memory bandwidth becomes
> the bottleneck, and branch-heavy logic doesn't benefit. The Godot engine's
> measured **1.5-2x** is more representative of complex application performance.
> Still, that means the difference between 30fps and 60fps for a game engine.

---

## 6. Toolchains

### Comparison Matrix

| Toolchain | Source Lang | Binary Size (sort benchmark) | Execution Time (Chrome) | Maturity | Best For |
|---|---|---|---|---|---|
| **wasm-pack + wasm-bindgen** (Rust) | Rust | 74 KB (44 KB .wasm + 30 KB JS) | **2,982 ms** | Production | Performance-critical modules |
| **Emscripten** | C/C++ | 100-500 KB+ (with runtime) | ~3,000-3,500 ms | Production (20+ years of C/C++ porting) | Porting existing C/C++ codebases |
| **AssemblyScript** | TypeScript-like | **4.7 KB** (3.5 KB .wasm + 1.2 KB) | 6,405 ms | Stable | Small modules, JS teams |
| **TinyGo** | Go | 37 KB (20 KB .wasm + 17 KB) | 9,717 ms | Beta | Go developers, lightweight tasks |
| **Zig** (native Wasm target) | Zig | ~15-50 KB | ~3,200 ms (estimated) | Alpha/Beta | Cross-compilation, C interop |
| **Go (standard)** | Go | 1-10 MB+ | Variable | Stable but large | Full Go runtime needed |

*Benchmark: 100K random values, copied 500x, stable-sorted each time, 5 repetitions. Intel MacBook Pro 2019.*
*Source: [Ecostack, 2022](https://ecostack.dev/posts/wasm-tinygo-vs-rust-vs-assemblyscript/)*

### Cross-Browser Execution Time (ms, Lower = Better)

| Toolchain | Chrome | Firefox | Edge |
|---|---|---|---|
| **Rust (wasm-pack)** | **2,982** | 3,582 | 3,306 |
| **AssemblyScript** | 6,405 | 6,152 | 6,882 |
| **TinyGo** | 9,717 | 10,668 | 9,546 |
| **JS (typed arrays)** | 4,904 | -- | -- |
| **JS (dynamic)** | 68,720 | -- | -- |

### Toolchain Deep Dives

**Emscripten** -- The veteran. Compiles C/C++ via LLVM to Wasm. Provides a
complete POSIX-like environment (virtual filesystem, GL emulation, pthreads
via Web Workers). Output includes a `.wasm` file plus a JS "glue" file that
handles memory setup, function exports, and browser API bridging. Best choice
for **porting existing C/C++ codebases** (used by Figma, AutoCAD, Photoshop web).
Supports `-Os` / `-Oz` flags for size-optimized builds.

**wasm-pack (Rust)** -- The performance champion. Rust's `wasm32-unknown-unknown`
target produces minimal Wasm binaries. `wasm-bindgen` generates JS/TS interop
bindings. `wasm-pack` orchestrates the build, runs `wasm-opt`, and produces
npm-publishable packages. Rust with raw Wasm exports (bypassing wasm-bindgen
overhead) achieves **8-10x over JS**; with wasm-bindgen, **3-5x**.

**AssemblyScript** -- TypeScript syntax, Wasm semantics. Compiles a strict
subset of TypeScript directly to Wasm without LLVM. Produces the **smallest
binaries** by far (4.7 KB total for the sort benchmark). Performance is ~2x
slower than Rust but the DX for JS-native teams is unmatched. Ideal for
**small, targeted compute kernels** where binary size matters.

**TinyGo** -- Compiles Go to Wasm using a custom compiler (not the standard
Go toolchain). Produces much smaller binaries than standard Go (37 KB vs 1-10 MB)
but is **3-4x slower than Rust**. Not all Go standard library packages are supported.
Good for teams invested in Go who need occasional browser-side compute.

**Zig** -- Native Wasm32 target via its self-hosted backend (LLVM backend also
available). Zig's cross-compilation story is strong -- "pretty much everything
compiles out of the box to all supported targets." C interop is excellent (Zig
can compile C headers directly). Still maturing for Wasm specifically, but
promising for teams that want C-like control without C's toolchain pain.

---

## 7. Language Tradeoffs

### Decision Matrix for Wasm Target Language

| Factor | Rust | C/C++ | Zig | AssemblyScript | TinyGo |
|---|---|---|---|---|---|
| **Runtime perf** | Excellent | Excellent | Excellent | Good | Fair |
| **Binary size** | Good (44 KB) | Variable (depends on runtime) | Good (~15-50 KB) | Excellent (3.5 KB) | Good (20 KB) |
| **Memory safety** | Compile-time (borrow checker) | Manual (foot-gun heavy) | Optional runtime checks | GC-managed | GC-managed |
| **Learning curve** | Steep (ownership model) | Moderate-High | Moderate | Low (TypeScript-like) | Low (Go) |
| **Wasm ecosystem** | Excellent (wasm-pack, wasm-bindgen) | Excellent (Emscripten, 20+ years) | Early but growing | Good (dedicated compiler) | Moderate (subset of stdlib) |
| **Existing code reuse** | Crates ecosystem | Massive (decades of C/C++ libs) | C libraries via built-in interop | JS/TS patterns | Go packages (subset) |
| **SIMD support** | Full (std::simd, intrinsics) | Full (intrinsics, auto-vectorization) | Full (LLVM backend) | Limited | Limited |
| **Threading** | Full (std::thread -> pthreads) | Full (pthreads via Emscripten) | Yes | No | Limited |
| **Debug experience** | DWARF in Chrome DevTools | DWARF in Chrome DevTools | Basic | Source maps | Basic |
| **Hiring pool** | Growing rapidly | Large | Small | Large (TS developers) | Moderate |

### Recommendations by Team Profile

| Team Background | Recommended Language | Rationale |
|---|---|---|
| **Systems / performance team** | Rust | Best perf + safety, rich Wasm tooling |
| **Existing C/C++ codebase** | C/C++ (Emscripten) | Port without rewrite, proven path |
| **Frontend / TypeScript team** | AssemblyScript | Familiar syntax, smallest output, lowest friction |
| **Go backend team** | TinyGo | Leverage existing knowledge, accept perf tradeoff |
| **New greenfield project** | Rust or Zig | Rust for ecosystem; Zig for simplicity + C interop |

---

## 8. WASI and Component Model

### What They Are

**WASI (WebAssembly System Interface)** defines a standard set of system-level
APIs (file I/O, networking, clocks, random) for Wasm modules running **outside
the browser**. Think of it as a portable POSIX for Wasm.

**The Component Model** builds on WASI to define a standard for Wasm module
composition -- how modules expose and consume typed interfaces, how they link
together, and how they communicate without shared memory.

### Timeline

| Milestone | Date | Status |
|---|---|---|
| WASI 0.2 (Preview 2) | Early 2024 | Shipped |
| WASI 0.3.0 (async support) | February 2026 | **Just shipped** |
| WASI 1.0 | Late 2026 / Early 2027 | Expected |
| Component Model | Advancing alongside WASI 0.3/1.0 | Active development |

### Browser Relevance

WASI was created specifically to extend Wasm **beyond** the browser sandbox.
In the browser, Wasm already has access to Web APIs via JavaScript glue.
Direct browser relevance is limited today, but two aspects matter:

1. **Code portability**: A Wasm module compiled with WASI can run in the
   browser (with a WASI polyfill like `@aspect-run/aspect-wasi` or
   `browser_wasi_shim`), on the server (Wasmtime, WasmEdge), and at
   the edge (Cloudflare Workers, Fastly Compute). **Write once, run anywhere**
   becomes real.

2. **Component Model for the browser**: WIT (WebAssembly Interface Types)
   defines typed contracts between modules, potentially eliminating JS glue
   code for Wasm-to-Wasm communication. This is relevant for **micro-frontend
   architectures** where multiple teams ship independent Wasm components.

> **Key Insight:** For browser-focused compute-heavy operations, WASI is
> **not directly relevant** today. Its value is in portability: the same Wasm
> module that processes data in the browser can also run server-side for SSR,
> testing, or batch processing. If you are building browser-only Wasm modules,
> you can ignore WASI for now. If you want portable compute logic, target WASI.

---

## 9. Binary Size Optimization

### Why Size Matters

Wasm binaries are downloaded, compiled, and instantiated before they can
execute. While streaming compilation helps (compilation begins during download),
**smaller binaries still mean faster time-to-interactive**.

Rule of thumb: **Wasm compiles ~10x faster than JS per byte** because
validation is a single linear pass. A 1 MB Wasm file compiles in roughly
the time it takes to parse 100 KB of JavaScript.

### Optimization Techniques

| Technique | Tool / Flag | Size Reduction | Perf Impact |
|---|---|---|---|
| **wasm-opt -Oz** | Binaryen | **Up to 90%** (extreme cases), typically 15-30% | Slight perf decrease |
| **wasm-opt -O3** | Binaryen | 10-20% | Perf improvement |
| **LTO (Link-Time Optimization)** | Compiler flag (`-C lto=true` in Rust) | 10-25% | Slight perf improvement |
| **Strip debug info** | `wasm-strip` / compiler flags | 30-60% of debug builds | None |
| **Compiler size flags** | `-Os` / `-Oz` (Emscripten), `opt-level = "z"` (Rust) | 10-30% | Minor perf cost |
| **Tree shaking / DCE** | wasm-opt, compiler DCE passes | 5-20% | None |
| **gzip / brotli compression** | Web server | **60-80%** of transfer size | Decompression cost (minimal) |
| **Streaming compilation** | `WebAssembly.compileStreaming()` | N/A (latency reduction) | Compiles during download |
| **Binary splitting** | Leptos `#[lazy]` macros (Rust) | Load only what's needed | None |
| **wasm-snip** | Remove unreachable functions | 5-15% | None |

### Rust-Specific Size Optimization Checklist

```toml
# Cargo.toml
[profile.release]
opt-level = "z"       # Optimize for size
lto = true            # Enable link-time optimization
codegen-units = 1     # Better optimization (slower compile)
panic = "abort"       # Remove panic unwinding code
strip = true          # Strip debug symbols
```

```bash
# Post-build optimization
wasm-opt -Oz -o output.wasm input.wasm
wasm-strip output.wasm
```

### Compression Impact (Typical 500 KB Wasm Module)

| Stage | Size | Notes |
|---|---|---|
| Debug build | 2-5 MB | Includes DWARF, names section |
| Release build | 500 KB | Compiler optimizations applied |
| After `wasm-opt -Oz` | 350 KB | Binaryen passes |
| After `wasm-strip` | 300 KB | Debug info removed |
| Brotli compressed (transfer) | **60-90 KB** | What the user actually downloads |

> **Key Insight:** The combination of `wasm-opt -Oz` + Brotli compression
> typically reduces a release Wasm binary to **15-20% of its unoptimized size**
> on the wire. Always serve Wasm with `Content-Type: application/wasm` to enable
> streaming compilation, and ensure your CDN applies Brotli or gzip.

---

## 10. Security Model

### Wasm's Sandboxing Architecture

WebAssembly's security model is fundamentally different from JavaScript's.
Rather than trying to restrict a powerful runtime, Wasm starts with
**zero capabilities** and only gains access to what the host explicitly provides.

```
   Security Model Comparison
   ┌──────────────────────────────────┐    ┌──────────────────────────────────┐
   │          JavaScript              │    │         WebAssembly              │
   │                                  │    │                                  │
   │  ┌───────────────────────────┐   │    │  ┌───────────────────────────┐   │
   │  │ Full Web API access       │   │    │  │ NO Web API access         │   │
   │  │ DOM, fetch, localStorage  │   │    │  │ NO DOM, NO fetch          │   │
   │  │ eval(), Function()        │   │    │  │ NO code generation        │   │
   │  │ Prototype chain access    │   │    │  │ NO prototype access       │   │
   │  │ Global object access      │   │    │  │ NO global object          │   │
   │  └───────────────────────────┘   │    │  └───────────────────────────┘   │
   │                                  │    │                                  │
   │  Security: RESTRICT what the     │    │  Security: GRANT only what the   │
   │  runtime can do (blacklist)      │    │  host provides (whitelist)       │
   └──────────────────────────────────┘    └──────────────────────────────────┘
```

### Security Properties

| Property | JavaScript | WebAssembly |
|---|---|---|
| **Memory access** | Shared heap, prototype chain | Isolated linear memory, bounds-checked |
| **Code generation** | `eval()`, `Function()`, `import()` | None -- binary is validated at load time |
| **System access** | Web APIs (restricted by browser) | Nothing unless host imports functions |
| **Type safety** | Dynamic types, coercion | Statically typed, validated instructions |
| **Control flow** | Arbitrary (closures, eval, prototype manip) | Structured (validated branch targets) |
| **Same-origin policy** | Applies | Applies (inherits from embedding context) |

### Capability-Based Model (WASI)

WASI enforces a **capability-based security model**: a Wasm module can only
access files, directories, or network resources that are **explicitly granted**
as capabilities by the host. This inverts the traditional POSIX model where
a process has ambient authority to access anything the user can.

**In the browser**, Wasm inherits the same origin-based security as its
embedding page. It cannot make network requests, access the DOM, or read
cookies directly -- all such operations must go through JS-imported functions,
which the developer controls.

### Known Attack Surfaces

| Attack Vector | Risk Level | Mitigation |
|---|---|---|
| **Memory corruption within linear memory** | Medium | Bounded -- cannot escape sandbox, but can corrupt Wasm-internal state |
| **Control flow hijack (ROP-style)** | Low | Possible via indirect call table manipulation; mitigated by structured control flow |
| **Side-channel (Spectre)** | Low-Medium | SharedArrayBuffer + high-res timers; mitigated by cross-origin isolation |
| **Supply chain (malicious .wasm)** | Medium | Same as JS supply chain risk; SRI hashes, auditing |
| **Sandbox escape (engine bugs)** | Very Low | Rare but critical (e.g., CVE-2023-6699 in V8); keep browsers updated |

> **Key Insight:** Wasm's security model is **stronger than JavaScript's by design**
> because it starts with zero capabilities. However, in practice, most Wasm modules
> are given JS-imported functions that bridge to Web APIs, so the effective security
> boundary is the **quality of those imports**. A poorly written JS glue layer that
> passes raw user input to Wasm linear memory without validation can still create
> vulnerabilities. The sandbox protects the **host** from the **module**, not the
> module from bad inputs.

---

## 11. Debugging and Profiling

### Current State of Tooling (2025-2026)

Wasm debugging has matured significantly. Chrome DevTools provides the most
complete experience, with Firefox close behind.

| Feature | Chrome DevTools | Firefox DevTools | VS Code |
|---|---|---|---|
| **Step through original source** (C++/Rust) | DWARF (since Chrome 114, no flags needed) | Source maps | Via browser bridge |
| **Set breakpoints in source** | Yes | Yes | Via browser bridge |
| **Inspect variables** | Yes (DWARF-based) | Partial | Partial |
| **Memory inspector** | Yes (linear memory viewer) | Yes | No |
| **Performance profiling** | Performance tab (function-level) | Performance tab | N/A |
| **Wasm-specific inspection** | `.wat` disassembly view | `.wat` disassembly view | N/A |
| **Network timing** | Streaming compilation metrics | Basic | N/A |

### Chrome DevTools: The Gold Standard

Starting with Chrome 114, **no experimental flags** are needed to debug Wasm.
When a `.wasm` file includes DWARF debug info (or a separate `.dwarf` file
linked via a custom section), Chrome DevTools will:

1. Show the **original source code** (C++, Rust, etc.) in the Sources panel
2. Allow setting **line-of-code breakpoints** in the original source
3. Display **variable values** with original names and types
4. Show the **call stack** with original function names

**V8 compilation behavior during debugging:**
- When DevTools opens: V8 **tiers down** to Liftoff (baseline) to maintain
  instruction-to-source mapping
- When profiling in DevTools: V8 **tiers up** to TurboFan so profiling results
  are representative of production performance

### Profiling Wasm Performance

```
   Profiling Workflow
   ┌─────────────────────────────────────────────────────────┐
   │  1. Build with debug info:                              │
   │     rustc --target wasm32 -g    (keeps DWARF)          │
   │     emcc -g4 -gsource-map      (generates source map)  │
   │                                                         │
   │  2. Profile in Chrome DevTools:                         │
   │     Performance tab → Record → Exercise workload        │
   │     → See Wasm function names in flame chart            │
   │                                                         │
   │  3. Measure compilation:                                │
   │     chrome://tracing with v8.wasm categories            │
   │     → wasm.BaselineFinished (Liftoff time)             │
   │     → wasm.TopTierFinished (TurboFan time)             │
   │                                                         │
   │  4. Inspect memory:                                     │
   │     Memory Inspector panel → view linear memory         │
   │     → TypedArray overlay for structured inspection      │
   └─────────────────────────────────────────────────────────┘
```

### Source Map vs. DWARF

| Approach | Format | Used By | Pros | Cons |
|---|---|---|---|---|
| **DWARF** | Binary debug format (standard in native tooling) | Chrome, Emscripten (`-g`), Rust (`-g`) | Full variable inspection, type info, rich | Larger debug files, Chrome-focused |
| **Source Maps** | JSON mapping format | Firefox, AssemblyScript | Familiar to web devs, broad tool support | Less type info, no variable inspection |

> **Key Insight:** For production profiling, **always build two artifacts**:
> a stripped release build for deployment and a debug build with DWARF info for
> investigation. Never profile debug builds -- V8 tiers down to Liftoff and the
> results are not representative. Chrome's DevTools correctly tiers up for
> profiling, but be aware that DevTools overhead itself can skew results for
> very tight loops. For micro-benchmarks, use `performance.now()` wrapping.

---

## 12. Emerging Proposals

### WebAssembly 3.0 (Shipped September 2025)

The Wasm 3.0 specification is now the **live standard**, bundling everything
that was previously separate proposals:

| Feature | Description | Status |
|---|---|---|
| **Exception Handling** (`exnref`) | Native try/catch/throw with typed exception tags | All browsers |
| **Tail Calls** | `return_call` / `return_call_indirect` for TCO | All browsers |
| **GC (struct/array types)** | Engine-managed garbage-collected reference types | All browsers |
| **Memory64** | 64-bit memory addressing (>4GB linear memory) | Chrome 133+, Firefox 134+, Safari 18.4+ |
| **Multiple Memories** | More than one linear memory per module | All browsers |
| **Extended Const Expressions** | More expressions in global/element initializers | All browsers |
| **Relaxed SIMD** | Architecture-dependent SIMD operations for perf | Chrome 114+, Firefox (2025), Safari (flag) |

### Post-3.0 Proposals in Progress

| Proposal | Phase | Description | Impact |
|---|---|---|---|
| **Stack Switching** | Phase 3 | Lightweight coroutines, green threads, async/await without code transform | High -- enables goroutine-style concurrency in Wasm |
| **Branch Hinting** | Phase 4 | Hint to compiler which branches are likely/unlikely | Low -- micro-optimization for hot loops |
| **Threads (shared-everything)** | Phase 2 | Full shared-memory threading without Web Workers | Very High -- would enable true multi-threading |
| **Type Reflection** | Phase 1-2 (demoted) | Inspect Wasm module types from JS | Low -- no active champion, stalled |
| **Memory Control** | Phase 1 | `memory.discard` to release physical pages | Medium -- helps memory-constrained environments |
| **JS String Builtins** | Phase 4 | Direct access to JS string operations from Wasm | Medium -- faster string interop |
| **Flexible Vectors** | Phase 1 | SIMD wider than 128-bit (256, 512) | High -- would unlock AVX2/AVX-512 level perf |
| **Multiple Return Values** | Shipped (Wasm 2.0) | Functions return multiple values | Already available |

### What to Watch

**Stack Switching** is the most impactful upcoming proposal. It would allow Wasm
to suspend and resume execution without OS-level threads, enabling:
- Lightweight "green threads" (like Go goroutines)
- Cooperative multitasking within a single Web Worker
- Efficient async/await compilation for languages that have it
- Dramatically reduced overhead for concurrent workloads

**Shared-everything threads** would be transformative but is years away.
Currently, each Web Worker runs a separate Wasm instance sharing only
linear memory. Full shared-everything would allow threads to share
functions, tables, and GC objects.

---

## 13. Where Wasm Beats JS -- and Where It Doesn't

### Performance Crossover Analysis

Research from [BenchmarkingWebAssembly](https://benchmarkingwasm.github.io/BenchmarkingWebAssembly/)
reveals a nuanced picture that depends heavily on **input size** and **workload type**:

| Input Size | Wasm Speedup vs JS | Notes |
|---|---|---|
| Extra-small | **26.99x** | Wasm's typed operations dominate; JS engine hasn't had time to optimize |
| Small | **8.22x** | Clear Wasm advantage |
| Medium | **Mixed** -- some benchmarks Wasm is 1.71x *slower* | V8's TurboFan catches up; interop overhead becomes visible |
| Large | **Moderate advantage** (2-4x typical) | Memory overhead grows (+24 MB for Wasm) |
| Extra-large | **Moderate advantage** | Memory overhead grows (+74 MB for Wasm) |

### Where Wasm Wins Decisively

| Workload | Why Wasm Wins | Real-World Example |
|---|---|---|
| **Tight numeric loops** | Predictable types, no GC pauses, SIMD | Image/audio processing filters |
| **Cryptography** | Constant-time operations, no JIT deopt | libsodium compiled to Wasm |
| **Codecs / compression** | Bit manipulation, no object allocation | FFmpeg, Brotli, zstd in browser |
| **Physics / simulation** | Matrix math, SIMD, deterministic floats | Game engines (Unity, Godot, Unreal) |
| **Porting native code** | Existing C/C++/Rust already optimized | Figma, AutoCAD, Photoshop web |
| **AI / ML inference** | Matrix operations, SIMD, threading | TensorFlow.js Wasm backend, ONNX Runtime Web |
| **Parsing / compilation** | Deterministic control flow, no deopt | Tree-sitter, SQLite in browser |

### Where JS Wins or Ties

| Workload | Why JS Wins | Explanation |
|---|---|---|
| **DOM manipulation** | Wasm has no DOM access; must call through JS | Every DOM call crosses the interop boundary |
| **Small/simple logic** | V8/SpiderMonkey optimize JS extremely well | JIT-compiled JS is already near-native for simple operations |
| **String-heavy operations** | Wasm linear memory lacks native string support | JS strings are engine-native; Wasm must manage encoding |
| **Async I/O / network** | Wasm cannot call Web APIs directly | `fetch()`, WebSocket, IndexedDB -- all go through JS |
| **Object-heavy code** | JS objects are engine-optimized (hidden classes) | Wasm structs in linear memory have no engine-level optimization (pre-WasmGC) |
| **Rapid prototyping** | JS is interpreted with instant feedback | No compile step, instant reload |

### Decision Framework

```
   Should You Use Wasm?
                                   ┌──────────────────┐
                                   │ Is the workload   │
                                   │ CPU-bound?         │
                                   └────────┬──────────┘
                                        ┌───┴───┐
                                      Yes       No ──> Stick with JS
                                        |
                                   ┌────┴──────────────┐
                                   │ Is it >1ms of      │
                                   │ sustained compute? │
                                   └────────┬──────────┘
                                        ┌───┴───┐
                                      Yes       No ──> JS is fine
                                        |
                                   ┌────┴──────────────┐
                                   │ Existing C/C++/    │
                                   │ Rust code to port? │
                                   └────────┬──────────┘
                                        ┌───┴───┐
                                      Yes       No
                                        |         |
                                   Use Wasm    ┌──┴──────────────┐
                                   (port it)   │ Need SIMD or     │
                                               │ threading?       │
                                               └────────┬────────┘
                                                   ┌────┴───┐
                                                 Yes        No ──> Benchmark first.
                                                   |               JS might be fast enough.
                                              Use Wasm
                                              (write new)
```

---

## 14. Integration Patterns

### Pattern 1: Thin Wasm Kernel + JS Glue (Recommended for Most)

The most common and practical pattern. Wasm handles the compute-intensive
core; JavaScript handles everything else.

```
   ┌─────────────────────────────────────────────────────────────┐
   │  Browser                                                    │
   │                                                             │
   │  ┌─────────────────────────────────────────────────┐       │
   │  │  JavaScript Layer                               │       │
   │  │  - DOM rendering (React, Svelte, vanilla, etc.) │       │
   │  │  - Event handling                               │       │
   │  │  - Network I/O (fetch, WebSocket)               │       │
   │  │  - State management                             │       │
   │  │  - Routing, auth, UI logic                      │       │
   │  └───────────────────────┬─────────────────────────┘       │
   │                          │                                  │
   │                  JS ←→ Wasm boundary                       │
   │                  (TypedArray views into                     │
   │                   shared linear memory)                     │
   │                          │                                  │
   │  ┌───────────────────────┴─────────────────────────┐       │
   │  │  Wasm Kernel                                    │       │
   │  │  - Image processing                             │       │
   │  │  - Physics simulation                           │       │
   │  │  - Codec encoding/decoding                      │       │
   │  │  - Crypto operations                            │       │
   │  │  - Data transformation                          │       │
   │  └─────────────────────────────────────────────────┘       │
   └─────────────────────────────────────────────────────────────┘
```

**Pros:** Minimal disruption, use existing JS framework, Wasm only where it helps.
**Cons:** Interop overhead for frequent calls, two build systems.

**Who uses this:** Most production Wasm users. Squoosh (image compression),
TensorFlow.js (ML inference backend), libsodium.js (crypto).

### Pattern 2: Full Wasm Application

The entire application runs in Wasm. JS is minimal -- just the bootstrap
loader and Web API bridges. Used for porting desktop applications to the web.

```
   ┌─────────────────────────────────────────────────────────────┐
   │  Browser                                                    │
   │                                                             │
   │  ┌──────────────┐                                          │
   │  │ JS Bootstrap │  (~1 KB: instantiate module, bridge APIs)│
   │  └──────┬───────┘                                          │
   │         │                                                   │
   │  ┌──────┴──────────────────────────────────────────┐       │
   │  │  Full Wasm Application                          │       │
   │  │  - UI rendering (Canvas/WebGL/WebGPU)           │       │
   │  │  - Application logic                            │       │
   │  │  - State management                             │       │
   │  │  - File handling (virtual FS via Emscripten)    │       │
   │  └─────────────────────────────────────────────────┘       │
   └─────────────────────────────────────────────────────────────┘
```

**Pros:** Single language/toolchain, leverage existing native codebase.
**Cons:** Large binary sizes (often 5-30 MB), no DOM access (canvas only),
longer initial load, harder to integrate with web ecosystem.

**Who uses this:** Figma (C++ engine), AutoCAD Web, Photoshop Web,
game engines (Unity, Godot, Unreal).

### Pattern 3: Hybrid Worker Architecture

Wasm runs in a Web Worker for heavy computation, communicating with the
main thread via `postMessage` or `SharedArrayBuffer`. The main thread
stays responsive for UI.

```
   ┌─────────────────────────────────────────────────────────────┐
   │  Main Thread                          Worker Thread(s)      │
   │  ┌────────────────────┐              ┌──────────────────┐  │
   │  │  JS UI Layer       │  postMessage │  Wasm Compute    │  │
   │  │  - DOM rendering   │ <──────────> │  - Heavy math    │  │
   │  │  - User input      │     or       │  - Data crunch   │  │
   │  │  - Display results │  SharedArray │  - ML inference  │  │
   │  └────────────────────┘   Buffer     └──────────────────┘  │
   │                                      ┌──────────────────┐  │
   │                                      │  Wasm Worker #2  │  │
   │                                      │  (parallel task) │  │
   │                                      └──────────────────┘  │
   └─────────────────────────────────────────────────────────────┘
```

**Pros:** Main thread never blocks, true parallelism, best for sustained
compute (video encoding, large dataset processing).
**Cons:** Async communication adds latency, SharedArrayBuffer requires
cross-origin isolation headers, worker pool management complexity.

**Who uses this:** Video editors, real-time audio processing, large-scale
data visualization, AI inference.

### Pattern 4: Progressive Enhancement

Start with JS; swap in Wasm for specific functions when available and
when the workload justifies it.

```javascript
// Progressive enhancement pattern
async function processImage(data) {
  if (wasmModule) {
    // Fast path: Wasm with SIMD
    const ptr = wasmModule.alloc(data.byteLength);
    new Uint8Array(wasmModule.memory.buffer, ptr, data.byteLength).set(data);
    wasmModule.processImage(ptr, data.byteLength);
    return new Uint8Array(wasmModule.memory.buffer, ptr, data.byteLength).slice();
  } else {
    // Fallback: JS implementation
    return jsProcessImage(data);
  }
}
```

**Pros:** Graceful degradation, works everywhere, Wasm is a pure
performance upgrade.
**Cons:** Maintaining two implementations, testing complexity.

### Choosing a Pattern

| Criterion | Thin Kernel | Full Wasm App | Hybrid Worker | Progressive |
|---|---|---|---|---|
| **Existing JS codebase** | Best | Poor | Good | Good |
| **Porting native app** | Poor | Best | Good | Poor |
| **Real-time compute** | Good | Good | Best | Good |
| **Initial load time** | Best | Worst | Good | Best |
| **Team skill requirement** | Low | High (C++/Rust) | Medium | Medium |
| **Browser compatibility** | Excellent | Good | Needs COOP/COEP | Excellent |

---

## 15. Sources

### Official Documentation & Specifications
- [V8 WebAssembly Compilation Pipeline](https://v8.dev/docs/wasm-compilation-pipeline)
- [V8 Liftoff: Baseline Compiler for WebAssembly](https://v8.dev/blog/liftoff)
- [V8 Wasm Dynamic Tiering](https://v8.dev/blog/wasm-dynamic-tiering)
- [V8 Speculative Optimizations for WebAssembly](https://v8.dev/blog/wasm-speculative-optimizations)
- [V8 SIMD Features](https://v8.dev/features/simd)
- [WebAssembly Feature Status](https://webassembly.org/features/)
- [WebAssembly Security](https://webassembly.org/docs/security/)
- [Wasm 3.0 Completed](https://webassembly.org/news/2025-09-17-wasm-3.0/)
- [WebAssembly GC Proposal](https://github.com/WebAssembly/gc/blob/main/proposals/gc/Overview.md)
- [WebAssembly Threads Proposal](https://github.com/WebAssembly/threads)
- [WebAssembly Exception Handling](https://github.com/WebAssembly/exception-handling/blob/main/proposals/exception-handling/Exceptions.md)
- [WebAssembly Tail Calls](https://github.com/WebAssembly/tail-call/blob/main/proposals/tail-call/Overview.md)
- [WebAssembly Component Model Introduction](https://component-model.bytecodealliance.org/)

### Browser Engine Internals
- [SpiderMonkey Engine Home](https://spidermonkey.dev/)
- [SpiderMonkey Portable Baseline Interpreter](https://cfallin.org/blog/2023/10/11/spidermonkey-pbl/)
- [JavaScript Engines Explained (Frontend Dogma, 2025)](https://frontenddogma.com/posts/2025/javascript-engines-explained/)
- [JavaScript Engines 2025: JIT Speed, Wasm, and GC (Madrigan, 2026)](https://blog.madrigan.com/en/blog/202602111004/)

### Performance Benchmarks & Analysis
- [Rust WebAssembly Performance: 8-10x Faster (byteiota, 2025)](https://byteiota.com/rust-webassembly-performance-8-10x-faster-2025-benchmarks/)
- [Understanding the Performance of WebAssembly Applications (BenchmarkingWasm)](https://benchmarkingwasm.github.io/BenchmarkingWebAssembly/)
- [Wasm vs. JavaScript: Who Wins at a Million Rows? (The New Stack)](https://thenewstack.io/wasm-vs-javascript-who-wins-at-a-million-rows/)
- [WebAssembly vs. JavaScript: Testing Side-by-Side Performance (The New Stack)](https://thenewstack.io/webassembly-vs-javascript-testing-side-by-side-performance/)
- [JS-to-Wasm Calls Are Finally Fast (Mozilla Hacks, 2018)](https://hacks.mozilla.org/2018/10/calls-between-javascript-and-webassembly-are-finally-fast-%F0%9F%8E%89/)
- [Is WebAssembly Magic Performance Pixie Dust? (Surma)](https://surma.dev/things/js-to-asc/)
- [WebAssembly: Go vs Rust vs AssemblyScript (Ecostack)](https://ecostack.dev/posts/wasm-tinygo-vs-rust-vs-assemblyscript/)

### Toolchains & Languages
- [Emscripten Pthreads Wiki](https://github.com/emscripten-core/emscripten/wiki/Pthreads-with-WebAssembly)
- [Binaryen / wasm-opt (GitHub)](https://github.com/WebAssembly/binaryen)
- [Shrinking .wasm Size (Rust and WebAssembly Book)](https://rustwasm.github.io/book/game-of-life/code-size.html)
- [Optimizing WASM Binary Size (Leptos Book)](https://book.leptos.dev/deployment/binary_size.html)
- [Rust + WebAssembly 2025: WasmGC and SIMD (DEV Community)](https://dev.to/dataformathub/rust-webassembly-2025-why-wasmgc-and-simd-change-everything-3ldh)

### WASI & Component Model
- [WASI and the WebAssembly Component Model: Current Status (Eunomia, 2025)](https://eunomia.dev/blog/2025/02/16/wasi-and-the-webassembly-component-model-current-status/)
- [WASI 1.0: WebAssembly Everywhere in 2026 (The New Stack)](https://thenewstack.io/wasi-1-0-you-wont-know-when-webassembly-is-everywhere-in-2026/)
- [WASI 0.3 and Composable Concurrency (Medium)](https://medium.com/wasm-radar/hypercharge-through-components-why-wasi-0-3-and-composable-concurrency-are-a-game-changer-0852e673830a)
- [WebAssembly Beyond the Browser: WASI 2.0 (DEV Community)](https://dev.to/pockit_tools/webassembly-beyond-the-browser-wasi-20-the-component-model-and-why-wasm-is-about-to-change-3ep0)

### Security
- [WebAssembly and Security: A Review (arXiv, 2024)](https://arxiv.org/html/2407.12297v1)
- [Memory Corruption in WebAssembly (Medium, 2025)](https://medium.com/@instatunnel/memory-corruption-in-webassembly-native-exploits-in-your-browser-f587d8938511)
- [Wasmtime Security Documentation](https://docs.wasmtime.dev/security.html)

### Production Case Studies
- [Figma: WebAssembly Cut Load Time by 3x](https://www.figma.com/blog/webassembly-cut-figmas-load-time-by-3x/)
- [V8 Blog: WasmGC Porting](https://v8.dev/blog/wasm-gc-porting)
- [WasmGC Enabled by Default in Chrome](https://developer.chrome.com/blog/wasmgc)
- [WebAssembly Production 2025: WasmGC and Enterprise Adoption (byteiota)](https://byteiota.com/webassembly-production-2025-wasmgc-and-enterprise-adoption/)
- [Godot Engine: Web Performance Boost with SIMD](https://godotengine.org/article/upcoming-serious-web-performance-boost/)

### State of WebAssembly Reports
- [The State of WebAssembly 2025 and 2026 (Platform.uno)](https://platform.uno/blog/the-state-of-webassembly-2025-2026/)
- [State of WebAssembly 2026 (DevNewsletter)](https://devnewsletter.com/p/state-of-webassembly-2026/)
- [What's New in WebAssembly 3.0 (Medium)](https://medium.com/wasm-radar/whats-new-in-webassembly-3-0-and-why-it-matters-for-developers-db14b6fb0d6c)

### Debugging & Tooling
- [Chrome DevTools: Debug C/C++ WebAssembly](https://developer.chrome.com/docs/devtools/wasm)
- [Debugging WebAssembly with Modern Tools (Chrome Blog)](https://developer.chrome.com/blog/wasm-debugging-2020)
- [Using WebAssembly Threads from C, C++ and Rust (web.dev)](https://web.dev/articles/webassembly-threads)
- [SharedArrayBuffer (MDN)](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer)

---

*Document generated February 2026. WebAssembly is evolving rapidly -- verify
browser support tables against [caniuse.com](https://caniuse.com) and
[webassembly.org/features](https://webassembly.org/features/) before
architectural decisions.*
