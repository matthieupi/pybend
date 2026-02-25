# 🗺️ WebAssembly Decision Framework

**When Wasm Makes Sense, When It Doesn't, and What Else to Consider**

*Research Date: February 2026 | Target Audience: Technical CEOs & Engineering Leadership*

---

## Executive Summary

WebAssembly (Wasm) delivers **real but bounded** performance gains for web applications: **2-3x speedups** on CPU-bound workloads in practice, not the 100x often claimed in marketing materials. Figma's 3x load-time reduction and Google Earth's cross-browser portability represent genuine success stories, but they share a specific profile: **large existing C/C++ codebases** performing **sustained, CPU-intensive computation** with **minimal JS-Wasm boundary crossing**.

For most web applications, the calculus is different. Serialization overhead at the JS-Wasm boundary can consume **up to 60% of execution time**. Rust developers command **$130K-$147K** versus **$74K-$135K** for JavaScript engineers. Debugging tooling remains immature. And optimized JavaScript using TypedArrays with Web Workers can match or beat Wasm in certain parallel workloads.

This document provides a structured framework for deciding **when Wasm delivers ROI**, **when it does not**, and **what alternatives to evaluate first**.

---

## Table of Contents

1. [When Wasm Delivers ROI](#1-when-wasm-delivers-roi)
2. [When Wasm Does NOT Make Sense](#2-when-wasm-does-not-make-sense)
3. [Alternatives to Evaluate First](#3-alternatives-to-evaluate-first)
4. [Wasm vs WebGPU Comparison](#4-wasm-vs-webgpu-comparison)
5. [Total Cost of Ownership Analysis](#5-total-cost-of-ownership-analysis)
6. [Team Readiness Assessment](#6-team-readiness-assessment)
7. [Build Complexity & CI/CD Impact](#7-build-complexity--cicd-impact)
8. [Decision Tree](#8-decision-tree)
9. [Risk Analysis](#9-risk-analysis)
10. [Benchmarking Properly](#10-benchmarking-properly)
11. [Migration Strategies](#11-migration-strategies)
12. [Organizational Readiness Checklist](#12-organizational-readiness-checklist)
13. [Sources](#13-sources)

---

## 1. When Wasm Delivers ROI

### 🗺️ Workload Characteristics That Predict Success

Wasm excels when **all three conditions** hold simultaneously:

| Condition | Why It Matters |
|-----------|---------------|
| **CPU-bound, not I/O-bound** | Wasm optimizes computation, not network/disk access |
| **Sustained computation, not burst** | Amortizes compilation and instantiation overhead |
| **Large data processed in bulk** | Minimizes boundary-crossing serialization cost |

> 💡 **Key Insight:** WebAssembly's advantage comes from **predictable, near-native execution speed** without JIT warmup variance. For small inputs, Wasm achieves up to **26.99x speedup** over JS. For medium-to-large inputs, the advantage narrows to **2-3x** as memory pressure increases. ([BenchmarkingWebAssembly](https://benchmarkingwasm.github.io/BenchmarkingWebAssembly/))

### 📊 Performance by Workload Type

| Workload | Typical Wasm Speedup | Confidence | Real-World Example |
|----------|---------------------|------------|-------------------|
| Image/video processing | 3-10x | High | Photoshop Web, Squoosh |
| 3D rendering / CAD | 2-5x | High | Figma (3x load time), AutoCAD Web |
| Cryptography | 5-20x | High | LibSodium Wasm bindings |
| Physics simulation | 3-8x | High | Unity WebGL, game engines |
| Data compression | 2-5x | Medium | Brotli/zstd in-browser |
| CSV/data parsing (millions of rows) | 2-3x | Medium | DuckDB-Wasm |
| Audio DSP | 3-10x | High | Spotify audio features |
| Code compilation | 2-4x | Medium | Pyodide, SwiftWasm playground |
| AI/ML inference (CPU) | 2-5x | Medium | TensorFlow.js Wasm backend |

### ✅ Ideal Wasm Candidates

- **Porting existing C/C++/Rust codebases** to the web (Google Earth, Photoshop, AutoCAD)
- **Computationally homogeneous** operations on **numeric data** (signal processing, scientific computing)
- **Latency-sensitive** code paths where JIT unpredictability is unacceptable
- **Codec/format processing** that browsers do not natively support
- Applications where **consistent performance across browsers** matters more than peak performance

### 📊 Adoption Data (2025-2026)

| Metric | Value | Source |
|--------|-------|--------|
| Sites using Wasm (desktop) | 0.35% (~43K sites) | HTTP Archive 2025 |
| Top-1000 site usage (desktop) | 2.0% | HTTP Archive 2025 |
| Chrome page visits touching Wasm | 5.5% | Chrome Platform Status |
| Developers using Wasm in production | 41% | State of Wasm Survey |
| Developers reporting >50% perf gain | 30% | State of Wasm Survey |
| Most common Wasm source language | .NET/Blazor (41.7%) | HTTP Archive 2025 |

---

## 2. When Wasm Does NOT Make Sense

### ❌ Anti-Patterns and False Starts

**The biggest mistake teams make** is adopting Wasm because it "will make the website faster" without identifying a specific, measurable performance bottleneck. ([ianjk.com](https://ianjk.com/webassembly-vs-javascript/))

| Anti-Pattern | Why It Fails |
|-------------|-------------|
| **DOM-heavy applications** | Wasm cannot touch the DOM directly; every DOM operation crosses the JS boundary |
| **I/O-bound workloads** | Network requests, IndexedDB, file system APIs are all JS-side; Wasm adds overhead |
| **Frequent small boundary crossings** | Serialization overhead dominates; up to **60% of execution time** spent on data transfer |
| **Simple CRUD/form apps** | No computational bottleneck to optimize; complexity increase with zero gain |
| **Text-heavy string processing** | Wasm operates on bytes, not UTF-16; string conversion overhead is substantial |
| **UI logic and event handling** | JavaScript's event loop integration is native; Wasm requires bridging |
| **Small-input, infrequent operations** | Wasm module instantiation cost (~1-5ms) may exceed the computation itself |

> ⚠️ **Warning:** Serialization at the JS-Wasm boundary contributes up to **60% of execution time** for complex data structures. Primitive types and TypedArrayBuffers cross cheaply; objects, strings, and nested structures do not. ([arxiv.org](https://arxiv.org/pdf/2511.01888))

### 📊 When Optimized JS Matches or Beats Wasm

Research demonstrates that **JavaScript with TypedArrays and Web Workers** can be **1.26x faster on average** than Wasm for parallel workloads that partition data well across threads using SharedArrayBuffer. ([dev.to](https://dev.to/sfundomhlungu/i-tried-to-beat-webassembly-with-nodejs-499o))

| Scenario | JS Approach | Wasm Advantage? |
|----------|------------|-----------------|
| Parallel numeric processing | SharedArrayBuffer + Workers | ❌ JS can be faster |
| JSON parsing/manipulation | Native V8 JSON.parse | ❌ JS is faster |
| DOM manipulation | Direct JS access | ❌ JS is the only option |
| Regex operations | Native engine regex | ❌ JS is faster |
| Small matrix math (<1000 elements) | Float64Array operations | ❌ Negligible difference |
| Image pixel manipulation | Canvas + Uint8ClampedArray | ⚠️ Depends on volume |
| Large matrix operations (>10K elements) | - | ✅ Wasm is faster |
| Sustained crypto operations | - | ✅ Wasm is significantly faster |

---

## 3. Alternatives to Evaluate First

Before committing to Wasm, evaluate these alternatives in order of **increasing complexity**:

### 📊 Alternative Technology Comparison

| Technology | What It Solves | Complexity | Browser Support | Best For |
|-----------|---------------|-----------|----------------|---------|
| **Optimized JS (TypedArrays)** | Raw numeric performance | Low | Universal | Numeric computation, data processing |
| **Web Workers** | Main thread blocking | Low | Universal | Any long-running task |
| **OffscreenCanvas** | Rendering jank | Low-Medium | Chrome, Firefox, Safari | Canvas-heavy rendering |
| **WebGPU** | Massively parallel compute | Medium-High | All major (since Nov 2025) | ML inference, image processing, simulations |
| **Server-side compute + streaming** | All client constraints | Medium | Universal | Very large datasets, security-sensitive |
| **WebAssembly** | CPU-bound hot paths | High | Universal | Codecs, crypto, physics, porting native code |

### 🗺️ Alternative Details

**1. Optimized JavaScript (Lowest Effort)**

Modern V8/SpiderMonkey JIT compilers are remarkably good at optimizing **monomorphic, TypedArray-based** code. Before reaching for Wasm:

- Replace `Array` with `Float64Array` / `Int32Array` for numeric work
- Avoid polymorphic function calls (V8 deoptimizes)
- Use `SharedArrayBuffer` for zero-copy sharing between workers
- Profile with Chrome DevTools Performance panel to find actual bottlenecks

> 💡 **Key Insight:** Using SharedArrayBuffer with typed arrays and workers for zero-copy sharing can achieve JavaScript performance comparable to WebAssembly. In benchmarks, this approach was **1.26x faster** on average than Wasm for well-partitioned parallel workloads.

**2. Web Workers (Parallelism)**

Web Workers solve a **different problem** than Wasm: they prevent main-thread blocking. Workers and Wasm are complementary, not competitors.

- Use Workers when the problem is **main thread jank**, not raw speed
- Combine with `SharedArrayBuffer` for zero-copy data sharing
- No learning curve for JS teams; standard browser API
- Can run Wasm **inside** Workers for both parallelism and speed

**3. OffscreenCanvas (Rendering)**

Moves canvas rendering to a worker thread, eliminating jank from heavy draw calls.

- Perfect for data visualization, chart rendering, animation
- Supported in Chrome, Firefox, and Safari
- No new language required; same Canvas API
- Combine with WebGL for GPU-accelerated rendering in a worker

**4. WebGPU (GPU Compute)**

The most powerful alternative for **massively parallel** workloads. Officially supported across all major browsers since **November 2025**.

- **23x faster** than Wasm for GPU-amenable rendering workloads ([aircada.com](https://aircada.com/blog/webgpu-vs-wasm))
- **2-3x faster** for AI/ML inference over Wasm backends ([Chrome DevBlog](https://developer.chrome.com/blog/io24-webassembly-webgpu-1))
- Requires learning WGSL (WebGPU Shading Language)
- Excellent for: ML inference, image processing, particle simulations, financial modeling

**5. Server-Side Compute with Streaming**

For the largest datasets or most security-sensitive computations:

- Server-Sent Events (SSE) or WebSocket streaming for progressive results
- WebTransport for low-latency bidirectional streaming
- Edge computing (Cloudflare Workers, Deno Deploy) reduces latency
- No client memory constraints; no browser compatibility issues
- Trade-off: requires network connectivity, adds latency

---

## 4. Wasm vs WebGPU Comparison

Both technologies enable high-performance web computation, but they target **fundamentally different hardware**:

### 📊 Head-to-Head Comparison

| Dimension | WebAssembly | WebGPU |
|-----------|------------|--------|
| **Hardware target** | CPU (single-threaded*) | GPU (massively parallel) |
| **Parallelism model** | Threads via Workers + SharedArrayBuffer | SIMD/SIMT on GPU cores |
| **Best speedup over JS** | 2-10x (typical) | 10-100x (for parallel workloads) |
| **Memory model** | Linear memory (4GB max, 16GB with Memory64) | GPU buffers, no strict limit |
| **Programming model** | Rust/C++/Go compiled to Wasm | WGSL shaders + JS orchestration |
| **Debugging** | Improving but immature | Very immature |
| **Browser support** | Universal (since 2017) | All major browsers (since Nov 2025) |
| **Startup overhead** | Module compilation (~1-50ms) | Pipeline compilation (~5-100ms) |
| **Data transfer cost** | JS-Wasm boundary serialization | CPU-GPU buffer transfer |
| **Maturity** | Production-proven (8+ years) | Newly standardized |

*Wasm threads (SharedArrayBuffer-based) enable multi-threaded operation but require cross-origin isolation headers.

### 🗺️ Decision: Wasm vs WebGPU by Workload

| Workload | Winner | Why |
|----------|--------|-----|
| Matrix multiplication (large) | **WebGPU** | Massively parallel; maps to GPU cores |
| Image convolution/filters | **WebGPU** | Per-pixel operations are embarrassingly parallel |
| ML inference | **WebGPU** | 2-3x faster than Wasm for LLM/embedding models |
| Sequential algorithms (sorting, graph traversal) | **Wasm** | Inherently serial; GPU adds transfer overhead |
| Compression/decompression | **Wasm** | Sequential byte processing; poor GPU fit |
| Cryptographic hashing | **Wasm** | Sequential computation with branching |
| Physics simulation (particles) | **WebGPU** | Embarrassingly parallel updates |
| Physics simulation (rigid body) | **Wasm** | Complex dependencies between objects |
| Porting existing C++/Rust code | **Wasm** | Direct compilation path exists |
| Audio processing (real-time) | **Wasm** | AudioWorklet integration; low-latency serial processing |

> 💡 **Key Insight:** Figma, one of Wasm's biggest success stories, is **also adopting WebGPU** for rendering. Their C++ renderer now uses Emscripten's WebGPU bindings, combining Wasm for logic with GPU for rendering. The future is **hybrid**, not either/or. ([Figma Blog](https://www.figma.com/blog/figma-rendering-powered-by-webgpu/))

---

## 5. Total Cost of Ownership Analysis

### 📊 Developer Cost Comparison (US Market, 2026)

| Role | Annual Salary (Median) | Hourly Rate (Contract) | Talent Pool Size |
|------|----------------------|----------------------|-----------------|
| JavaScript/TypeScript Developer | $74K - $135K | $40 - $80/hr | Very large |
| Rust Developer | $130K - $147K | $50 - $120/hr | Small |
| C++ Developer (Wasm-capable) | $120K - $155K | $55 - $110/hr | Medium |
| WebGPU/Graphics Engineer | $140K - $170K | $70 - $130/hr | Very small |

Sources: [Glassdoor](https://www.glassdoor.com/Salaries/rust-developer-salary-SRCH_KO0,14.htm), [ZipRecruiter](https://www.ziprecruiter.com/Salaries/Rust-Developer-Salary), [Lemon.io](https://lemon.io/hire/rust-developers/)

### 📊 TCO Model: Wasm Module for Compute-Heavy Feature

**Scenario:** Adding client-side image processing (resize, filter, compress) to a web application.

| Cost Category | JS-Only Approach | Wasm (Rust) Approach | Delta |
|--------------|-----------------|---------------------|-------|
| **Developer salary** (1 engineer, 6 months) | $55K - $67K | $65K - $73K | +$10K - $6K |
| **Ramp-up time** (if team is JS-only) | 0 weeks | 8 - 16 weeks | Significant delay |
| **Build pipeline** setup | Existing | +20-40 hours | One-time cost |
| **CI/CD maintenance** (annual) | Baseline | +10-15% pipeline time | Ongoing |
| **Bundle size impact** | None | +50KB - 2MB (.wasm) | Per-page-load cost |
| **Debugging time** (per incident) | Baseline | +50-200% per bug | Ongoing overhead |
| **Cross-browser testing** | Standard | +20% effort | Ongoing |
| **Hiring future maintainers** | Easy | Harder, premium salary | Long-term risk |
| **Performance gain** | Baseline | 2-5x for image ops | The ROI |

### 📊 Break-Even Analysis

The Wasm investment breaks even when:

```
(Performance gain value) × (User impact) > (TCO premium) × (Duration)
```

**Wasm pays off quickly when:**
- Performance is a **core product differentiator** (Figma, Photoshop)
- You already have a **C++/Rust codebase** to port (Google Earth, AutoCAD)
- The compute module is **isolated and stable** (codec, crypto library)
- You are building a **developer tool or platform** where performance is table stakes

**Wasm is hard to justify when:**
- Performance is "nice to have" but not a differentiator
- The team must learn Rust/C++ from scratch
- The computation is **already fast enough** in optimized JS
- The module would require **frequent updates** tied to business logic changes

> ⚠️ **Risk:** Niche technologies command higher salaries. Rust and WebAssembly expertise is among the most expensive to hire for. If your only Wasm engineer leaves, replacing them takes **2-4 months** at a premium. ([K&C](https://kruschecompany.com/international-rust-developer-salary-rate-ranges/))

---

## 6. Team Readiness Assessment

### 🗺️ Skills Needed by Role

| Role | Required Skills | Ramp-Up Estimate |
|------|----------------|-----------------|
| **Wasm Developer (Rust path)** | Rust ownership/borrowing, wasm-bindgen, wasm-pack, memory management | 3-6 months from JS background |
| **Wasm Developer (C++ path)** | Emscripten, C++ memory management, CMake/build systems | 2-4 months from C++ background |
| **Integration Engineer** | JS interop, TypedArrays, SharedArrayBuffer, Worker APIs | 2-4 weeks for experienced JS dev |
| **DevOps/Build Engineer** | wasm-pack/Emscripten CI setup, bundle optimization, wasm-opt | 1-2 weeks |
| **QA Engineer** | Cross-browser Wasm testing, performance regression testing | 1-2 weeks |

### 📊 Ramp-Up Time Estimates

| Starting Skill | Target | Estimated Time | Notes |
|---------------|--------|---------------|-------|
| Senior JS dev → Rust + Wasm | Production-ready | 3-6 months | Rust's ownership model is the main blocker |
| Senior C++ dev → Emscripten + Wasm | Production-ready | 1-2 months | Familiar mental model; toolchain is the learning |
| Senior Rust dev → wasm-bindgen | Production-ready | 1-2 weeks | Minimal additional learning |
| Junior dev → Rust + Wasm | Production-ready | 6-12 months | Not recommended as first project |
| Any dev → JS interop layer | Comfortable | 2-4 weeks | Understanding the boundary is key |

> 💡 **Key Insight:** Rust is consistently ranked the **most loved language** by developers, but learning curves vary wildly. Some junior developers excel quickly while senior engineers with decades of C/C++ experience may struggle for months with Rust's borrow checker. Prior experience does not reliably predict ramp-up speed. ([corrode.dev](https://corrode.dev/blog/flattening-rusts-learning-curve/))

### Team Profile Quick Assessment

Rate your team (1-5) on each dimension:

| Dimension | Score 1 (Low) | Score 5 (High) |
|-----------|--------------|----------------|
| **Systems programming experience** | Team is JS/Python only | Multiple C++/Rust engineers |
| **Performance culture** | "Ship features first" | Regular profiling and optimization |
| **Build pipeline sophistication** | npm scripts only | Multi-stage, multi-language CI/CD |
| **Risk tolerance** | Must use proven tools only | Comfortable with emerging tech |
| **Code ownership stability** | High turnover, many contractors | Stable core team, long tenure |

**Scoring:**
- **20-25:** Green light for Wasm adoption
- **14-19:** Proceed with caution; start with a small pilot
- **8-13:** Invest in JS optimization first; Wasm later
- **5-7:** Not ready; too much organizational risk

---

## 7. Build Complexity & CI/CD Impact

### 📊 Pipeline Additions for Wasm

| Pipeline Stage | Addition | Time Impact | Tooling |
|---------------|----------|-------------|---------|
| **Compile** | Rust/C++ → Wasm compilation | +30s - 5min per build | wasm-pack, Emscripten |
| **Optimize** | wasm-opt binary optimization | +5-30s | Binaryen |
| **Bundle** | .wasm file handling, async loading | +5-10s | webpack/Vite plugin |
| **Test (unit)** | Wasm-specific tests (wasm-pack test) | +30s - 2min | wasm-pack test, headless browser |
| **Test (integration)** | Cross-browser Wasm validation | +2-5min | Playwright, Selenium |
| **Size audit** | .wasm bundle size monitoring | +5s | Custom script or twiggy |

### 📊 Bundle Size Impact

| Optimization Level | Typical .wasm Size | Gzipped | Notes |
|-------------------|-------------------|---------|-------|
| Debug build | 1-20 MB | 500KB - 5MB | Includes debug info, names |
| Release build (default) | 200KB - 5MB | 50KB - 1MB | Standard optimization |
| Release + LTO + opt-level=z | 100KB - 2MB | 30KB - 500KB | Size-optimized |
| + wasm-opt -Oz | 80KB - 1.5MB | 25KB - 400KB | Further 10-30% reduction |
| + tree shaking | 50KB - 1MB | 15KB - 300KB | Remove unused exports |

> 💡 **Key Insight:** A real-world example showed wasm-pack optimization reducing binary from **29,410 bytes to 17,317 bytes**, with gzip bringing it to **9,045 bytes**. But beware: the `regex` crate alone adds ~500KB, and `serde` can inflate binaries significantly. Audit your dependency tree. ([Rust Wasm Book](https://rustwasm.github.io/book/game-of-life/code-size.html), [Leptos Docs](https://book.leptos.dev/deployment/binary_size.html))

### Cross-Browser Testing Matrix

| Browser | Wasm Support | Notes |
|---------|-------------|-------|
| Chrome 57+ | ✅ Full | Best DevTools support, most Wasm features |
| Firefox 52+ | ✅ Full | Good performance, JSPI still behind flag |
| Safari 11+ | ✅ Full | Memory64 and GC support added in 2025 |
| Edge 16+ | ✅ Full | Chromium-based; same as Chrome |
| Mobile Chrome | ✅ Full | Memory pressure on low-end devices |
| Mobile Safari | ✅ Full | 4GB limit more constrained on mobile |
| WebView (Android) | ✅ Full | Version-dependent; test specifically |

**wasm-bindgen browser support** covers all major browsers. The key variable is **feature support** (threads, SIMD, Memory64, GC), not basic Wasm execution. ([wasm-bindgen docs](https://rustwasm.github.io/docs/wasm-bindgen/reference/browser-support.html))

---

## 8. Decision Tree

```
                    ┌─────────────────────────────────┐
                    │  Do you have a measured, specific│
                    │  CPU-bound performance problem?  │
                    └───────────────┬─────────────────┘
                                    │
                          ┌─────────┴─────────┐
                          │                   │
                         YES                  NO
                          │                   │
                          │          ┌────────┴────────────┐
                          │          │ STOP. Optimize JS   │
                          │          │ first, or accept    │
                          │          │ current performance. │
                          │          └─────────────────────┘
                          │
                ┌─────────┴──────────────┐
                │ Is the workload        │
                │ embarrassingly parallel │
                │ (per-pixel, per-particle)?│
                └─────────┬──────────────┘
                          │
                ┌─────────┴─────────┐
                │                   │
               YES                  NO
                │                   │
       ┌────────┴────────┐         │
       │ Consider WebGPU │         │
       │ (10-100x gains) │         │
       └─────────────────┘         │
                                   │
                ┌──────────────────┴───────────────┐
                │ Is the problem main-thread jank   │
                │ (UI freezes) rather than raw speed?│
                └──────────────────┬───────────────┘
                                   │
                          ┌────────┴────────┐
                          │                 │
                         YES                NO
                          │                 │
                 ┌────────┴────────┐        │
                 │ Use Web Workers │        │
                 │ (+ OffscreenCanvas│       │
                 │  if rendering)   │       │
                 └─────────────────┘        │
                                            │
                ┌───────────────────────────┴──────────┐
                │ Have you tried optimized JS?          │
                │ (TypedArrays, SharedArrayBuffer,      │
                │  manual memory management)            │
                └───────────────────────────┬──────────┘
                                            │
                          ┌─────────────────┴─────────┐
                          │                           │
                         YES (still too slow)          NO
                          │                           │
                          │               ┌───────────┴───────────┐
                          │               │ Try optimized JS first.│
                          │               │ Profile. Benchmark.    │
                          │               │ Return here if needed. │
                          │               └───────────────────────┘
                          │
                ┌─────────┴──────────────────────┐
                │ Do you have an existing C++/Rust│
                │ codebase that does this work?   │
                └─────────┬──────────────────────┘
                          │
                ┌─────────┴─────────┐
                │                   │
               YES                  NO
                │                   │
       ┌────────┴──────────┐  ┌────┴───────────────────┐
       │ ✅ STRONG CASE    │  │ Does your team have    │
       │ Port via Emscripten│  │ Rust/C++ experience?   │
       │ or wasm-pack.     │  └────┬───────────────────┘
       │ ROI is highest    │       │
       │ here.             │  ┌────┴─────────┐
       └───────────────────┘  │              │
                             YES              NO
                              │              │
                    ┌─────────┴─────┐  ┌─────┴──────────────────┐
                    │ ✅ GOOD CASE  │  │ ⚠️ PROCEED WITH       │
                    │ Write new Wasm│  │ CAUTION.               │
                    │ module. Start │  │ Factor in 3-6 month    │
                    │ with isolated │  │ ramp-up. Consider      │
                    │ hot path.     │  │ server-side compute    │
                    └───────────────┘  │ as alternative.        │
                                       └────────────────────────┘
```

### 🗺️ Quick-Reference Decision Matrix

| Your Situation | Recommendation | Confidence |
|---------------|---------------|------------|
| Porting large C++ desktop app to web | ✅ Use Wasm (Emscripten) | Very High |
| Image/video processing in browser | ✅ Use Wasm or WebGPU | High |
| Typical SaaS CRUD application | ❌ Stick with JS | Very High |
| ML inference in browser | ✅ Use WebGPU (or Wasm fallback) | High |
| Real-time collaborative editor | ⚠️ Evaluate carefully; CRDT in Wasm can help | Medium |
| Data visualization with 100K+ points | ✅ WebGPU for rendering, Wasm for data processing | High |
| Crypto operations (client-side) | ✅ Use Wasm | High |
| Form validation / business logic | ❌ Stick with JS | Very High |
| Game engine in browser | ✅ Use Wasm + WebGPU | High |
| PDF generation client-side | ⚠️ Wasm if porting existing lib; else JS | Medium |
| Compression before upload | ✅ Wasm (port zstd/brotli) | High |
| Search/filter over local dataset | ❌ JS is fine for <100K records | High |
| Audio synthesis / DSP | ✅ Wasm + AudioWorklet | High |

---

## 9. Risk Analysis

### ⚠️ Technical Risks

| Risk | Severity | Likelihood | Mitigation |
|------|----------|-----------|------------|
| **4GB linear memory limit** | High | Medium | Use Memory64 (16GB cap in browsers); segment data across Workers; stream large datasets |
| **Debugging difficulty** | Medium | High | Invest in logging infrastructure; use DWARF debug info; accept slower debug cycles |
| **Serialization bottleneck** | High | High | Design API around TypedArrays and bulk transfers; avoid per-object boundary crossings |
| **Browser edge cases** | Medium | Low | Test on real devices; Safari memory behavior differs from Chrome; mobile has tighter limits |
| **Build toolchain breakage** | Medium | Medium | Pin tool versions; use Docker for reproducible builds; maintain fallback JS path |
| **Performance regression in browser updates** | Low | Low | Automated performance benchmarks in CI; browser vendors have strong Wasm compat commitment |
| **WASM binary size bloat** | Medium | High | Audit dependencies; use `wasm-opt -Oz`; enable LTO; avoid heavy crates (regex, serde) |

### ⚠️ Organizational Risks

| Risk | Severity | Likelihood | Mitigation |
|------|----------|-----------|------------|
| **Key-person dependency** | High | High | Document architecture thoroughly; pair programming; at least 2 engineers per module |
| **Hiring pipeline dry-up** | High | Medium | Invest in internal training; consider Rust-curious JS devs over external hires |
| **Scope creep** ("let's Wasm everything") | Medium | Medium | Strict boundary: Wasm for compute modules only; JS for everything else |
| **Sunk cost fallacy** | Medium | Medium | Set clear performance targets before starting; kill the project if targets aren't met in POC |
| **Team morale** (frustrating tooling) | Medium | Medium | Acknowledge the learning curve; allocate slack time; celebrate wins |

### 📊 Memory Limits in Detail

| Memory Configuration | Max Address Space | Browser Support | Notes |
|---------------------|------------------|----------------|-------|
| Wasm32 (default) | 4 GB | All browsers | Standard; most tools target this |
| Memory64 | 16 GB (browser-imposed) | Chrome 133+, Firefox (flag), Safari (WIP) | 64-bit pointers; some optimization loss |
| Multi-memory (proposal) | 4 GB per memory | Behind flags | Multiple independent memory spaces |
| External ArrayBuffers | No Wasm limit | All browsers | Use JS heap; manual management |

> ⚠️ **Warning:** Even with Memory64, browsers impose practical limits. Chrome limits to 16GB. Mobile browsers may impose much tighter limits (1-2GB) depending on device memory. Always design for graceful degradation. ([V8 Blog](https://v8.dev/blog/4gb-wasm-memory), [WebAssembly/spec#1116](https://github.com/WebAssembly/spec/issues/1116))

---

## 10. Benchmarking Properly

### ⚠️ Common Benchmarking Mistakes

Most Wasm-vs-JS benchmarks in blog posts are **misleading**. Here is how to avoid the most common traps:

| Mistake | Why It's Misleading | Correct Approach |
|---------|-------------------|-----------------|
| **Excluding Wasm compilation time** | Real users pay this cost on first load | Measure cold-start including `WebAssembly.compile()` + `instantiate()` |
| **Excluding serialization overhead** | Data must cross the JS-Wasm boundary | Include full round-trip: JS → serialize → Wasm compute → deserialize → JS |
| **Measuring after JIT warmup only** | JS gets faster over iterations; Wasm is stable | Measure both cold and warmed performance; report both |
| **Micro-benchmarks only** | Tight loops favor Wasm; real apps have overhead | Benchmark the **actual feature**, not an isolated function |
| **Running in Node.js, reporting as "browser"** | Node V8 and browser V8 behave differently | Benchmark in **actual target browsers** |
| **Not testing across browsers** | Performance varies 2-3x between engines | Test Chrome, Firefox, Safari minimum |
| **Ignoring memory consumption** | Wasm uses **significantly more memory** for large inputs | Profile memory alongside execution time |
| **Small input sizes only** | Wasm advantage shrinks with larger inputs | Test with production-realistic data sizes |

### ✅ Benchmark Methodology Checklist

```
□ Define the metric: wall-clock time? throughput? latency P99?
□ Include module compilation and instantiation in "cold" benchmark
□ Include JS-Wasm serialization in all measurements
□ Run on real target browsers (not just Node.js)
□ Test with production-realistic input sizes
□ Measure memory consumption alongside speed
□ Run enough iterations for statistical significance (100+ warm runs)
□ Report cold-start AND warm-start numbers separately
□ Compare against OPTIMIZED JS (TypedArrays), not naive JS
□ Test on target hardware (including low-end mobile devices)
□ Use performance.now() with cross-origin isolation for precision
□ Document browser versions, OS, and hardware specs
```

### 📊 What "Good" Benchmarks Look Like

| Benchmark Design | Measures | Example |
|-----------------|---------|---------|
| **End-to-end feature** | Real user impact | "Image resize 4K→1080p: 45ms (Wasm) vs 180ms (JS)" |
| **Cold start** | First-load penalty | "Module compile: 12ms; first call: 48ms; subsequent: 2ms" |
| **Memory profile** | Resource consumption | "Peak heap: 24MB (Wasm) vs 8MB (JS) for same workload" |
| **Browser matrix** | Cross-browser variance | "Chrome: 2.1x faster; Firefox: 1.8x; Safari: 2.4x" |
| **Scaling curve** | Input-size sensitivity | "Speedup: 8x at 1KB, 3x at 1MB, 1.5x at 100MB" |

> 💡 **Key Insight:** Research found that at extra-small input sizes, Wasm achieves **26.99x speedup** in 97.6% of benchmarks. At medium input sizes, **18 benchmarks flipped** to JavaScript being faster. Always benchmark at your **actual** data sizes. ([BenchmarkingWebAssembly](https://benchmarkingwasm.github.io/BenchmarkingWebAssembly/))

---

## 11. Migration Strategies

### 🗺️ Strategy 1: Strangler Fig for Hot Paths (Recommended)

Inspired by Martin Fowler's [Strangler Fig Pattern](https://martinfowler.com/bliki/StranglerFigApplication.html), this approach incrementally replaces JavaScript hot paths with Wasm modules while keeping the rest of the application unchanged.

**Phase 1: Identify and Isolate (2-4 weeks)**
```
┌─────────────────────────────────────────────┐
│  JS Application                             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌───────────┐  │
│  │ UI   │ │ State│ │ API  │ │ Compute   │  │
│  │ Layer│ │ Mgmt │ │ Layer│ │ Module    │◄─┼── Profile: Is this the bottleneck?
│  └──────┘ └──────┘ └──────┘ └───────────┘  │
└─────────────────────────────────────────────┘
```

- Profile the application; identify the top 1-3 CPU-bound hot paths
- Verify they meet the criteria: CPU-bound, sustained, bulk data
- Extract the hot path into a **pure function** with a clean interface
- Define the data contract: TypedArray inputs → TypedArray outputs

**Phase 2: Build Wasm Module in Parallel (4-8 weeks)**
```
┌─────────────────────────────────────────────┐
│  JS Application                             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌───────────┐  │
│  │ UI   │ │ State│ │ API  │ │ JS Compute│  │
│  │ Layer│ │ Mgmt │ │ Layer│ │ (original)│  │
│  └──────┘ └──────┘ └──────┘ └─────┬─────┘  │
│                                    │        │
│                              ┌─────┴─────┐  │
│                              │ Adapter   │  │
│                              │ (feature  │  │
│                              │  flag)    │  │
│                              └─────┬─────┘  │
│                           ┌────────┴───┐    │
│                           │ Wasm Module│    │
│                           │ (new)      │    │
│                           └────────────┘    │
└─────────────────────────────────────────────┘
```

- Implement the same function in Rust/C++
- Feature-flag toggles between JS and Wasm implementations
- A/B test performance in production with real user data
- Keep the JS implementation as a fallback

**Phase 3: Validate and Commit (2-4 weeks)**

- Compare performance metrics: execution time, memory, bundle size
- Verify correctness: output parity between JS and Wasm implementations
- Monitor error rates, browser compatibility issues
- If targets are met: make Wasm the default, keep JS fallback
- If targets are not met: revert without production impact

### 🗺️ Strategy 2: Library Wrapping

Use existing Wasm libraries (e.g., ffmpeg.wasm, sql.js, pdflib-wasm) without writing Rust/C++:

| Library | What It Does | Bundle Size (gzipped) |
|---------|-------------|---------------------|
| ffmpeg.wasm | Video/audio processing | ~25 MB (full), ~3 MB (core) |
| sql.js | SQLite in browser | ~400 KB |
| pdflib-wasm | PDF generation | ~1.5 MB |
| libsodium.js | Cryptography | ~180 KB |
| squoosh-lib | Image compression | ~200-500 KB per codec |
| DuckDB-Wasm | Analytical SQL queries | ~4 MB |

> 💡 **Key Insight:** Library wrapping is the **lowest-risk entry point** for Wasm. You consume a pre-built .wasm module via a JS API. No Rust/C++ required. If it solves your problem, start here.

### 🗺️ Strategy 3: Full Port (High Risk, High Reward)

For organizations with existing native codebases (desktop applications, game engines):

| Stage | Duration | Risk | Deliverable |
|-------|----------|------|------------|
| Feasibility POC | 2-4 weeks | Low | Core loop running in browser |
| Core engine port | 3-6 months | Medium | Feature-complete Wasm module |
| JS integration layer | 1-3 months | Medium | Full application working |
| Performance optimization | 1-2 months | Low | Meet target benchmarks |
| Production hardening | 1-2 months | Medium | Error handling, monitoring, fallbacks |

**Total: 6-15 months** for a significant port. Budget for surprises.

Success stories: Figma (C++ → Wasm), Google Earth (C++ → Wasm), AutoCAD (C++ → Wasm), Adobe Photoshop (C++ → Wasm).

---

## 12. Organizational Readiness Checklist

Use this checklist before committing to a Wasm project. Each item scored 0 (not met) or 1 (met).

### ✅ Technical Readiness

| # | Criterion | Score |
|---|----------|-------|
| 1 | We have **profiled our application** and identified a specific CPU-bound bottleneck | ☐ |
| 2 | We have **benchmarked optimized JS** (TypedArrays, Workers) and it's not sufficient | ☐ |
| 3 | The bottleneck involves **sustained computation** (not one-off, not I/O) | ☐ |
| 4 | The data interface can be expressed as **TypedArrays or simple numeric types** | ☐ |
| 5 | We have tested that the **boundary-crossing overhead** does not dominate | ☐ |
| 6 | Our target browsers all **support required Wasm features** (threads, SIMD, etc.) | ☐ |
| 7 | The .wasm bundle size is **acceptable** for our loading budget (<500KB gzipped for most apps) | ☐ |
| 8 | We have a **fallback strategy** if Wasm fails (JS implementation, server-side, etc.) | ☐ |

### ✅ Team Readiness

| # | Criterion | Score |
|---|----------|-------|
| 9 | At least **2 engineers** have or can acquire Rust/C++ Wasm experience | ☐ |
| 10 | The team has **allocated ramp-up time** (8-16 weeks for JS-only teams) | ☐ |
| 11 | We have **documentation and knowledge-sharing** practices to avoid key-person risk | ☐ |
| 12 | Engineering leadership **understands the TCO trade-offs** and has budgeted accordingly | ☐ |

### ✅ Organizational Readiness

| # | Criterion | Score |
|---|----------|-------|
| 13 | We have **defined success metrics** (e.g., "image resize under 50ms at P95") | ☐ |
| 14 | We have a **kill criteria** (e.g., "if POC doesn't show >2x improvement, we stop") | ☐ |
| 15 | The Wasm module's **scope is bounded** (not "let's rewrite everything in Rust") | ☐ |
| 16 | Our CI/CD pipeline can **accommodate multi-language builds** | ☐ |
| 17 | We have a **monitoring plan** for Wasm-specific metrics (compile time, memory usage, errors) | ☐ |
| 18 | The project timeline allows for **proper benchmarking** before and after | ☐ |

### 📊 Scoring

| Score | Recommendation |
|-------|---------------|
| **16-18** | Strong go. Execute with confidence. |
| **12-15** | Conditional go. Address gaps before scaling past POC. |
| **8-11** | Not ready. Fill gaps or choose an alternative approach. |
| **0-7** | Stop. The risk/reward ratio is unfavorable. Revisit in 6 months. |

---

## Summary: The One-Page Decision Guide

| Question | If YES | If NO |
|----------|--------|-------|
| Is there a **measured** CPU-bound bottleneck? | Continue evaluating | ❌ Don't use Wasm |
| Is the workload **embarrassingly parallel**? | Consider **WebGPU** first | Continue evaluating |
| Is the problem **main-thread blocking** only? | Use **Web Workers** | Continue evaluating |
| Have you tried **optimized JS** (TypedArrays, Workers)? | Continue if still too slow | Try optimized JS first |
| Do you have an **existing C++/Rust codebase**? | ✅ **Strong Wasm case** | Continue evaluating |
| Does your team have **Rust/C++ experience**? | ✅ **Good Wasm case** | ⚠️ Factor in 3-6 month ramp-up |
| Can the interface use **TypedArrays/numerics**? | ✅ Low boundary overhead | ⚠️ Serialization may dominate |
| Is performance a **product differentiator**? | ✅ Worth the investment | ⚠️ Hard to justify TCO premium |

**The bottom line:** WebAssembly is a **precision tool**, not a silver bullet. It delivers exceptional value for CPU-bound computation with clean numeric interfaces, porting existing native codebases, and performance-critical product features. For everything else, optimized JavaScript, Web Workers, and WebGPU are usually better investments.

---

## 13. Sources

### Benchmarks and Performance Research
- [WebAssembly Benchmark Suite](https://benchmarkingwasm.github.io/BenchmarkingWebAssembly/) - Academic performance analysis across input sizes
- [WebAssembly vs JavaScript: Side-by-Side Performance](https://thenewstack.io/webassembly-vs-javascript-testing-side-by-side-performance/) - The New Stack, 2026
- [Not So Fast: Analyzing the Performance of WebAssembly vs. Native Code](https://ar5iv.labs.arxiv.org/html/1901.09056) - USENIX ATC 2019
- [WebAssembly versus JavaScript: Energy and Runtime Performance](https://ieeexplore.ieee.org/document/9830108) - IEEE 2022
- [Wasm vs JavaScript: Who Wins at a Million Rows?](https://thenewstack.io/wasm-vs-javascript-who-wins-at-a-million-rows/) - The New Stack
- [WebAssembly vs. JavaScript: Which Is Better in 2026?](https://graffersid.com/webassembly-vs-javascript/) - GraffersID

### Case Studies
- [WebAssembly Cut Figma's Load Time by 3x](https://www.figma.com/blog/webassembly-cut-figmas-load-time-by-3x/) - Figma Blog
- [Figma Rendering: Powered by WebGPU](https://www.figma.com/blog/figma-rendering-powered-by-webgpu/) - Figma Blog
- [How We Brought Google Earth to the Web](https://web.dev/earth-webassembly/) - web.dev
- [How We Used WebAssembly to Speed Up Our Web App by 20x](https://www.smashingmagazine.com/2019/04/webassembly-speed-web-app/) - Smashing Magazine
- [10 Years of Wasm: A Retrospective](https://bytecodealliance.org/articles/ten-years-of-webassembly-a-retrospective) - Bytecode Alliance

### WebGPU
- [WebGPU vs WASM: Is WebGPU a Better Choice?](https://aircada.com/blog/webgpu-vs-wasm) - Aircada
- [WebAssembly and WebGPU Enhancements for Faster Web AI](https://developer.chrome.com/blog/io24-webassembly-webgpu-1) - Chrome for Developers
- [GPU Acceleration in Browsers: WebGPU Benchmarks](https://www.mayhemcode.com/2025/12/gpu-acceleration-in-browsers-webgpu.html)

### Developer Costs and Hiring
- [Rust Developer Salary 2026](https://www.glassdoor.com/Salaries/rust-developer-salary-SRCH_KO0,14.htm) - Glassdoor
- [Rust Developer Hourly Rate 2026](https://www.ziprecruiter.com/Salaries/Rust-Developer-Salary) - ZipRecruiter
- [Hire Rust Developers](https://lemon.io/hire/rust-developers/) - Lemon.io
- [International Rust Developer Salary Ranges](https://kruschecompany.com/international-rust-developer-salary-rate-ranges/) - K&C

### Adoption Statistics
- [WebAssembly | 2025 Web Almanac](https://almanac.httparchive.org/en/2025/webassembly) - HTTP Archive
- [The State of WebAssembly 2025 and 2026](https://platform.uno/blog/the-state-of-webassembly-2025-2026/) - Platform.uno
- [WebAssembly Hits 4.5% Adoption](https://byteiota.com/webassembly-hits-4-5-adoption-eyes-50-by-2030/) - ByteIota

### Technical References
- [V8 Blog: Up to 4GB of Memory in WebAssembly](https://v8.dev/blog/4gb-wasm-memory)
- [Memory64: Smashing the 4GB Barrier](https://jsschools.com/web_dev/webassemblys-memory64-smashing-the-4gb-barrier-f/)
- [Shrinking .wasm Size](https://rustwasm.github.io/book/game-of-life/code-size.html) - Rust and WebAssembly Book
- [Optimizing WASM Binary Size](https://book.leptos.dev/deployment/binary_size.html) - Leptos Docs
- [Six Ways of Optimizing WebAssembly](https://www.infoq.com/articles/six-ways-optimize-webassembly/) - InfoQ
- [wasm-bindgen Browser Support](https://rustwasm.github.io/docs/wasm-bindgen/reference/browser-support.html)
- [Debugging WebAssembly with Modern Tools](https://developer.chrome.com/blog/wasm-debugging-2020) - Chrome for Developers
- [Roadrunner: Accelerating Data Delivery to Wasm](https://arxiv.org/pdf/2511.01888) - arxiv (serialization overhead research)

### Decision Frameworks and Guides
- [WebAssembly in Practice: When JavaScript Isn't Enough](https://www.codewithseb.com/blog/webassembly-practical-guide-when-javascript-isnt-enough/) - Code With Seb
- [WebAssembly vs JavaScript: Complete Guide](https://snipcart.com/blog/webassembly-vs-javascript) - Snipcart
- [WebAssembly vs JavaScript](https://ianjk.com/webassembly-vs-javascript/) - Ian J. Kennedy
- [Rust vs JavaScript & TypeScript: Performance and WebAssembly](https://blog.jetbrains.com/rust/2026/01/27/rust-vs-javascript-typescript/) - JetBrains
- [Flattening Rust's Learning Curve](https://corrode.dev/blog/flattening-rusts-learning-curve/) - corrode Rust Consulting
- [WebAssembly Is Still Waiting for Its Moment](https://leaddev.com/technical-direction/webassembly-still-waiting-its-moment) - LeadDev
