# 📋 WebAssembly for Compute-Heavy Operations: Strategic Analysis Report

## For: Technical Leadership & Engineering Teams
## Date: February 2026
## Prepared by: Engineering Strategy

---

### How to Read This Document

This report runs long -- deliberately. Different readers need different depths. Pick the path that fits your time:

| Time | What to Read | What You'll Learn |
|------|-------------|-------------------|
| **5 min** | [Executive Summary](#-executive-summary) only | The verdict, the numbers, the recommendation |
| **15 min** | Executive Summary + [Section 4: Our Architecture](#4--our-current-architecture-assessment) + [Section 7: Recommendation](#7--recommendation) | Whether Wasm matters for *us* specifically |
| **30 min** | Add [Section 2: Industry Landscape](#2--industry-landscape) + [Section 5: Cost-Benefit](#5--cost-benefit-analysis) + [Section 6: Decision Framework](#6--decision-framework) | Full strategic picture with industry context and financial analysis |
| **45 min** | The whole thing | Complete technical depth, risk register, appendices, and all supporting evidence |

**Companion document:** A standalone 2-4 page executive summary is available at [webassembly-executive-summary.md](webassembly-summary.md) for distribution to leadership who prefer a shorter format.

---

## 📋 Executive Summary

> 💡 **Key Finding:** WebAssembly is a mature, production-proven technology for compute-heavy browser workloads -- but PyBend is not a compute-heavy browser workload. Our frontend spends **3% of wall-clock time on CPU operations** and **84% on network round-trips**. Wasm cannot improve network latency. The recommendation is clear: **do not invest in Wasm for PyBend today**, but monitor two specific triggers that would change the calculus.

WebAssembly has crossed from experimental to production infrastructure. The **W3C ratified Wasm 3.0** in September 2025. **96.14% of browsers** support it globally. The cloud platform market stands at **$1.82 billion** with a projected **33.3% CAGR** through 2029. Companies running Wasm in production include Figma (3x load time improvement), Google Sheets (2x calculation speed), Adobe Photoshop, Autodesk AutoCAD, eBay, American Express, and Cloudflare (10M+ requests/second).

The technology is real. The performance gains are real. The question is whether *our* architecture benefits from it.

We analyzed every compute path in PyBend's ~38,000-line codebase (27K JS / 11K Python across 118 JS files and ~80 Python files). The findings are unambiguous:

| PyBend's Compute Reality | Detail |
|---|---|
| **Total CPU time per page load** | ~11ms out of ~321ms total |
| **Network time per page load** | ~270ms (84% of total) |
| **DOM rendering time** | ~40ms (12% of total) |
| **Hottest CPU path** | `Formidable.getForm()` at 1-5ms per call |
| **Fastest CPU path** | `Permissions.canAction()` at <0.05ms per call |
| **Compute-to-network ratio** | 1:8 |

Even a hypothetical 10x Wasm speedup on *all* CPU operations would save ~10ms on a 321ms page load -- a **3% improvement invisible to users**. The JS-Wasm boundary crossing overhead would likely *increase* total time for most of PyBend's microsecond-scale operations.

**The recommendation:**

1. **Do not invest in Wasm for PyBend today.** The ROI is negative at current scale.
2. **Monitor two triggers** that would change the calculus:
   - **Trigger A:** Client-side entity counts exceed 1,000 per page (batch operations become CPU-bound)
   - **Trigger B:** Validation parity between frontend and backend becomes a recurring source of bugs (shared Wasm module eliminates duplication)
3. **Invest engineering effort where it matters:** HTTP caching, schema preloading, WebSocket for real-time updates -- these address the 84% network bottleneck that Wasm cannot touch.

---

## 1. 🔍 What Is WebAssembly?

> 💡 **Key Finding:** WebAssembly is a binary instruction format that delivers near-native execution speed inside the browser sandbox. It is not a replacement for JavaScript -- it is a complement for CPU-bound workloads where JavaScript's JIT compiler is not fast enough or not predictable enough.

### The 30-Second Explanation

WebAssembly (Wasm) is a low-level binary format designed to run in web browsers at near-native speed. Languages like Rust, C++, Go, and even Java can be compiled to Wasm, and the resulting binary runs inside the browser's sandbox alongside JavaScript.

Think of it this way: JavaScript is interpreted and JIT-compiled by the browser engine. Wasm is pre-compiled to a binary format that the browser can validate and execute much more quickly. The browser still applies its own compilation (baseline + optimizing tiers), but Wasm's typed, structured binary format eliminates the parsing, AST construction, and type inference work that JavaScript requires.

### How It Executes

Every major browser engine implements a **two-tier compilation strategy** for Wasm. The binary format was designed from the start for streaming compilation -- the engine can begin compiling bytes as they arrive over the network, before the full module is downloaded (see [Technical Deep Dive](../research/02-technical-deep-dive.md), Section 1).

```
                    Wasm Execution Pipeline (Simplified)

  .wasm binary ──> [Validate] ──┬──> [Baseline Compile] ──> Execute immediately
     (network,       (single     |        (fast, 1-pass)
      streaming)      pass)      |
                                 └──> [Optimizing Compile] ──> Replace hot functions
                                         (background thread,     with optimized code
                                          multi-pass)

  Engine Names:
  ──────────────────────────────────────────────────
  V8 (Chrome/Edge):      Liftoff (baseline)  →  TurboFan (optimizing)
  SpiderMonkey (Firefox): Baseline JIT        →  IonMonkey/Warp
  JavaScriptCore (Safari): BBQ               →  OMG
```

The key advantage over JavaScript is not just raw speed -- it is **predictability**. JavaScript's JIT compiler can achieve near-native speed on hot paths, but it can also "fall off the fast path" due to type guard failures, deoptimization, or garbage collection pauses. Wasm code runs at a consistent speed from the first invocation. For latency-sensitive applications, this predictability matters more than peak throughput (see [Industry Research](../research/01-industry-landscape.md), Performance Benchmarks section).

### What Wasm 3.0 Brings (September 2025)

The W3C ratified Wasm 3.0 in September 2025, bundling years of feature development into a single standard:

| Feature | What It Enables | Why It Matters |
|---------|----------------|---------------|
| **Garbage Collection (GC)** | Java, Kotlin, Dart compile to Wasm without shipping their own GC | Opens Wasm to ~60% of programming languages |
| **Memory64** | 64-bit address space (16 EB theoretical vs. 4 GB) | Large dataset processing, AI model inference |
| **SIMD (128-bit)** | Process 4 floats / 2 doubles simultaneously | 3-10x speedups for image/audio/numeric work |
| **Exception Handling** | Native try/catch/throw with typed tags | Proper error propagation from C++/Rust |
| **Threads + Atomics** | True shared-memory concurrency via Web Workers | Parallel computation for heavy workloads |
| **Tail Calls** | Functional language optimization | Efficient compilation of OCaml, Scheme, Haskell |

(Source: [Wasm 3.0 Completed](https://webassembly.org/news/2025-09-17-wasm-3.0/); see [Technical Deep Dive](../research/02-technical-deep-dive.md), Section 12)

### What Wasm Cannot Do

This is as important as what it can do:

- **Cannot access the DOM.** Every DOM operation must go through JavaScript. If your bottleneck is rendering, Wasm does not help.
- **Cannot make network requests.** `fetch()`, WebSocket, IndexedDB -- all go through JS.
- **Cannot reduce network latency.** If your bottleneck is HTTP round-trips, Wasm is irrelevant.
- **Cannot replace JavaScript for UI logic.** Event handling, state management, routing -- these remain JS territory.
- **Is not "free" to call.** Every JS-to-Wasm call crosses an ABI boundary (~2.5 nanoseconds per call, but data marshaling for complex types can cost much more).

---

## 2. 🏢 Industry Landscape

> 💡 **Key Finding:** WebAssembly is production infrastructure, not experimental technology. The companies running it -- Figma, Google, Adobe, Autodesk, eBay, American Express, Cloudflare -- are among the most technically sophisticated on the planet. But every successful deployment shares a specific profile: large existing C/C++ codebases performing sustained, CPU-intensive computation with minimal JS-Wasm boundary crossing. Companies using Wasm for general-purpose web apps (Blazor) have encountered persistent performance criticism.

### Market Size and Trajectory

The WebAssembly market has reached a scale that signals durable investment, not speculative hype:

| Market Segment | Current Value | Projected Value | CAGR | Source |
|---|---|---|---|---|
| Wasm Cloud Platform | **$1.82B** (2025) | **$5.75B** (2029) | **33.3%** | [Research and Markets](https://www.researchandmarkets.com/reports/6215521/webassembly-cloud-platform-global-market-report) |
| Wasm Runtime | **$1.42B** (2024) | Projected to 2033 | **32.8%** | [Growth Market Reports](https://growthmarketreports.com/report/webassembly-runtime-market) |
| Serverless Edge (Wasm-powered) | -- | **$11.45B** (2033) | **27.1%** | Industry estimates |

The most significant acquisition signal: **Akamai acquired Fermyon** (the leading Wasm serverless startup) in December 2025, indicating that the largest CDN companies view Wasm as core infrastructure (see [Industry Research](../research/01-industry-landscape.md), Market Size section).

### Browser Support: Universal

WebAssembly achieved **96.14%** global browser support as of early 2026 -- higher than CSS Grid (95.5%) and on par with ES6 modules. The only browsers that cannot run Wasm (IE 11 and Opera Mini) represent less than 2% of global traffic and are declining. For any new project in 2026, **Wasm browser support is not a risk factor** ([Can I Use](https://caniuse.com/wasm)).

Advanced features have slightly less coverage but are rapidly converging:

```
Feature                Chrome   Firefox   Safari   Global %
───────────────────────────────────────────────────────────
Core Wasm 1.0          57+      52+       11+      ~96%
SIMD (128-bit)         91+      89+       16.4+    ~93%
Threads/Atomics        74+      79+       15.2+    ~90%*
Exception Handling     95+      100+      15.2+    ~92%
WasmGC                 119+     120+      18.2+    ~85%
Memory64               135+     ❌        ❌       ~70%
───────────────────────────────────────────────────────────
* Requires cross-origin isolation (COOP/COEP headers)
```

(Source: [Can I Use](https://caniuse.com/wasm), [HTTP Archive 2025 Web Almanac](https://almanac.httparchive.org/en/2025/webassembly); see [Industry Research](../research/01-industry-landscape.md), Browser Support section)

### Production Case Studies: Who Ships Wasm and Why

The strongest evidence for WebAssembly comes not from benchmarks but from production deployments at scale. Here are the most instructive case studies, organized by the lesson they teach.

---

#### Figma: The Gold Standard (3x Load Time Improvement)

Figma compiled their existing **C++ rendering engine** to WebAssembly via Emscripten. The result: **3x faster load time** regardless of document size, with subsequent loads even faster because browsers cache the Wasm-to-native translation.

**Why it worked:** Figma had an existing native codebase performing millions of geometric calculations per frame -- the ideal Wasm workload. The compilation path (C++ -> Emscripten -> Wasm) was natural. No new code was written in a new language; the same code simply got a different compilation target.

**The lesson:** Wasm delivers the highest ROI when you are *porting* existing high-performance code, not *writing* new code from scratch. Figma did not rewrite their renderer in Rust for the browser -- they compiled their existing C++ to Wasm.

(Source: [Figma Engineering Blog](https://www.figma.com/blog/webassembly-cut-figmas-load-time-by-3x/); see [Industry Research](../research/01-industry-landscape.md), Case Studies)

---

#### Google Sheets: The Long Road (2x Calculation Speed via WasmGC)

Google ported the Sheets calculation engine from JavaScript to **WasmGC**, compiling from Java. The production result: **2x faster calculations** on Chrome and Edge.

**But the journey was not smooth.** The initial WasmGC prototype in late 2021 was **2x slower than JavaScript** -- the opposite of the goal. It took **3+ years of optimization** across compiler, runtime, and application layers to reach the 2x improvement. Key wins included a ~40% speedup from virtual method dispatch optimization and a ~100x speedup from switching compiled Java regex to browser-native RegExp.

**The lesson:** Wasm optimization is not plug-and-play. Google had dedicated compiler engineers working for years to achieve a 2x improvement. This is not a weekend project.

(Source: [web.dev case study](https://web.dev/case-studies/google-sheets-wasmgc); see [Industry Research](../research/01-industry-landscape.md), Case Studies)

---

#### Adobe Photoshop: Million-Line Codebase in the Browser

Adobe brought the full Photoshop application to the browser by compiling their C/C++ codebase to WebAssembly using Emscripten. **SIMD provides 3-4x average speedup** across image processing, with **80-160x speedups** for Halide-based operations. TensorFlow.js ML models see **30-200% performance improvements** via the Wasm backend.

**The lesson:** Wasm can handle enormous codebases and deliver multiplicative gains for pixel-level computation. The SIMD instruction set is the key enabler for image processing workloads.

(Source: [Addy Osmani / Medium](https://medium.com/@addyosmani/photoshop-is-now-on-the-web-38d70954365a); see [Industry Research](../research/01-industry-landscape.md), Case Studies)

---

#### eBay: Speed Is Not Enough (50 FPS, but 60% Accuracy)

eBay ported their C++ barcode scanning library to Wasm for the mobile web seller experience, achieving **50 FPS** average scanning speed. But single-library accuracy was only **60%** within the timeout threshold. The production solution used **3 parallel Wasm workers** (C++ port at 50 FPS + BarcodeReader at 1 FPS + ZBar Wasm at 15 FPS), where "what any two libraries failed to decipher, was successfully recognized by the third." The result: **30% increase in listing completion rate**.

**The lesson:** Raw speed is necessary but not sufficient. System design still matters. Wasm makes a particular operation faster; it does not make the overall system better unless the system is architected to exploit that speed.

(Source: [eBay Engineering](https://innovation.ebayinc.com/stories/webassembly-at-ebay-a-real-world-use-case/); see [Industry Research](../research/01-industry-landscape.md), Case Studies)

---

#### Microsoft Clipchamp: Video Editing (4K in the Browser, 2.3x SIMD Speedup)

Clipchamp runs its entire video processing pipeline in-browser using WebAssembly, including a Wasm build of FFmpeg. The architecture is a reference implementation for browser-based video processing:

```
Source Video ──> [Wasm FFmpeg Decoder] ──> Raw Frames
                                              │
                                   [Wasm Compositor + Effects]
                                              │
                            [Wasm FFmpeg Encoder] ──> MP4 Output
```

**Results:**
- **2.3x performance improvement** with SIMD, achieved in under one month of engineering effort
- 4K video decoding and encoding in the browser
- **97% monthly growth** in PWA installations
- **9% higher retention** for PWA users vs. standard desktop users

The decoder and encoder stages use **WebCodecs API** stubs inside the FFmpeg Wasm build for hardware-accelerated codec access, while compositing and effects run in pure Wasm for portability.

**The lesson:** For media processing, Wasm + SIMD is a proven production stack. The one-month SIMD integration timeline shows that targeted optimizations can deliver quickly when the workload is genuinely compute-bound.

(Source: [web.dev case study](https://web.dev/case-studies/clipchamp))

---

#### Cloudflare Workers: Wasm at the Edge (10M+ Req/sec)

Cloudflare's edge computing platform processes **10 million+ Wasm-powered requests per second** with cold starts under **1 ms** (vs. 100-1000 ms for AWS Lambda). This is the server-side Wasm story -- not browser -- but it demonstrates Wasm's viability for high-throughput, low-latency workloads. Cloudflare supports Rust, C++, and Go compiled to Wasm, with automatic global scaling across hundreds of cities.

(Source: [Cloudflare Blog](https://blog.cloudflare.com/webassembly-on-cloudflare-workers/))

---

#### American Express: Enterprise-Scale FaaS

American Express built an internal **Function-as-a-Service platform** using WebAssembly (via [wasmCloud](https://wasmcloud.com/)), replacing traditional containers. Key results:

- Lightweight, low-latency function execution with full sandboxing
- Security decorator automatically added to each Wasm component
- Single high-density runtime with function isolation
- Database-specific code still runs as native binaries (hybrid approach)

According to [The New Stack](https://thenewstack.io/amexs-faas-uses-webassembly-instead-of-containers/), this "may be the largest commercial Wasm deployment to date." The architecture uses the **Wasm Component Model** for composability, with security filters compiled into the Wasm binary itself.

**The lesson:** For server-side sandboxing and function isolation, Wasm's security model provides genuine value over containers. This is relevant to PyBend's potential future as a multi-tenant platform.

---

### Failure Stories: When Wasm Backfires

Success stories get the headlines. The failures are equally instructive.

#### Blazor WebAssembly: The Runtime Tax

Blazor, Microsoft's .NET-in-the-browser framework, represents **41.7% of identified Wasm modules** on the web (the largest single source by count). However, it exemplifies the wrong approach to Wasm:

- **Initial load: ~10 seconds** on low-end mobile devices for bootstrapping the .NET runtime
- **AOT compilation payload: 10-20+ MB** (vs. typical 50-500 KB for targeted Wasm modules)
- **Rendering regression in .NET 9:** applications "frequently freeze for seconds"
- A [GitHub issue with 500+ upvotes](https://github.com/dotnet/aspnetcore/issues/41909) calls bundle size "the worst and biggest problem ever"

**The lesson:** Shipping an entire language runtime to the browser via Wasm is the anti-pattern. Wasm shines when used for *targeted compute kernels*, not as a general-purpose application platform. Blazor uses Wasm as a runtime, not a performance tool -- and the result is the opposite of what Figma achieved.

(See [Industry Research](../research/01-industry-landscape.md), Failure Stories section)

---

#### The 42% Survival Rate

Research testing **54,000+ relatively simple C programs** for Wasm compilation found that only **42% survived** -- meaning 58% of naively compiled C programs either failed or exhibited undefined behavior in Wasm. Wasm compilation is not a magic wand; it requires understanding of memory management, ABI differences, and the Wasm execution model.

(See [Industry Research](../research/01-industry-landscape.md), Failure Stories section)

---

### Adoption Statistics

Real-world adoption tells a more nuanced story than the success headlines suggest:

| Metric | Value | Source |
|---|---|---|
| Sites serving Wasm modules (desktop) | **0.35%** (~43,000 sites) | [HTTP Archive 2025](https://almanac.httparchive.org/en/2025/webassembly) |
| Chrome page loads encountering Wasm | **4.5% -> 5.5%** (2024-2025) | [Chrome Platform Status](https://chromestatus.com) |
| Usage among top 1,000 sites | **2.0%** desktop / **1.27%** mobile | HTTP Archive 2025 |
| Developers using Wasm in production | **41%** | [CNCF State of Wasm](https://www.cncf.io/wp-content/uploads/2023/09/The-State-of-WebAssembly-2023.pdf) |
| Developers with no Wasm experience | **57%** | CNCF State of Wasm |
| Non-adopters: "not applicable to us" | **39%** | CNCF State of Wasm |

The plateau in raw site count (0.35%) is misleading. Two countervailing trends: Wasm usage is **concentrating in high-traffic sites** (2% of top 1,000 vs. 0.35% of the long tail), and **Chrome Platform Status shows 5.5% of page loads** encounter Wasm -- meaning fewer sites serve it, but those sites serve far more traffic.

**Source language distribution tells its own story.** Of the Wasm modules detected on the web in 2025:

```
Language / Toolchain        Desktop    Mobile     What it tells us
───────────────────────────────────────────────────────────────────
.NET / Mono / Blazor        41.7%      38.7%     CRUD apps using Wasm as runtime
Emscripten (C/C++)          10.1%       7.8%     Native code ports (strong use case)
Scala                        3.6%       3.4%     JVM language experimentation
AssemblyScript               2.4%       2.3%     JS teams dipping into Wasm
Rust                         1.5%       2.2%     Performance-focused modules
Go / TinyGo                 ~0.1%     ~0.1%     Early adopters
Unknown / Unidentified      40.5%      45.5%     Mix of everything
───────────────────────────────────────────────────────────────────
```

The dominance of .NET/Blazor (41.7%) is surprising and somewhat misleading. Many Blazor deployments are standard CRUD applications using Wasm as a runtime platform -- not the compute-heavy use case where Wasm shines. The Emscripten (C/C++) and Rust categories better represent the performance-oriented deployments discussed in this report.

**Growth trajectory:**

```
Year    Sites Serving Wasm    Trend            Context
──────────────────────────────────────────────────────
2021    0.04%                 Baseline
2022    0.26%                 +550%            Blazor boom
2023    0.34%                 +31%
2024    0.36%                 +6%              Plateau
2025    0.35%                 Flat             Concentration in high-traffic
──────────────────────────────────────────────────────
```

The plateau in raw site count is counterbalanced by concentration in high-traffic sites. The technology is settling into its natural niche rather than achieving universal adoption -- exactly what you would expect from a specialized performance tool.

**The bottom line:** Wasm is adopted by the companies that need it and ignored by the companies that don't. The 39% who say "not applicable" are, for the most part, correct. PyBend falls into the "not applicable" category today.

(See [Industry Research](../research/01-industry-landscape.md), Adoption Statistics section)

### Developer Survey Deep-Dive

The CNCF State of Wasm surveys (2023-2025) provide insight into *why* teams adopt Wasm and *why* they don't:

**Top cited benefits by adopters:**

| Benefit | % Citing | Relevance to PyBend |
|---|---|---|
| Faster execution | **47%** | Low -- our bottleneck is network |
| Cross-platform compatibility | **46%** | Medium -- shared validation potential |
| Improved security (sandboxing) | **45%** | Medium -- future plugin system |
| Portability | **44%** | Medium -- write-once validation |

**Top use cases reported:**

| Use Case | % of Adopters | Relevance to PyBend |
|---|---|---|
| Web development (browser) | **71%** | Not at current compute profile |
| Plugin / extension environment | **32%** | Future potential (Trigger C) |
| Backend services | **24%** | Not relevant |
| Serverless functions | **21%** | Not relevant |

**Why non-adopters stay away:**

| Reason | % of Non-Adopters | Our Assessment |
|---|---|---|
| "Not applicable to our needs" | **39%** | Accurate for PyBend today |
| "Not sure why we're not using it" | **25%** | We are sure -- we've done the analysis |
| Insufficient tooling | **15%** | Tooling has improved significantly |
| Lack of expertise | **12%** | Real barrier; 3-6 month ramp-up |

(Source: [CNCF State of WebAssembly 2023-2025](https://www.cncf.io/wp-content/uploads/2023/09/The-State-of-WebAssembly-2023.pdf))

---

### Performance Benchmarks: What the Data Actually Shows

Industry benchmarks reveal a more complex picture than "Wasm is faster":

| Domain | Typical Wasm Speedup | Source |
|---|---|---|
| Image processing (SIMD) | **3-4x avg, 80-160x peak** | Adobe Photoshop |
| Spreadsheet calculation | **2x** | Google Sheets (WasmGC) |
| Barcode scanning | **50 FPS** (vs ~5 FPS JS) | eBay |
| Cryptography (ECDH) | **12.3x** | IEEE research |
| Video encoding (SIMD) | **2.3x** | Clipchamp |
| Force-layout simulation | **5-8x** | D3.js Wasm port |
| Design tool load time | **3x** | Figma |

But the academic data is more nuanced:

| Input Size | Wasm Faster (% of benchmarks) | Average Speedup |
|---|---|---|
| Extra-small | **97.6%** | **26.99x** |
| Small | **95.1%** | **8.22x** |
| Medium | Mixed -- some benchmarks **flip to JS** | **6.70x** (when faster) |
| Large | Mixed -- memory overhead increases | Variable |

**The critical insight:** Wasm's advantage shrinks as input size grows because memory allocation and boundary-crossing costs increase. For small, tight compute kernels on numeric data, Wasm is dominant. For large, complex, object-rich workloads, JavaScript's JIT catches up. PyBend's workloads fall into the latter category.

### Where Wasm Wins Decisively vs. Where JS Wins or Ties

Understanding the crossover point is essential for investment decisions. Research from [BenchmarkingWebAssembly](https://benchmarkingwasm.github.io/BenchmarkingWebAssembly/) reveals:

**Wasm wins when:**

| Workload Type | Why Wasm Wins | Real-World Example |
|---|---|---|
| Tight numeric loops | Predictable types, no GC pauses, SIMD | Image/audio processing filters |
| Cryptography | Constant-time operations, no JIT deoptimization | libsodium compiled to Wasm |
| Codecs / compression | Bit manipulation, no object allocation | FFmpeg, Brotli, zstd in browser |
| Physics / simulation | Matrix math, SIMD, deterministic floats | Game engines (Unity, Godot) |
| Porting native code | Existing C/C++/Rust already optimized | Figma, AutoCAD, Photoshop |
| AI / ML inference | Matrix operations, SIMD, threading | TensorFlow.js Wasm backend |
| Parsing / compilation | Deterministic control flow, no deoptimization | Tree-sitter, SQLite in browser |

**JS wins or ties when:**

| Workload Type | Why JS Wins | Explanation |
|---|---|---|
| DOM manipulation | Wasm cannot access DOM; must call through JS | Every DOM call crosses the interop boundary |
| Small/simple logic | V8/SpiderMonkey optimize JS extremely well | JIT-compiled JS is near-native for simple operations |
| String-heavy operations | Wasm linear memory lacks native string support | JS strings are engine-native; Wasm must manage encoding |
| Async I/O / network | Wasm cannot call Web APIs directly | `fetch()`, WebSocket, IndexedDB -- all go through JS |
| Object-heavy code | JS objects are engine-optimized (hidden classes) | Wasm structs in linear memory lack engine-level optimization |
| JSON processing | V8's `JSON.parse` is highly optimized C++ | Wasm JSON parsers are slower than the native engine parser |
| Rapid prototyping | JS has instant feedback, no compile step | Development velocity matters |

**Applying this to PyBend's specific operations:**

| PyBend Operation | Input Type | Workload Type | Winner |
|---|---|---|---|
| Schema parsing | JSON object (2-10KB) | JSON processing | **JS** (V8's JSON.parse is native C++) |
| `prototype()` property loop | 10-20 JS objects | Object manipulation | **JS** (V8 hidden classes optimize this) |
| Form string generation | Schema + values | String concatenation | **JS** (V8 string ops are highly tuned) |
| Permission rule evaluation | 3-10 conditionals | Small logic branches | **JS** (trivial computation) |
| Matrix message routing | TX object (< 100 bytes) | Map lookup | **JS** (V8 Map is near-optimal) |
| Batch normalize 1,000+ entities | 500KB+ JSON | Data transformation | **Wasm** (if data stays in Wasm memory) |
| Client-side full-text search 10K+ | Text corpus | Sequential scan/index | **Wasm** (compiled index like tantivy) |

The pattern is clear: **every current PyBend operation falls in the "JS wins" column**. Only hypothetical future operations at much larger scale would cross into Wasm territory.

(Source: [IEEE](https://ieeexplore.ieee.org/document/10277917/), [BenchmarkingWebAssembly](https://benchmarkingwasm.github.io/BenchmarkingWebAssembly/); see [Industry Research](../research/01-industry-landscape.md), Performance Benchmarks section and [Technical Deep Dive](../research/02-technical-deep-dive.md), Section 13)

---

## 3. ⚡ Technical Architecture Overview

> 💡 **Key Finding:** Wasm's technical strengths -- predictable performance, SIMD, threading, memory isolation -- are precisely matched to compute-heavy, numeric workloads. Its weaknesses -- no DOM access, serialization overhead at the JS boundary, no direct Web API access -- are precisely the characteristics that dominate web application frameworks like PyBend.

### The JS-Wasm Boundary: Where Performance Lives or Dies

The most misunderstood aspect of Wasm integration is the cost of crossing between JavaScript and WebAssembly. The call itself is cheap (~2.5 nanoseconds for a monomorphic scalar call after browser optimizations). The real cost is **data marshaling**:

| Data Type | Marshaling Strategy | Overhead |
|---|---|---|
| `i32`, `i64`, `f32`, `f64` | Direct register pass | **~2-5 ns** (negligible) |
| Strings | Copy into linear memory, pass pointer+length | **O(n)** -- significant for large strings |
| Arrays / TypedArrays | Share via linear memory view (zero-copy possible) | **Near-zero** if pre-allocated |
| Complex objects / JSON | Serialize -> copy -> deserialize | **Expensive** -- avoid in hot paths |
| `ArrayBuffer` / `SharedArrayBuffer` | Direct memory view (zero-copy) | **Zero** -- ideal pattern |

Measured call overhead (Firefox, 100M iterations) shows the improvements made by browser vendors:

| Call Pattern | Before Optimization | After Optimization | Improvement |
|---|---|---|---|
| JS -> Wasm | ~5,500 ms | **~450 ms** | **12x** |
| Wasm -> JS | ~750 ms | **~450 ms** | 1.7x |
| JS -> Wasm (monomorphic) | ~5,250 ms | **~250 ms** | **21x** |

After optimization, **JS-to-Wasm calls are faster than non-inlined JS-to-JS calls** in Firefox. At ~250ms / 100M calls, each monomorphic boundary crossing costs approximately **2.5 nanoseconds** -- comparable to a virtual function dispatch in native C++.

(Source: [Mozilla Hacks](https://hacks.mozilla.org/2018/10/calls-between-javascript-and-webassembly-are-finally-fast-%F0%9F%8E%89/); see [Technical Deep Dive](../research/02-technical-deep-dive.md), Section 2)

**The design rule:** if your data crosses the JS-Wasm boundary as numbers or TypedArrays, overhead is negligible. If it crosses as JSON objects, strings, or complex data structures, the serialization can consume **up to 60% of execution time** ([arxiv](https://arxiv.org/pdf/2511.01888)).

For PyBend, virtually all data is JSON objects (schemas, entity data, permission rules). This is the worst case for Wasm boundary crossing. Every schema is a tree of nested objects with string keys. Every entity is a dictionary of mixed-type values. Every permission rule is a recursive structure of `{rule, op, rules}` objects. None of these can be expressed as TypedArrays without a serialization step that would dwarf the computation.

### The Practical Guidelines

| Call Frequency | Recommendation |
|---|---|
| < 100 calls/frame | Interop overhead is **invisible** |
| 100-10,000 calls/frame | Batch operations, prefer TypedArray views |
| > 10,000 calls/frame | Restructure: move the loop into Wasm, call once per frame |

**PyBend's profile:** The framework makes roughly 50-200 messages per page load through the Matrix actor system, with each message routing taking <0.05ms. This is firmly in the "invisible overhead" tier -- but only because the messages stay in JavaScript. Moving routing to Wasm would add boundary-crossing overhead to each message for zero compute benefit.

### Memory Model

Wasm operates on a **linear memory** -- a contiguous, byte-addressable, bounds-checked array. This is fundamentally different from JavaScript's garbage-collected heap:

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

Key properties:

- **Bounds-checked**: Every load/store is validated against the current memory size. Out-of-bounds access traps deterministically (not undefined behavior like C).
- **Isolated**: Each module gets its own linear memory. No pointer arithmetic can reach outside it.
- **Growable**: `memory.grow(n)` adds `n` pages (64 KiB each). Growth can fail if the engine runs out of address space.
- **JS-accessible**: `WebAssembly.Memory.buffer` exposes it as an `ArrayBuffer`, enabling zero-copy data sharing via `TypedArray` views.

**Memory limits matter for planning:**

| Configuration | Max Address Space | Browser Support | Notes |
|---|---|---|---|
| Wasm32 (default) | 4 GB | All browsers | Standard; most tools target this |
| Memory64 (Wasm 3.0) | 16 GB (browser-imposed) | Chrome 133+, Firefox 134+, Safari 18.4+ | 64-bit pointers |
| Mobile browsers | 1-2 GB practical limit | Varies by device | Design for graceful degradation |

(Source: [V8 Blog: 4GB Wasm Memory](https://v8.dev/blog/4gb-wasm-memory); see [Technical Deep Dive](../research/02-technical-deep-dive.md), Section 3)

### SIMD: The Performance Multiplier

Wasm SIMD (Single Instruction, Multiple Data) operates on **128-bit vectors**, processing 4x `f32`, 2x `f64`, 4x `i32`, 8x `i16`, or 16x `i8` values in a single instruction. Browser support is strong at **~93% globally** (Chrome 91+, Firefox 89+, Safari 16.4+).

Measured performance gains from production and research:

| Workload | Without SIMD | With SIMD | Speedup | Source |
|---|---|---|---|---|
| Array operations | 1.4 ms | 0.231 ms | **6x** | byteiota 2025 |
| Matrix multiplication | Baseline | +SIMD | **9.5x** | byteiota 2025 |
| Game engine (Godot) | Baseline | +Wasm SIMD | **1.5-2x** | Godot Engine |
| Scientific computing (Node 22) | Baseline | +SIMD | **10x** | markaicode 2025 |
| Image processing | Baseline | +SIMD | **4-8x** | Various |
| Adobe Photoshop (Halide) | Baseline | +SIMD | **80-160x** | Adobe |
| Clipchamp video | Baseline | +SIMD | **2.3x** | web.dev |

> ⚠️ **Warning:** Peak SIMD benchmarks (10-15x) represent best-case scenarios on perfectly vectorizable code. **Real-world applications typically see 1.5-4x** from SIMD alone because not all code paths vectorize, memory bandwidth becomes the bottleneck, and branch-heavy logic does not benefit. The Godot engine's measured 1.5-2x is more representative of complex application performance. That said, the difference between 30fps and 60fps is the difference between "sluggish" and "smooth."

**Relevance to PyBend:** SIMD operates on numeric arrays -- pixel buffers, audio samples, physics vectors, matrix data. PyBend's data is JSON schemas, HTML strings, and permission rule trees. There is no vectorizable hot path in our codebase. SIMD is irrelevant to our workload.

(See [Technical Deep Dive](../research/02-technical-deep-dive.md), Section 5)

### Threading: True Parallelism in the Browser

Wasm threading is built on three browser primitives: **Web Workers** (separate execution contexts), **SharedArrayBuffer** (shared linear memory between workers), and **Atomics** (synchronization operations). Emscripten provides a full pthreads implementation on top of these.

```
   Wasm Threading Architecture
   ┌───────────────────────────────────────────────────────────┐
   │  Main Thread                          Worker Thread(s)    │
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

**Caveats that affect real-world adoption:**

- **Cross-origin isolation required**: Headers `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` must be set. These break third-party embeds (iframes, CDN resources without CORP headers). Google Earth hit this directly: Firefox disabled SharedArrayBuffer for a period, resulting in degraded performance.
- **Main thread cannot block**: `Atomics.wait()` throws on the main thread. Work must be dispatched to workers.
- **Worker startup cost**: Creating a Web Worker has ~5-50ms overhead. Pre-create a worker pool for latency-sensitive applications.
- **Memory overhead**: Each worker gets its own JS heap + stack. Typical per-worker cost: 2-8 MB.

**Relevance to PyBend:** PyBend's frontend performs no sustained parallel computation. The actor message bus is single-threaded by design. Schema processing, form generation, and permission checks are sequential operations on small data. Threading would add overhead without parallelism to exploit.

(See [Technical Deep Dive](../research/02-technical-deep-dive.md), Section 4)

### Security Model

Wasm's security is **stronger than JavaScript's by design** because it starts with zero capabilities:

```
   JavaScript:                      WebAssembly:
   ┌────────────────────────┐       ┌────────────────────────┐
   │ Full Web API access    │       │ NO Web API access      │
   │ DOM, fetch, localStorage│      │ NO DOM, NO fetch       │
   │ eval(), Function()     │       │ NO code generation     │
   │ Prototype chain access │       │ NO prototype access    │
   │ Global object access   │       │ NO global object       │
   └────────────────────────┘       └────────────────────────┘
   Security: RESTRICT what the      Security: GRANT only what the
   runtime can do (blacklist)       host provides (whitelist)
```

Wasm modules can only access what the host (JavaScript) explicitly provides via imports. This capability-based model makes Wasm attractive for **sandboxing untrusted code** -- a potential future use case for PyBend's plugin architecture.

**Known attack surfaces:**

| Attack Vector | Risk Level | Mitigation |
|---|---|---|
| Memory corruption within linear memory | Medium | Bounded -- cannot escape sandbox, but can corrupt Wasm-internal state |
| Control flow hijack (ROP-style) | Low | Mitigated by structured control flow validation |
| Side-channel (Spectre) | Low-Medium | Mitigated by cross-origin isolation |
| Supply chain (malicious .wasm) | Medium | Same as JS supply chain risk; SRI hashes |
| Sandbox escape (engine bugs) | Very Low | Rare but critical; keep browsers updated |

**For PyBend's future:** If the framework evolves toward a multi-tenant model where users can define custom model methods, Wasm sandboxing via `wasmtime-py` on the backend would provide memory-safe isolation at near-native speed. This is the one Wasm use case where PyBend's architecture genuinely benefits -- not from performance, but from the security model. We have flagged this as Trigger C in the recommendations.

(See [Technical Deep Dive](../research/02-technical-deep-dive.md), Sections 10 and 12)

### Debugging and Profiling

Wasm debugging has matured but still lags behind JavaScript tooling:

| Feature | Chrome DevTools | Firefox DevTools |
|---|---|---|
| Step through original source (C++/Rust) | DWARF (Chrome 114+, no flags) | Source maps |
| Set breakpoints in source | Yes | Yes |
| Inspect variables | Yes (DWARF-based) | Partial |
| Memory inspector | Yes (linear memory viewer) | Yes |
| Performance profiling | Function-level in flame chart | Basic |

Starting with Chrome 114, **no experimental flags** are needed to debug Wasm with original source code. When a `.wasm` file includes DWARF debug info, Chrome DevTools shows the original C++/Rust source, allows breakpoints, and displays variable values with original names.

**The catch:** V8 tiers down to Liftoff (baseline) when DevTools is open, which means debugging and profiling cannot happen simultaneously with production-level performance. For micro-benchmarks, `performance.now()` wrapping is more reliable.

**Relevance to PyBend:** If Wasm were adopted, debugging Wasm modules would require Rust/C++ debugging skills in addition to browser DevTools proficiency. This adds to the key-person dependency risk identified in the risk register.

(See [Technical Deep Dive](../research/02-technical-deep-dive.md), Section 11)

### Toolchain Landscape

The choice of source language and toolchain significantly affects binary size, performance, and developer experience:

| Toolchain | Source Lang | Binary Size (benchmark) | Execution Time (Chrome) | Best For |
|---|---|---|---|---|
| **wasm-pack** (Rust) | Rust | 74 KB (44 KB .wasm + 30 KB JS) | **2,982 ms** | Performance-critical modules |
| **Emscripten** | C/C++ | 100-500 KB+ | ~3,000-3,500 ms | Porting existing C/C++ |
| **AssemblyScript** | TypeScript-like | **4.7 KB** | 6,405 ms | Small modules, JS teams |
| **TinyGo** | Go | 37 KB | 9,717 ms | Go developers |

*Benchmark: 100K random values, copied 500x, stable-sorted, 5 reps. Source: [Ecostack](https://ecostack.dev/posts/wasm-tinygo-vs-rust-vs-assemblyscript/)*

**For a team considering Wasm, the language choice has major implications:**

| Team Background | Recommended Language | Rationale |
|---|---|---|
| Systems / performance team | **Rust** | Best performance + safety, rich Wasm tooling |
| Existing C/C++ codebase | **C/C++ (Emscripten)** | Port without rewrite, proven path |
| Frontend / TypeScript team | **AssemblyScript** | Familiar syntax, smallest output |
| Go backend team | **TinyGo** | Leverage existing knowledge, accept perf tradeoff |

(See [Technical Deep Dive](../research/02-technical-deep-dive.md), Sections 6 and 7)

### Integration Patterns

Four established patterns exist for integrating Wasm into web applications:

```
Pattern 1: Thin Wasm Kernel + JS Glue (Recommended for Most)
─────────────────────────────────────────────────────────────
  JS Layer (DOM, events, network, state)
       │
       │  ← JS-Wasm boundary (TypedArray views)
       │
  Wasm Kernel (image processing, physics, crypto)

Who uses this: Squoosh, TensorFlow.js, libsodium.js


Pattern 2: Full Wasm Application
─────────────────────────────────
  JS Bootstrap (~1 KB)
       │
  Full Wasm App (UI via Canvas/WebGL, all logic)

Who uses this: Figma, AutoCAD, Photoshop, game engines


Pattern 3: Hybrid Worker Architecture
──────────────────────────────────────
  Main Thread (JS UI)  ←─ postMessage ─→  Worker(s) (Wasm compute)

Who uses this: Video editors, ML inference, data viz


Pattern 4: Progressive Enhancement
───────────────────────────────────
  Wasm available?  ─→ Yes: Use Wasm   ─→ No: JS fallback

Who uses this: Feature detection scenarios
```

**Why each pattern does or does not fit PyBend:**

| Pattern | Fit for PyBend | Reasoning |
|---|---|---|
| **1: Thin Kernel** | Possible (future) | Would work for an isolated compute module (validation, batch processing). JS framework stays intact. |
| **2: Full Wasm App** | Incompatible | PyBend is a DOM-based framework. Moving to Canvas/WebGL rendering would require a complete rewrite. |
| **3: Hybrid Worker** | Possible (future) | Would work if sustained compute (e.g., 10K entity processing) is needed. Adds async communication complexity. |
| **4: Progressive Enhancement** | Possible (future) | Provides graceful fallback. But requires maintaining two implementations -- the duplication Wasm was supposed to eliminate. |

If Wasm is ever adopted for PyBend, **Pattern 1 with a lazy-loading variant** is the right starting point. The Wasm module loads asynchronously, falls back to JS until ready, and handles a single well-defined compute function. The JS framework never depends on Wasm for correctness -- only for speed.

(See [Technical Deep Dive](../research/02-technical-deep-dive.md), Section 14)

### The Ecosystem Trajectory: What Is Coming

Two upcoming developments matter for strategic planning:

**WASI 1.0 (Expected late 2026 / early 2027):** This standardizes a POSIX-like system interface for Wasm outside the browser -- file I/O, networking, clocks, random numbers. When it ships, a single Wasm module could run identically in the browser, on the server, and at the edge. WASI 0.3.0 (just shipped February 2026) adds native async support and `stream<T>` / `future<T>` types. For PyBend, this could eventually enable shared validation logic compiled once and deployed to both `wasmtime-py` on the backend and `WebAssembly.instantiateStreaming` in the browser.

According to [The New Stack](https://thenewstack.io/wasi-1-0-you-wont-know-when-webassembly-is-everywhere-in-2026/), "You won't know when WebAssembly is everywhere in 2026" -- the expectation is that Wasm will become invisible infrastructure, embedded in platforms without users or developers being aware of it.

**ESM Integration (Phase 3):** When `import module from './validator.wasm'` works cross-browser (expected late 2026 to mid-2027), the integration friction for buildless architectures like PyBend drops dramatically. Currently, loading a Wasm module requires `WebAssembly.instantiateStreaming(fetch(...))` -- an async operation that complicates synchronous module loading. Chrome and Firefox have partial support as of early 2026; Safari/WebKit lags behind. This is the single most important ecosystem signal for PyBend's Wasm timeline.

**WasmGC maturity:** The garbage collection extension (Wasm 3.0) is now production-ready in all major browsers. This is most relevant for managed languages (Java, Kotlin, Dart) compiling to Wasm. Google Sheets' production deployment is the proof point. For PyBend, WasmGC is relevant only if the team ever considers writing Wasm modules in a GC-managed language rather than Rust or C++.

**The Component Model:** The [WebAssembly Component Model](https://component-model.bytecodealliance.org/) standardizes how Wasm modules compose into larger applications -- typed interfaces for cross-language interop, sandboxing, and linking components from different languages. American Express already uses this for function composition. For PyBend, this becomes relevant if the framework evolves toward a plugin architecture where third-party code runs in sandboxed Wasm components.

### Investment Signals: Follow the Money

The investment landscape validates Wasm's strategic importance without implying universal applicability:

| Event | Date | Signal Strength |
|---|---|---|
| **Akamai acquires Fermyon** | Dec 2025 | Strongest signal -- largest CDN buys leading Wasm startup |
| **Fermyon prior funding** | -- | $20M from Insight Partners, Amplify Partners |
| **Bytecode Alliance** (Mozilla, Fastly, Intel, Microsoft) | Ongoing | Joint governance validates cross-industry commitment |
| **CNCF incubation: wasmCloud** | 2024 | Cloud-native ecosystem endorsement |
| **Sapphire Ventures analysis** | 2024 | Identifies Wasm as "compute's next paradigm shift" |

Notable Wasm startups: Fermyon (now Akamai), Wasmer (universal Wasm runtime, supports 20+ languages), Cosmonic (distributed Wasm applications), Suborbital (Wasm for secure serverless). The venture capital attention is focused on **server-side and edge Wasm**, not browser Wasm -- further confirming that browser Wasm is a mature tool for specific use cases, not a growth market in itself.

(See [Industry Research](../research/01-industry-landscape.md), Market Size section; [Technical Deep Dive](../research/02-technical-deep-dive.md), Sections 8 and 12; [Our Stack Analysis](../research/04-our-stack-relevance.md), Section 4)

---

## 4. 🔍 Our Current Architecture Assessment

> 💡 **Key Finding:** PyBend's frontend spends 84% of wall-clock time on network I/O, 12% on DOM rendering, and 3% on CPU computation. Every CPU-bound operation completes in single-digit milliseconds or less. There is no compute bottleneck for Wasm to solve.

### PyBend's Architecture: How Data Flows

To understand why Wasm does not fit, you need to understand how PyBend actually works. The framework implements a schema-driven architecture where a Python model definition is the single source of truth for the entire stack. Here is the complete data flow for a typical page load:

```
  Browser                                          Server (Python/FastAPI)
  ========                                         ======================

  matrix.html
      |
      v
  <ntt-list model="Product">                       GET /Product
      |                                                 |
      v                                                 v
  NTT.SCHEMA(data)               <─── HTTP ───    ProtoModel.schema()
      |                                            [cached after 1st call]
      |─── Register $defs (nested models)               |
      |─── prototype(addr,schema,href)                  |
      |       |                                         |
      |       +── DynamicClass created                  |
      |       +── Field getters/setters via             |
      |       |   Object.defineProperty                 |
      |       +── Method stubs for @expose_route        |
      |                                                 |
      v                                                 v
  DynamicClass.call('READ')      ─── HTTP ──>    GET /products?limit=20
      |                                                 |
      v                                                 v
  DynamicClass.READ(data)        <─── HTTP ───    sqlite_storage.list()
      |                                            [SQL + FK hydration]
      |─── normalizePopulated() per entity
      |─── new DynamicClass(data) per entity
      |
      v
  <ntt-item>.DESCRIBE()
      |─── Permissions.canAction()   [CPU: <0.05ms/call]
      |─── Formidable.getForm()      [CPU: 1-5ms, HTML strings]
      |─── render() -> innerHTML     [DOM: 2-8ms]
      |─── #bindEvents()             [DOM: <1ms]
```

Every arrow labeled "HTTP" is a network round-trip (50-200ms). Every item labeled "CPU" is measured computation. Every item labeled "DOM" is browser rendering. The ratio tells the story: the network arrows dominate; the CPU items are rounding errors.

### PyBend's Compute Profile

We profiled every operation by frequency, duration, and bottleneck type. The full analysis is documented in [Our Stack Relevance](../research/04-our-stack-relevance.md), Section 1. Here is the summary:

```
  Time breakdown for a typical page load (Products + Comments):

  [===========================] Network: Schema fetch          120ms
  [=]                           CPU: SCHEMA parse + prototype    2ms
  [=============================] Network: Data fetch           150ms
  [=]                           CPU: Instance creation + norm     5ms
  [===]                         DOM: 20x render()               40ms
  [=]                           CPU: Permission checks            1ms
  [=]                           CPU: Form generation              3ms

  Total: ~321ms
  Network: ~270ms (84%)
  DOM:     ~40ms  (12%)
  CPU:     ~11ms  (3%)
```

### Subsystem-by-Subsystem Analysis

We evaluated every candidate subsystem for Wasm integration. The verdict is unanimous: **none of PyBend's current compute paths would benefit from Wasm.**

| Subsystem | CPU Time | Frequency | Bottleneck | Wasm Gain | Verdict |
|---|---|---|---|---|---|
| Schema parse + `prototype()` | <2ms | 1x per model | Trivial CPU | Negligible (boundary overhead would make it slower) | **No** |
| Form generation (`Formidable`) | 1-5ms | Per-render | DOM, not strings | Marginal (HTML strings cross boundary; DOM stays in JS) | **No** |
| Permission evaluation | <0.05ms | Per-entity | Trivial CPU | Zero (marshaling rules costs more than evaluating them) | **No** |
| Matrix message routing | <0.05ms | Per-message | Trivial CPU | Negative (serializing TX objects costs more than routing) | **No** |
| `normalizePopulated()` | <0.25ms | Per-entity | Trivial CPU | Future candidate at >1,000 entities | **Monitor** |
| Backend schema generation | 10-50ms (cached) | Once at startup | One-time | None (already cached; Pydantic lock-in) | **No** |
| SQLite query + hydration | 1-20ms | Per-request | I/O | Near zero (SQLite is already C) | **No** |
| **Shared validation** | N/A | Cross-stack | Code duplication | **High (portability)** -- but not performance | **Future** |

### Why Each Candidate Fails

**Schema parsing and `prototype()`** -- `NTT.js:663` creates a DynamicClass by iterating ~10-20 fields and calling `Object.defineProperty` per field. This takes <2ms. Moving it to Wasm would require serializing the JSON Schema into Wasm memory, building class descriptors there, and returning them to JS for the actual `Object.defineProperty` calls (which cannot happen in Wasm). The boundary crossing alone would exceed the 2ms it currently takes. (See [Our Stack Analysis](../research/04-our-stack-relevance.md), Section 2.1)

**Form generation (`Formidable.getForm()`)** -- `form.js:17` iterates schema properties, checks permissions, and generates HTML strings via concatenation. The bottleneck is not string generation (which JS handles efficiently) but the subsequent `innerHTML` assignment and event binding in the DOM layer. Wasm cannot touch the DOM, and the generated HTML strings would need to cross the JS-Wasm boundary. (See [Our Stack Analysis](../research/04-our-stack-relevance.md), Section 2.2)

**Permission evaluation** -- `Permissions.canAction()` evaluates ABAC rule trees that are 1-3 levels deep, each requiring 3-10 conditional checks. Total time for all permission checks on a 20-entity page: <1ms. The overhead of marshaling rule objects and user state into Wasm memory would exceed the evaluation time itself. (See [Our Stack Analysis](../research/04-our-stack-relevance.md), Section 2.3)

**Matrix message routing** -- `Matrix.inbox()` (`/workspace/src/pybend/static/core/Matrix.js`, line 26) does a string split, a `Map.has()` lookup, and forwards to a child actor's inbox. Each routing decision takes <0.05ms. The JS-Wasm boundary cost per message would exceed the routing cost. Map lookups in V8 are already near-optimal. (See [Our Stack Analysis](../research/04-our-stack-relevance.md), Section 2.4)

**Entity normalization (`normalizePopulated()`)** -- `NTT.js:614` walks entity objects, converts inline populated data back to href strings, and pre-registers child instances. At 20 entities per page, total time is <5ms. At 1,000+ entities, this becomes measurable (~120ms). This is the one subsystem with a plausible Wasm future -- but only at a scale PyBend does not currently operate at. (See [Our Stack Analysis](../research/04-our-stack-relevance.md), Section 2.5)

**Backend schema generation** -- `proto_model.py:199` performs Pydantic introspection, reference collection, access rules injection, and `$defs` resolution. First call takes 10-50ms; subsequent calls hit cache (`deepcopy` only). Reimplementing Pydantic schema generation in Rust would require maintaining parity with Pydantic's evolving API -- an enormous effort for a one-time startup cost that is already solved by caching. (See [Our Stack Analysis](../research/04-our-stack-relevance.md), Section 2.6)

**SQLite query + FK hydration** -- `sqlite_storage.py` performs SQL queries, row-to-dict conversion, and builds href URLs for related entities. The bottleneck is SQLite I/O, and SQLite is already a C library wrapped by Python's sqlite3 module. There is nothing for Wasm to optimize. (See [Our Stack Analysis](../research/04-our-stack-relevance.md), Section 2.7)

### The Buildless Constraint

PyBend's frontend is **buildless** -- no webpack, no npm, no bundler. All JavaScript is vanilla ES Modules served as static files. This is a core philosophical choice that significantly constrains Wasm integration:

| Concern | Impact |
|---|---|
| No npm | Cannot use `wasm-pack` output directly (generates npm packages). Must use `--target web`. |
| No bundler | Cannot rely on webpack's `experiments.asyncWebAssembly`. Must manually fetch/instantiate `.wasm` files. |
| No build step | Pre-compiled `.wasm` binaries must be checked into the repo. No Rust compilation in user workflow. |
| ES Module imports | Cannot `import` `.wasm` directly (ESM integration is Phase 3, not yet cross-browser). |
| Sync module loading | `NTT.SCHEMA()` is currently synchronous. Adding `await` for Wasm init changes the contract. |

The least-friction integration pattern would use **top-level await** in a loader module:

```javascript
// static/wasm/loader.js (hypothetical)
import init, { validate } from './validator.js';
await init();  // Blocks dependents until ready; works in Chrome 89+, Firefox 89+, Safari 15+
export { validate };
```

This is workable but introduces an async dependency into a currently synchronous boot path. It also requires checking pre-compiled `.wasm` binaries into the repository -- acceptable, but a departure from PyBend's current zero-artifact approach.

(See [Our Stack Analysis](../research/04-our-stack-relevance.md), Sections 4 and 8)

### The One Genuine Opportunity: Shared Validation

The most architecturally interesting Wasm opportunity for PyBend is not performance but **portability** -- sharing validation logic between the Python backend and JS frontend via a single Wasm module:

```
  Rust source (single truth)
       |
       +──> wasm-pack --target web    ──> Browser Wasm module
       |
       +──> wasm-pack --target bundler ──> wasmtime-py on server
```

Currently, validation is duplicated:

| Validation | Backend | Frontend |
|---|---|---|
| Field type checking | Pydantic type annotations | `isTypeCompatible()` in `Utils.js` |
| Min/max length | `Field(min_length=...)` | `validationAttrs()` in `form.js` |
| Access rules | `authorize/rules.py` | `Permissions.js` reimplements rule evaluation |
| Required fields | Pydantic `required` | `validationAttrs()` adds `required` attr |

However, this duplication is **intentional and lightweight**. The frontend validation is advisory (HTML5 attributes + UI gating); the backend is authoritative. The backend always re-validates. Eliminating the duplication via shared Wasm adds Rust to the toolchain -- a significant complexity increase -- without fixing a real bug class, since the backend is the final arbiter.

**Trigger to revisit:** If validation parity becomes a recurring source of bugs (i.e., the frontend allows something the backend rejects, causing user-visible errors), the shared Wasm module becomes worth the complexity.

(See [Our Stack Analysis](../research/04-our-stack-relevance.md), Section 5)

---

## 5. 📊 Cost-Benefit Analysis

> 💡 **Key Finding:** The total cost of Wasm integration for a targeted compute module is $65K-$73K for 6 months of engineering, plus ongoing costs for dual build pipeline, cross-browser testing, and Rust hiring premium. For PyBend, the expected performance return is ~10ms saved on a 321ms page load -- a 3% improvement with negative ROI.

### Developer Cost Comparison (US Market, 2026)

| Role | Annual Salary (Median) | Hourly Rate (Contract) | Talent Pool |
|---|---|---|---|
| JavaScript/TypeScript Developer | $74K - $135K | $40 - $80/hr | Very large |
| Rust Developer | $130K - $147K | $50 - $120/hr | Small |
| C++ Developer (Wasm-capable) | $120K - $155K | $55 - $110/hr | Medium |
| WebGPU/Graphics Engineer | $140K - $170K | $70 - $130/hr | Very small |

(Sources: [Glassdoor](https://www.glassdoor.com/Salaries/rust-developer-salary-SRCH_KO0,14.htm), [ZipRecruiter](https://www.ziprecruiter.com/Salaries/Rust-Developer-Salary), [Lemon.io](https://lemon.io/hire/rust-developers/); see [Decision Framework](../research/03-decision-framework.md), Section 5)

### TCO Model: Wasm Module for a Hypothetical Compute Feature

**Scenario:** Adding client-side image processing (resize, filter, compress) -- a workload that *would* benefit from Wasm, unlike PyBend's actual workloads.

| Cost Category | JS-Only | Wasm (Rust) | Delta |
|---|---|---|---|
| Developer salary (1 engineer, 6 months) | $55K - $67K | $65K - $73K | +$10K - $6K |
| Ramp-up time (JS-only team) | 0 weeks | 8 - 16 weeks | Significant delay |
| Build pipeline setup | Existing | +20-40 hours | One-time |
| CI/CD maintenance (annual) | Baseline | +10-15% pipeline time | Ongoing |
| Bundle size impact | None | +50KB - 2MB (.wasm) | Per-load cost |
| Debugging time (per incident) | Baseline | +50-200% per bug | Ongoing |
| Cross-browser testing | Standard | +20% effort | Ongoing |
| Hiring future maintainers | Easy | Harder, premium salary | Long-term risk |
| **Performance gain** | Baseline | **2-5x for image ops** | The ROI |

(See [Decision Framework](../research/03-decision-framework.md), Section 5)

### Break-Even Analysis

The Wasm investment breaks even when:

```
(Performance gain value) x (User impact) > (TCO premium) x (Duration)
```

**Wasm pays off when:**
- Performance is a **core product differentiator** (Figma, Photoshop)
- You already have a **C++/Rust codebase** to port (Google Earth, AutoCAD)
- The compute module is **isolated and stable** (codec, crypto library)
- You are building a **developer tool or platform** where performance is table stakes

**Wasm is hard to justify when:**
- Performance is "nice to have" but not a differentiator
- The team must learn Rust/C++ from scratch
- The computation is already fast enough in optimized JS
- The module requires frequent updates tied to business logic changes

### PyBend's Specific Cost-Benefit

Let's be precise about what Wasm would deliver for *our* stack:

| Investment | Cost |
|---|---|
| Add Rust to toolchain, build Wasm module | 4-8 weeks of 1 engineer |
| Integrate with buildless ES module architecture | 1-2 weeks |
| Cross-browser testing, CI/CD updates | 1-2 weeks |
| Ongoing maintenance, debugging overhead | +15-25% per year |

| Return | Value |
|---|---|
| CPU time saved per page load | ~10ms (from ~11ms to ~1ms) |
| Percentage of total page load saved | **3%** (10ms of 321ms) |
| User-perceivable improvement | **None** (below human perception threshold of ~100ms) |

**The math does not work.** The investment is measured in engineer-months; the return is measured in imperceptible milliseconds. This is not a close call.

### Alternatives That Address the Actual Bottleneck

Instead of Wasm, these investments would address PyBend's real bottleneck (the 84% network time):

| Alternative | Addresses | Expected Impact | Effort |
|---|---|---|---|
| HTTP caching headers for schemas | 120ms schema fetch | -100ms on repeat visits | 2-4 hours |
| Schema preloading (`link rel=preload`) | 120ms schema fetch | -50-80ms first load | 4-8 hours |
| WebSocket for real-time updates | Polling latency | -200-400ms for live data | 1-2 weeks |
| Server-Sent Events for list updates | Stale data | Near-instant updates | 1 week |
| `requestIdleCallback` for deferred rendering | DOM jank | Smoother perceived performance | 1-2 days |

Every item on this list delivers more user-perceivable improvement than Wasm, at a fraction of the cost.

### Scenario Analysis: When Would Wasm Pay Off for PyBend?

Let us model three hypothetical future scenarios where Wasm might become relevant:

**Scenario 1: Large-Scale Client-Side Data Processing**

If PyBend evolves to support client-side filtering, sorting, and searching across 10,000+ entities (e.g., an analytics dashboard or data exploration feature):

| Operation | JS (current) | Wasm (projected) | Data |
|---|---|---|---|
| Sort 10K entities by field | ~15ms | ~5ms | 2-3x improvement |
| Filter 10K entities by criteria | ~8ms | ~3ms | 2-3x improvement |
| Full-text search 10K entities | ~50ms (regex) | ~5ms (compiled index) | 10x improvement |
| Batch normalization 10K entities | ~120ms | ~40ms | 3x improvement |

**Verdict:** At 10K entities, the CPU time becomes noticeable (193ms total JS -> 53ms Wasm). The 140ms savings is perceptible to users. This scenario justifies a targeted Wasm investment -- but only if client-side processing of this scale becomes a product requirement. Currently, PyBend paginates at 20 entities per page, and server-side SQLite handles filtering.

**Scenario 2: Real-Time Collaborative Editing (CRDT)**

If PyBend adds collaborative editing where multiple users edit the same entity simultaneously:

| Operation | JS CRDT | Wasm CRDT (e.g., Automerge) | Data |
|---|---|---|---|
| Merge 1K operations | ~25ms | ~8ms | 3x improvement |
| Merge 10K operations | ~250ms | ~50ms | 5x improvement |
| Conflict resolution | ~5ms | ~1ms | 5x improvement |

**Verdict:** CRDTs are one of the strongest Wasm use cases in the application framework space. Libraries like Automerge ship Rust-compiled-to-Wasm modules that handle the compute-heavy merge operations. If real-time collaboration becomes a product direction, Wasm would be the right tool -- consumed as a library, not as custom-built code.

**Scenario 3: Client-Side Media Processing**

If PyBend adds image upload with client-side resize/compress before upload:

| Operation | JS Canvas | Wasm (Rust/SIMD) | Data |
|---|---|---|---|
| Resize 4K -> 1080p | ~180ms | ~45ms | 4x improvement |
| JPEG compress (quality 80) | ~120ms | ~30ms | 4x improvement |
| Apply filter (blur) | ~200ms | ~25ms | 8x improvement |

**Verdict:** Image processing is the canonical Wasm use case. If PyBend needs it, consuming a pre-built Wasm library (like squoosh-lib) via Pattern 1 (Thin Kernel) would be the right approach -- no Rust required, just load a pre-compiled .wasm binary.

### Team Readiness Assessment for PyBend

Rating our team (1-5) on the dimensions that predict Wasm success:

| Dimension | PyBend Score | Notes |
|---|---|---|
| Systems programming experience | **1** | Python + JS team; no Rust/C++ |
| Performance culture | **2** | Ship features first; profile occasionally |
| Build pipeline sophistication | **1** | Buildless architecture; no multi-language CI |
| Risk tolerance | **3** | Comfortable with emerging patterns |
| Code ownership stability | **4** | Small, stable core team |

**Total: 11 out of 25.** Per the readiness framework in [Decision Framework](../research/03-decision-framework.md), Section 6, this score falls in the **"Not ready; invest in JS optimization first"** range (8-13). The primary gaps are systems programming experience and build pipeline -- exactly the areas where Wasm adoption creates the most friction.

---

## 6. 🗺️ Decision Framework

> 💡 **Key Finding:** The decision tree for Wasm adoption is clear: if you have a measured CPU-bound bottleneck, existing native code to port, and a team with systems programming experience, Wasm is a strong investment. If any of those conditions are missing -- as they are for PyBend -- the decision is equally clear: don't.

### The Decision Tree

```
                    ┌──────────────────────────────────────┐
                    │  Do you have a MEASURED, SPECIFIC     │
                    │  CPU-bound performance problem?       │
                    └───────────────────┬──────────────────┘
                                        │
                              ┌─────────┴─────────┐
                              │                   │
                             YES                  NO ──────> STOP. Optimize JS first.
                              │                              PyBend is here.
                              │
                    ┌─────────┴──────────────┐
                    │ Is the workload        │
                    │ embarrassingly parallel?│
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
                    │ Have you tried optimized JS?      │
                    │ (TypedArrays, SharedArrayBuffer,  │
                    │  Web Workers)                     │
                    └──────────────────┬───────────────┘
                                       │
                              ┌────────┴─────────┐
                              │                  │
                   YES (still too slow)           NO ──> Try optimized JS first.
                              │
                    ┌─────────┴──────────────────────┐
                    │ Do you have existing C++/Rust   │
                    │ code that does this work?       │
                    └─────────┬──────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                   YES                  NO
                    │                   │
           ┌────────┴──────────┐  ┌────┴────────────────────┐
           │  STRONG CASE      │  │ Does team have Rust/C++ │
           │  Port via          │  │ experience?             │
           │  Emscripten or     │  └────┬────────────────────┘
           │  wasm-pack.        │       │
           │  Highest ROI here. │  ┌────┴─────────┐
           └────────────────────┘  │              │
                                  YES              NO
                                   │              │
                         ┌─────────┴─────┐  ┌─────┴──────────────────┐
                         │  GOOD CASE    │  │  PROCEED WITH CAUTION. │
                         │  Write new    │  │  3-6 month ramp-up.    │
                         │  Wasm module. │  │  Consider server-side  │
                         │  Start small. │  │  compute as alternative│
                         └───────────────┘  └────────────────────────┘
```

(See [Decision Framework](../research/03-decision-framework.md), Section 8)

### Quick-Reference Decision Matrix

| Situation | Recommendation | Confidence |
|---|---|---|
| Porting large C++ desktop app to web | Use Wasm (Emscripten) | Very High |
| Image/video processing in browser | Use Wasm or WebGPU | High |
| **Schema-driven CRUD framework (us)** | **Stick with JS** | **Very High** |
| ML inference in browser | Use WebGPU (Wasm fallback) | High |
| Data viz with 100K+ points | WebGPU for rendering, Wasm for data | High |
| Crypto operations (client-side) | Use Wasm | High |
| Form validation / business logic | Stick with JS | Very High |
| Real-time collaborative editing | Evaluate carefully; CRDT in Wasm can help | Medium |
| Compression before upload | Wasm (port zstd/brotli) | High |

### Alternatives to Evaluate Before Wasm

Before committing to Wasm, evaluate these alternatives in order of **increasing complexity**:

| # | Technology | What It Solves | Complexity | Best For |
|---|---|---|---|---|
| 1 | **Optimized JS (TypedArrays)** | Raw numeric performance | Low | The first thing to try |
| 2 | **Web Workers** | Main thread blocking | Low | Any long-running task |
| 3 | **OffscreenCanvas** | Rendering jank | Low-Medium | Canvas-heavy work |
| 4 | **WebGPU** | Massively parallel compute | Medium-High | ML, image processing, simulation |
| 5 | **Server-side compute + streaming** | All client constraints | Medium | Large datasets, security-sensitive |
| 6 | **WebAssembly** | CPU-bound hot paths | **High** | Codecs, crypto, physics, porting native |

Research shows that **JavaScript with TypedArrays and Web Workers** using `SharedArrayBuffer` can be **1.26x faster on average** than Wasm for well-partitioned parallel workloads ([dev.to](https://dev.to/sfundomhlungu/i-tried-to-beat-webassembly-with-nodejs-499o)). Always benchmark against optimized JS, not naive JS.

### Wasm vs. WebGPU: A Critical Distinction

Both technologies enable high-performance computation, but they target fundamentally different hardware and workload shapes. Understanding this distinction is essential for making the right investment.

| Dimension | WebAssembly | WebGPU |
|---|---|---|
| **Hardware target** | CPU (sequential + SIMD) | GPU (massively parallel) |
| **Parallelism model** | Threads via Workers + SharedArrayBuffer | SIMD/SIMT on hundreds of GPU cores |
| **Best speedup over JS** | 2-10x typical | 10-100x (for parallel workloads) |
| **Memory model** | Linear memory (4GB, 16GB with Memory64) | GPU buffers, no strict limit |
| **Programming model** | Rust/C++/Go compiled to Wasm | WGSL shaders + JS orchestration |
| **Debugging** | Improving (Chrome DWARF) | Very immature |
| **Browser support** | Universal (since 2017) | All major browsers (since Nov 2025) |
| **Maturity** | Production-proven (8+ years) | Newly standardized |

**Decision by workload type:**

| Workload | Winner | Why |
|---|---|---|
| Matrix multiplication (large) | **WebGPU** | Massively parallel; maps directly to GPU cores |
| Image convolution/filters | **WebGPU** | Per-pixel operations are embarrassingly parallel |
| ML inference (large models) | **WebGPU** | 2-3x faster than Wasm for LLM/embedding models |
| Sequential algorithms (sort, graph) | **Wasm** | Inherently serial; GPU adds transfer overhead |
| Compression/decompression | **Wasm** | Sequential byte processing |
| Cryptographic hashing | **Wasm** | Sequential computation with branching |
| Physics (particles) | **WebGPU** | Embarrassingly parallel particle updates |
| Physics (rigid body) | **Wasm** | Complex dependencies between objects |
| Audio processing | **Wasm** | AudioWorklet integration; low-latency serial processing |

Figma, one of Wasm's biggest success stories, is **also adopting WebGPU** for rendering. Their C++ renderer now uses Emscripten's WebGPU bindings, combining Wasm for logic with GPU for rendering. The future is **hybrid**, not either/or. According to [Figma's blog](https://www.figma.com/blog/figma-rendering-powered-by-webgpu/), the combination delivers the best of both worlds: Wasm for application logic and data processing, WebGPU for the rendering pipeline.

**For PyBend:** Neither technology addresses our bottleneck (network I/O). If PyBend ever needs client-side compute acceleration, the choice between Wasm and WebGPU depends on the specific workload. Batch entity processing -> Wasm. Data visualization rendering -> WebGPU. Both would use Pattern 1 (Thin Kernel) integration.

(See [Decision Framework](../research/03-decision-framework.md), Section 4)

### The 2026-2027 Outlook

Five developments to track over the next 18 months:

1. **WASI 1.0** (expected late 2026 / early 2027) will mark the point where Wasm becomes a universal portable binary format. This is the inflection point for server-side Wasm adoption and could make the shared validation module pattern significantly more practical for PyBend.

2. **ESM Integration** reaching cross-browser stability (expected late 2026) will remove the async initialization friction that makes buildless Wasm integration awkward. This is the most important signal for PyBend specifically.

3. **WebGPU maturation** -- as more teams ship WebGPU in production, best practices will emerge for combining Wasm compute with GPU rendering. The Figma model (Wasm for logic, WebGPU for pixels) is likely to become the standard pattern.

4. **The Component Model** advancing to production readiness will enable polyglot Wasm applications -- Rust + Python + Go in composable modules. American Express's FaaS platform is the leading edge of this pattern.

5. **Wasm adoption acceleration** -- as WASI 1.0 removes the last ecosystem gap, expect Wasm to become "invisible infrastructure" embedded in platforms without developers being aware of it. The technology will succeed not by being adopted explicitly but by being embedded implicitly.

**For PyBend's planning horizon:** None of these developments change our immediate recommendation. They all strengthen the case for *monitoring* rather than *investing*. When ESM Integration reaches cross-browser stability, re-evaluate. When entity scale exceeds 1,000, re-evaluate. Until then, the 84% network bottleneck deserves every available engineering hour.

---

## 7. 💡 Recommendation

> 💡 **Key Finding:** The recommendation is unambiguous: do not invest in Wasm for PyBend today. The technology is excellent; our architecture is the wrong fit. Two measurable triggers would change this calculus, and we should monitor both.

### The Verdict

**Do not invest in WebAssembly for PyBend.** The technology is production-proven and continues to mature, but PyBend's workload profile is fundamentally mismatched:

- PyBend is **I/O-bound**, not CPU-bound (84% network, 3% CPU)
- PyBend's data is **JSON objects**, not numeric arrays (worst case for JS-Wasm boundary)
- PyBend's compute paths complete in **microseconds**, not milliseconds (below Wasm break-even)
- PyBend's architecture is **buildless** (Wasm adds build toolchain complexity)
- PyBend's philosophy is **zero-config** (Rust compilation is the opposite of zero-config)

### What to Do Instead (Immediate, 0-3 Months)

| Action | Expected Impact | Effort |
|---|---|---|
| Add `Cache-Control` headers for schema endpoints | -100ms on repeat visits | 2-4 hours |
| Add `<link rel="preload">` for schema fetch | -50-80ms first load | 4-8 hours |
| Implement WebSocket for real-time entity updates | Eliminate stale data | 1-2 weeks |
| Profile actual CPU times with `performance.now()` instrumentation | Validate <2ms estimates | 2-4 hours |

### What to Monitor (6-24 Months)

**Trigger A: Entity Scale**
- **Signal:** Client-side entity counts regularly exceed 1,000 per page
- **Why it matters:** At 1,000+ entities, batch `normalizePopulated()` + permission evaluation + form generation becomes measurable (50ms+ CPU)
- **Response:** Evaluate Wasm for batch data normalization and filtering
- **Measurement:** Instrument `NTT.READ()` with `performance.now()`; alert if CPU portion exceeds 100ms

**Trigger B: Validation Parity Bugs**
- **Signal:** Three or more bugs in 6 months caused by frontend/backend validation mismatch
- **Why it matters:** The current duplication (Pydantic on backend, JS on frontend) is intentional -- frontend validation is advisory, backend is authoritative. If this intentional duplication starts causing user-visible bugs, shared validation logic becomes worth the complexity.
- **Response:** Prototype a minimal Rust crate encoding field validation rules, compiled to Wasm for both browser and Python (via wasmtime-py)
- **Measurement:** Track bugs tagged "validation-mismatch" in the issue tracker

**Trigger C: Multi-Tenant Plugin System**
- **Signal:** PyBend needs to execute user-defined model methods in a sandboxed environment
- **Why it matters:** Wasm's capability-based security model (zero capabilities by default, explicit grants only) is ideal for sandboxing untrusted code
- **Response:** Evaluate `wasmtime-py` for server-side Wasm sandboxing of plugin methods
- **Measurement:** When multi-tenant requirements emerge in the product roadmap

**Ecosystem Watch: ESM Integration**
- **Signal:** `import module from './validator.wasm'` works cross-browser without flags
- **Why it matters:** Eliminates the async initialization friction that complicates PyBend's synchronous module loading
- **Expected timeline:** Late 2026 to mid-2027
- **Response:** Re-evaluate integration cost/benefit when this lands

### If a Trigger Fires: The Migration Playbook

If any of the triggers above fire, here is the recommended approach -- the Strangler Fig pattern adapted for PyBend:

**Phase 1: Identify and Isolate (2-4 weeks)**

```
  PyBend Frontend
  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────────┐
  │ NTT  │ │Matrix│ │ Form │ │  [Hot Path]  │ <-- Profile: Is this the bottleneck?
  │      │ │      │ │ Gen  │ │  e.g. batch  │
  │      │ │      │ │      │ │  normalize() │
  └──────┘ └──────┘ └──────┘ └──────────────┘
```

- Profile the application with `performance.now()` instrumentation
- Verify the hot path meets all three Wasm criteria: CPU-bound, sustained, bulk data
- Extract the hot path into a **pure function** with TypedArray inputs/outputs
- Define the data contract: minimize boundary crossings

**Phase 2: Build Wasm Module in Parallel (4-8 weeks)**

```
  PyBend Frontend
  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────────┐
  │ NTT  │ │Matrix│ │ Form │ │ JS Hot Path  │
  │      │ │      │ │ Gen  │ │ (original)   │
  └──────┘ └──────┘ └──────┘ └──────┬───────┘
                                     │
                               ┌─────┴─────┐
                               │ Feature   │
                               │ Flag      │
                               └─────┬─────┘
                            ┌────────┴───┐
                            │ Wasm Module│
                            │ (new)      │
                            └────────────┘
```

- Implement the same function in Rust (or consume a pre-built library)
- Feature-flag toggles between JS and Wasm implementations
- A/B test performance with real user data
- Keep the JS implementation as a permanent fallback

**Phase 3: Validate and Commit (2-4 weeks)**

- Compare: execution time, memory consumption, bundle size
- Verify output parity between JS and Wasm implementations
- Monitor error rates and browser compatibility
- If targets met: make Wasm the default, keep JS fallback
- If targets not met: **revert without production impact**

**For PyBend's buildless architecture specifically:**

The Wasm module would live at `src/pybend/static/wasm/` alongside a `wasm-bindgen --target web` glue file. Loading uses top-level await:

```javascript
// static/wasm/loader.js
import init, { batch_normalize } from './normalizer.js';
await init();  // Top-level await; blocks dependents until ready
export { batch_normalize };
```

The `.wasm` binary would be pre-compiled and checked into the repository. Framework users would never need Rust installed -- the binary ships as a static asset, same as the JavaScript files.

### The Lowest-Risk Entry Point: Library Wrapping

If a compute-heavy feature is needed, the lowest-risk approach is consuming a **pre-built Wasm library** rather than writing custom Rust:

| Library | What It Does | Bundle Size (gzipped) | Effort to Integrate |
|---|---|---|---|
| sql.js | SQLite in browser | ~400 KB | 1-2 days |
| libsodium.js | Cryptography | ~180 KB | 1-2 days |
| squoosh-lib | Image compression | ~200-500 KB per codec | 2-3 days |
| DuckDB-Wasm | Analytical SQL queries | ~4 MB | 1 week |

Library wrapping requires **zero Rust/C++ expertise**. You consume a pre-built `.wasm` module via a JavaScript API. If any of these solve a real product need, start here.

### What NOT to Do

These are explicit anti-recommendations. Do not:

- **Do not rewrite `prototype()`, `Formidable`, `Permissions`, or `Matrix` in Wasm.** The gains are zero to negative. These subsystems are already fast; Wasm boundary crossing would make them slower.

- **Do not add Rust to the developer toolchain for building PyBend apps.** PyBend's value proposition is zero-config Python-to-full-stack. Adding a Rust compilation step contradicts the core philosophy.

- **Do not chase Wasm for marketing/resume reasons.** "We use WebAssembly" sounds impressive but adds no value when the workload doesn't justify it. Ship features instead.

- **Do not adopt Blazor's approach** (shipping an entire language runtime via Wasm). This is the documented anti-pattern -- it produces 10-20 MB payloads, 10-second load times on mobile, and rendering freezes.

- **Do not benchmark Wasm against unoptimized JavaScript.** Always compare against TypedArrays + Web Workers + SharedArrayBuffer. Comparing Wasm to naive `Array.push()` in a loop is misleading.

- **Do not start with threading or SIMD.** If Wasm is ever adopted for PyBend, start with a single-threaded, non-SIMD module. Threading requires cross-origin isolation headers that can break third-party integrations. SIMD requires vectorizable numeric data that PyBend does not have. Add these only if profiling shows they would help.

- **Do not ignore the fallback.** Every Wasm module must have a JS fallback implementation. Browser Wasm support is 96.14%, but edge cases exist (WebViews, enterprise browsers with policies, older mobile devices). The JS fallback also serves as documentation of what the Wasm module does.

---

## 8. 🛡️ Risk Register

> 💡 **Key Finding:** The risks of adopting Wasm for PyBend today outweigh the benefits across all dimensions. The risks of *not* adopting it are low and manageable -- the triggers above provide clear re-evaluation points.

### Risk Register: If We Adopt Wasm

| # | Risk | Probability | Impact | Severity | Mitigation |
|---|---|---|---|---|---|
| **R1** | **Key-person dependency** -- Rust/Wasm expertise concentrated in 1-2 engineers | High (75%) | High | **Critical** | Require at least 2 engineers per Wasm module; document architecture thoroughly; pair programming |
| **R2** | **Hiring pipeline dry-up** -- cannot replace departed Wasm engineer within 2 months | Medium (50%) | High | **High** | Invest in internal training; maintain JS fallback for every Wasm module |
| **R3** | **Serialization bottleneck** -- JS-Wasm boundary cost exceeds compute savings | High (80%) | High | **Critical** | Design APIs around TypedArrays and bulk transfers; avoid per-object boundary crossings; benchmark before committing |
| **R4** | **Build toolchain complexity** -- Rust/wasm-pack breaks, blocks deploys | Medium (40%) | Medium | **Medium** | Pin tool versions; Docker for reproducible builds; maintain JS fallback |
| **R5** | **Debugging cost escalation** -- Wasm bugs take 2-5x longer to diagnose | High (70%) | Medium | **High** | Invest in logging infrastructure; use DWARF debug info; accept slower debug cycles |
| **R6** | **Scope creep** -- "let's Wasm everything" syndrome | Medium (50%) | Medium | **Medium** | Strict boundary: Wasm for compute modules only; leadership-approved exceptions only |
| **R7** | **Wasm binary size bloat** -- .wasm file exceeds loading budget | Medium (45%) | Medium | **Medium** | Audit dependencies; use `wasm-opt -Oz`; enable LTO; avoid heavy crates (regex adds ~500KB, serde inflates significantly) |
| **R8** | **Browser edge cases** -- Safari memory behavior differs from Chrome; mobile has tighter limits | Low (25%) | Medium | **Low-Medium** | Test on real devices; automated cross-browser CI; design for graceful degradation |
| **R9** | **Sunk cost fallacy** -- team continues Wasm effort after POC fails to meet targets | Medium (40%) | High | **High** | Set clear performance targets before starting; kill criteria defined upfront (e.g., "if POC doesn't show >2x improvement, we stop") |
| **R10** | **Team morale** -- frustrating tooling and steep learning curve | Medium (50%) | Low-Medium | **Medium** | Acknowledge the learning curve; allocate slack time; celebrate wins |

### Probability-Impact Matrix

```
              │  Low Impact    Medium Impact    High Impact
──────────────┼──────────────────────────────────────────────
High Prob     │               R5, R10          R1, R3
(>60%)        │
──────────────┼──────────────────────────────────────────────
Medium Prob   │               R4, R6, R7       R2, R9
(30-60%)      │
──────────────┼──────────────────────────────────────────────
Low Prob      │               R8
(<30%)        │
```

### Risk Deep-Dive: The Critical Three

**R1: Key-Person Dependency** (Probability: High, Impact: High)

This is the single most dangerous risk. Rust/Wasm expertise is scarce. According to [K&C](https://kruschecompany.com/international-rust-developer-salary-rate-ranges/), replacing a departed Wasm engineer takes **2-4 months** at a premium. During that window, the Wasm module becomes a black box -- nobody on the team can debug, optimize, or extend it. If a critical bug emerges during that window, the team must either revert to the JS fallback (if one exists) or wait for the hire.

**Mitigation:** Never allow a Wasm module to have a single owner. Require pair programming on all Wasm work. Document the module's architecture, data contracts, and debugging procedures. Maintain a JS fallback that can take over.

**R3: Serialization Bottleneck** (Probability: High, Impact: High)

Research shows that for complex data structures, serialization at the JS-Wasm boundary can consume **up to 60% of execution time** ([arxiv](https://arxiv.org/pdf/2511.01888)). PyBend's data is entirely JSON objects -- the worst case. A Wasm module that processes entity data would need to:

1. Receive JSON from JS
2. Deserialize it in Wasm memory (allocate, parse, build internal representation)
3. Process it
4. Serialize the result back to JSON
5. Return to JS

For PyBend's microsecond-scale operations, steps 1-2 and 4-5 would dominate step 3. The "optimization" would make the operation slower.

**Mitigation:** Only apply Wasm where data can be expressed as TypedArrays or where the processing is so intensive that serialization cost is amortized. For PyBend, this means batch operations on 1,000+ entities, not per-entity processing.

**R5: Debugging Cost Escalation** (Probability: High, Impact: Medium)

Wasm debugging has improved dramatically (Chrome 114+ supports DWARF without flags), but it still requires understanding of:
- Linear memory layout (where data lives in the byte array)
- Rust/C++ debugging techniques (different from JS)
- The interaction between JS glue code and Wasm internals
- Module compilation and instantiation lifecycle

When a Wasm bug occurs, the debugging cycle is: identify symptom in JS -> determine if it crosses into Wasm -> set up DWARF debugging -> step through Rust/C++ source -> identify fix -> recompile -> test. Each step takes longer than the JS equivalent.

**Mitigation:** Invest in comprehensive logging at the JS-Wasm boundary. Log all inputs and outputs of every Wasm function call in development mode. This allows most bugs to be diagnosed from the JS side without entering Wasm-level debugging.

### Risk Register: If We Do NOT Adopt Wasm

| # | Risk | Probability | Impact | Severity | Mitigation |
|---|---|---|---|---|---|
| **R-N1** | **Competitive disadvantage** -- competitor ships Wasm-powered feature we cannot match | Very Low (5%) | Low | **Very Low** | PyBend competes on developer experience and schema-driven architecture, not raw client-side compute speed |
| **R-N2** | **Scale ceiling** -- 1,000+ entities become sluggish without Wasm optimization | Low (15%) | Medium | **Low** | Monitor entity counts; server-side pagination already limits client-side load; triggers defined above |
| **R-N3** | **Validation divergence** -- frontend/backend validation mismatch causes bugs | Low (20%) | Medium | **Low-Medium** | Backend is always authoritative; frontend validation is advisory; track validation-mismatch bugs |
| **R-N4** | **Missing ecosystem trend** -- industry shifts to Wasm-first, we fall behind | Very Low (5%) | Low | **Very Low** | Re-evaluate annually; the triggers defined in Section 7 ensure we notice if circumstances change |

The not-adopting risks are uniformly lower in both probability and impact. This is the right posture for PyBend's current architecture and scale.

### Comparative Risk Summary

```
   ADOPTION RISKS                          NON-ADOPTION RISKS

   ███████████ R1: Key-person (Critical)
   ███████████ R3: Serialization (Critical)
   █████████   R5: Debugging (High)         ██  R-N3: Validation bugs (Low-Med)
   ███████     R2: Hiring (High)            █   R-N2: Scale ceiling (Low)
   ███████     R9: Sunk cost (High)
   █████       R4: Build toolchain (Medium)  █   R-N1: Competitive (Very Low)
   █████       R6: Scope creep (Medium)      █   R-N4: Ecosystem miss (Very Low)
   █████       R7: Binary bloat (Medium)
   █████       R10: Morale (Medium)
   ███         R8: Browser edges (Low-Med)

   Adoption: 2 Critical + 3 High + 4 Medium + 1 Low = 10 risks
   Non-adoption: 0 Critical + 0 High + 1 Low-Med + 3 Low = 4 risks
```

The risk asymmetry is stark. Adoption creates 10 risks including 2 at Critical severity. Non-adoption creates 4 risks, none above Low-Medium. The triggers in Section 7 serve as early warning signals for the non-adoption risks, ensuring we re-evaluate before they materialize.

---

## 9. 📎 Appendices

### Appendix A: Complete Subsystem Analysis

The full subsystem-by-subsystem Wasm assessment is documented in [Our Stack Relevance](../research/04-our-stack-relevance.md), Section 2. Key code paths analyzed:

| Subsystem | Key File | Function/Line | Assessment |
|---|---|---|---|
| Schema bootstrap | `/workspace/src/pybend/static/core/NTT.js` | `SCHEMA()`, `prototype()` (line ~663) | Not a candidate |
| Form generation | `/workspace/src/pybend/static/generators/form.js` | `getForm()` (line 17) | Not a candidate |
| Permission evaluation | `/workspace/src/pybend/static/utils/Permissions.js` | `canAction()` | Not a candidate |
| Message routing | `/workspace/src/pybend/static/core/Matrix.js` | `inbox()` (line 26) | Not a candidate |
| Entity normalization | `/workspace/src/pybend/static/core/NTT.js` | `normalizePopulated()` (line ~614) | Monitor |
| Backend schema gen | `/workspace/src/pybend/core/models/proto_model.py` | `schema()` (line ~199) | Not a candidate |
| SQL + hydration | `/workspace/src/pybend/core/storage/sqlite_storage.py` | `list()`, `get()` | Not a candidate |

### Appendix B: Browser Feature Support Matrix

Current as of February 2026. Verify at [caniuse.com](https://caniuse.com/wasm) before deployment decisions.

| Feature | Chrome | Firefox | Safari | Edge | Global % |
|---|---|---|---|---|---|
| Core Wasm 1.0 | 57+ | 52+ | 11+ | 16+ | ~96% |
| Bulk Memory | 79+ | 79+ | 15+ | 79+ | ~95% |
| SIMD (128-bit) | 91+ | 89+ | 16.4+ | 91+ | ~93% |
| Threads/Atomics | 74+ | 79+ | 15.2+ | 79+ | ~90%* |
| Exception Handling | 95+ | 100+ | 15.2+ | 95+ | ~92% |
| GC (WasmGC) | 119+ | 120+ | 18.2+ | 119+ | ~85% |
| Memory64 | 135+ | 134+ | 18.4+ | 135+ | ~70% |
| Relaxed SIMD | 114+ | 2025 | Behind flag | 114+ | ~80% |

\* Threads require cross-origin isolation headers (COOP/COEP), which can break third-party embeds.

### Appendix C: Toolchain Comparison Data

Sort benchmark: 100K random values, copied 500x, stable-sorted each time, 5 repetitions. Intel MacBook Pro 2019.

| Toolchain | Binary Size | Chrome (ms) | Firefox (ms) | Edge (ms) |
|---|---|---|---|---|
| Rust (wasm-pack) | 74 KB total | **2,982** | 3,582 | 3,306 |
| AssemblyScript | 4.7 KB total | 6,405 | 6,152 | 6,882 |
| TinyGo | 37 KB total | 9,717 | 10,668 | 9,546 |
| JS (typed arrays) | N/A | 4,904 | -- | -- |
| JS (dynamic) | N/A | 68,720 | -- | -- |

Key observation: Rust Wasm is ~1.6x faster than optimized JS with TypedArrays, but ~23x faster than naive dynamic JS. **Always benchmark against optimized JS, not naive JS.**

(Source: [Ecostack](https://ecostack.dev/posts/wasm-tinygo-vs-rust-vs-assemblyscript/))

### Appendix D: Binary Size Optimization Pipeline

Typical Wasm binary size through optimization stages:

| Stage | Size | Notes |
|---|---|---|
| Debug build | 2-5 MB | Includes DWARF, names section |
| Release build | 500 KB | Compiler optimizations |
| After `wasm-opt -Oz` | 350 KB | Binaryen passes |
| After `wasm-strip` | 300 KB | Debug info removed |
| Brotli compressed (transfer) | **60-90 KB** | What the user downloads |

The combination of `wasm-opt -Oz` + Brotli typically reduces a release binary to **15-20% of its unoptimized size** on the wire.

### Appendix E: Benchmarking Methodology Guide

If Wasm evaluation is triggered in the future, use this checklist to avoid common benchmarking mistakes:

**Common Mistakes to Avoid:**

| Mistake | Why It's Misleading | Correct Approach |
|---|---|---|
| Excluding Wasm compilation time | Real users pay this cost on first load | Include `WebAssembly.compile()` + `instantiate()` in cold-start measurement |
| Excluding serialization overhead | Data must cross the JS-Wasm boundary | Include full round-trip: JS -> serialize -> Wasm compute -> deserialize -> JS |
| Measuring after JIT warmup only | JS gets faster over iterations; Wasm is stable | Measure both cold and warmed; report both |
| Micro-benchmarks only | Tight loops favor Wasm; real apps have overhead | Benchmark the actual feature, not an isolated function |
| Not testing across browsers | Performance varies 2-3x between engines | Test Chrome, Firefox, Safari minimum |
| Ignoring memory consumption | Wasm uses significantly more memory for large inputs | Profile memory alongside execution time |
| Small input sizes only | Wasm advantage shrinks with larger inputs | Test with production-realistic data sizes |
| Comparing against unoptimized JS | Apples to oranges | Always compare against TypedArrays + Workers + SharedArrayBuffer |

**Benchmark Template:**

```javascript
// Template for PyBend Wasm benchmarking
async function benchmarkOperation(name, jsImpl, wasmImpl, testData, iterations = 100) {
    // Cold start (includes module instantiation)
    const coldStart = performance.now();
    const wasmResult = await wasmImpl(testData);
    const coldEnd = performance.now();

    // Warm start (module already loaded)
    const warmTimes = [];
    for (let i = 0; i < iterations; i++) {
        const t0 = performance.now();
        wasmImpl(testData);
        warmTimes.push(performance.now() - t0);
    }

    // JS comparison (always warm -- V8 optimizes after a few iterations)
    for (let i = 0; i < 10; i++) jsImpl(testData);  // Warmup
    const jsTimes = [];
    for (let i = 0; i < iterations; i++) {
        const t0 = performance.now();
        jsImpl(testData);
        jsTimes.push(performance.now() - t0);
    }

    console.table({
        operation: name,
        wasmColdMs: (coldEnd - coldStart).toFixed(2),
        wasmWarmP50Ms: median(warmTimes).toFixed(2),
        wasmWarmP99Ms: percentile(warmTimes, 99).toFixed(2),
        jsP50Ms: median(jsTimes).toFixed(2),
        jsP99Ms: percentile(jsTimes, 99).toFixed(2),
        speedup: (median(jsTimes) / median(warmTimes)).toFixed(2) + 'x',
    });
}
```

**What "good" looks like:**

| Benchmark Design | Measures | Example |
|---|---|---|
| End-to-end feature | Real user impact | "Batch normalize 1K entities: 12ms (Wasm) vs 45ms (JS)" |
| Cold start | First-load penalty | "Module compile: 8ms; first call: 15ms; subsequent: 3ms" |
| Memory profile | Resource consumption | "Peak heap: 24MB (Wasm) vs 8MB (JS) for same workload" |
| Browser matrix | Cross-browser variance | "Chrome: 2.1x faster; Firefox: 1.8x; Safari: 2.4x" |
| Scaling curve | Input-size sensitivity | "Speedup: 8x at 100 entities, 3x at 1K, 1.5x at 10K" |

(See [Decision Framework](../research/03-decision-framework.md), Section 10)

### Appendix F: Emerging Proposals to Watch

Several post-Wasm 3.0 proposals could change the strategic calculus. These are the ones worth tracking:

| Proposal | Phase | What It Does | Impact on PyBend | Expected Timeline |
|---|---|---|---|---|
| **Stack Switching** | Phase 3 | Lightweight coroutines, green threads without OS threads | Medium -- could enable async Wasm without Workers | 2027+ |
| **Shared-Everything Threads** | Phase 2 | Full shared-memory threading without Web Workers | Low -- PyBend has no parallel compute | 2028+ |
| **JS String Builtins** | Phase 4 | Direct access to JS string operations from Wasm | Medium -- reduces string interop overhead | Late 2026 |
| **Flexible Vectors** | Phase 1 | SIMD wider than 128-bit (256, 512) | Low -- no vectorizable data | Years away |
| **ESM Integration** | Phase 3 | `import from './module.wasm'` syntax | **High** -- eliminates async init friction | Late 2026 - Mid 2027 |
| **Memory Control** | Phase 1 | `memory.discard` to release physical pages | Low | Years away |
| **Branch Hinting** | Phase 4 | Hint to compiler which branches are likely | Very Low -- micro-optimization | Late 2026 |

**Stack Switching** is the most impactful upcoming proposal. It would allow Wasm to suspend and resume execution without OS-level threads, enabling lightweight "green threads" (like Go goroutines) and efficient async/await compilation. For a framework like PyBend that could eventually run compute in Wasm, stack switching would eliminate the need for Web Workers to keep the main thread responsive.

**ESM Integration** is the most impactful proposal for *our buildless architecture*. Currently, loading Wasm requires an explicit `fetch()` + `WebAssembly.instantiateStreaming()` dance. ESM Integration would allow `import { validate } from './validator.wasm'` -- the same syntax as any other ES module. This would eliminate the async initialization friction and make Wasm modules first-class citizens in PyBend's module graph.

(See [Technical Deep Dive](../research/02-technical-deep-dive.md), Section 12)

### Appendix G: WASI Roadmap

| Milestone | Date | Status |
|---|---|---|
| WASI 0.2 (Preview 2) | Early 2024 | Shipped |
| WASI 0.3.0 (async support) | February 2026 | **Just shipped** |
| WASI 1.0 | Late 2026 / Early 2027 | Expected |
| Component Model | Alongside WASI 0.3/1.0 | Active development |

WASI 1.0 is the inflection point for server-side and edge Wasm. When it ships, a single Wasm module could run identically in the browser, on the server, and at the edge. For PyBend, this could eventually enable shared validation logic compiled once and deployed everywhere.

(See [Technical Deep Dive](../research/02-technical-deep-dive.md), Section 8)

### Appendix H: Source Language Distribution in Production

What languages produce the Wasm binaries observed in the wild (HTTP Archive 2025):

```
Language / Toolchain        Desktop    Mobile
──────────────────────────────────────────────
.NET / Mono / Blazor        41.7%      38.7%     ██████████████████████
Emscripten (C/C++)          10.1%       7.8%     █████
Scala                        3.6%       3.4%     ██
AssemblyScript               2.4%       2.3%     █
Rust                         1.5%       2.2%     █
Go / TinyGo                 ~0.1%     ~0.1%     ▏
Unknown / Unidentified      40.5%      45.5%     ████████████████████
──────────────────────────────────────────────
```

The dominance of .NET/Blazor (41.7%) reflects Microsoft's push of Blazor WebAssembly, not high-performance Wasm usage. The Emscripten (C/C++) and Rust categories better represent the compute-heavy use cases.

### Appendix I: Organizational Readiness Checklist

If leadership decides to proceed despite this report's recommendation, use this checklist before committing resources. Each item scored 0 (not met) or 1 (met).

**Technical Readiness:**

| # | Criterion | Score |
|---|---|---|
| 1 | We have profiled our application and identified a specific CPU-bound bottleneck | |
| 2 | We have benchmarked optimized JS (TypedArrays, Workers) and it's not sufficient | |
| 3 | The bottleneck involves sustained computation (not one-off, not I/O) | |
| 4 | The data interface can be expressed as TypedArrays or simple numeric types | |
| 5 | We have tested that boundary-crossing overhead does not dominate | |
| 6 | Our target browsers support required Wasm features | |
| 7 | The .wasm bundle size is acceptable (<500KB gzipped for most apps) | |
| 8 | We have a fallback strategy if Wasm fails | |

**Team Readiness:**

| # | Criterion | Score |
|---|---|---|
| 9 | At least 2 engineers have or can acquire Rust/C++ Wasm experience | |
| 10 | The team has allocated ramp-up time (8-16 weeks for JS-only teams) | |
| 11 | Documentation and knowledge-sharing practices prevent key-person risk | |
| 12 | Leadership understands the TCO trade-offs | |

**Organizational Readiness:**

| # | Criterion | Score |
|---|---|---|
| 13 | Success metrics defined (e.g., "operation under 50ms at P95") | |
| 14 | Kill criteria defined (e.g., "if POC doesn't show >2x, we stop") | |
| 15 | Wasm module scope is bounded (not "rewrite everything in Rust") | |
| 16 | CI/CD pipeline can accommodate multi-language builds | |
| 17 | Monitoring plan for Wasm-specific metrics | |
| 18 | Timeline allows for proper before/after benchmarking | |

**Scoring: 16-18** = Strong go. **12-15** = Conditional; address gaps. **8-11** = Not ready. **0-7** = Stop.

For PyBend today, we would score approximately **3-5** on this checklist (items 6, 16, and possibly 8). This is well below the "Not ready" threshold.

(See [Decision Framework](../research/03-decision-framework.md), Section 12)

### Appendix J: Performance Domain Reference

Domain-specific Wasm speedups from production case studies and academic research:

| Domain | Typical Speedup | Peak Speedup | Source |
|---|---|---|---|
| Image processing (SIMD) | 3-4x | 80-160x (Halide) | Adobe Photoshop |
| Spreadsheet calculation | 2x | -- | Google Sheets (WasmGC) |
| Barcode scanning | ~10x (FPS) | -- | eBay |
| Cryptography (ECDH) | 12.3x | -- | IEEE research |
| Cryptography (HMAC) | 7.1x | -- | IEEE research |
| Video encoding (SIMD) | 2.3x | -- | Clipchamp |
| Force-layout simulation | 5-8x | -- | D3.js Wasm port |
| Design tool load time | 3x | -- | Figma |
| ML inference (SIMD) | Up to 35% | -- | Chrome for Developers |
| Array operations (Rust) | 6x | -- | byteiota 2025 |
| Matrix multiplication (SIMD) | 9.5x | -- | byteiota 2025 |
| Scientific computing (Node 22 SIMD) | 10x | -- | markaicode 2025 |

### Appendix K: Research Document Index

This report synthesizes findings from four research documents. Refer to them for full technical depth:

| Document | Lines | Focus | Path |
|---|---|---|---|
| Industry Landscape | 739 | Case studies, adoption stats, market data | [01-industry-landscape.md](../research/01-industry-landscape.md) |
| Technical Deep Dive | 1,097 | Compilation pipeline, interop, toolchains, security | [02-technical-deep-dive.md](../research/02-technical-deep-dive.md) |
| Decision Framework | 766 | When Wasm makes sense, TCO, alternatives, decision tree | [03-decision-framework.md](../research/03-decision-framework.md) |
| Our Stack Relevance | 721 | PyBend source analysis, compute profile, integration assessment | [04-our-stack-relevance.md](../research/04-our-stack-relevance.md) |

---

## 📎 Full Source Bibliography

### Case Studies and Company Blogs
- [Figma: WebAssembly cut load time by 3x](https://www.figma.com/blog/webassembly-cut-figmas-load-time-by-3x/)
- [Figma: Rendering powered by WebGPU](https://www.figma.com/blog/figma-rendering-powered-by-webgpu/)
- [Google Sheets: WasmGC case study](https://web.dev/case-studies/google-sheets-wasmgc)
- [Adobe Photoshop on the web](https://medium.com/@addyosmani/photoshop-is-now-on-the-web-38d70954365a)
- [eBay: WebAssembly real-world use case](https://innovation.ebayinc.com/stories/webassembly-at-ebay-a-real-world-use-case/)
- [American Express: FaaS with Wasm](https://thenewstack.io/amexs-faas-uses-webassembly-instead-of-containers/)
- [Cloudflare Workers: Wasm at edge](https://blog.cloudflare.com/webassembly-on-cloudflare-workers/)
- [Clipchamp: PWA + Wasm](https://web.dev/case-studies/clipchamp)
- [Google Earth: Wasm migration](https://web.dev/earth-webassembly/)
- [AutoCAD: 30-year codebase to web](https://www.infoq.com/presentations/autocad-webassembly/)

### Standards and Specifications
- [Wasm 3.0 Completed (W3C)](https://webassembly.org/news/2025-09-17-wasm-3.0/)
- [WASI Roadmap](https://wasi.dev/roadmap)
- [Component Model (Bytecode Alliance)](https://component-model.bytecodealliance.org/)
- [WebAssembly Feature Status](https://webassembly.org/features/)

### Data and Statistics
- [HTTP Archive Web Almanac 2025: WebAssembly](https://almanac.httparchive.org/en/2025/webassembly)
- [Can I Use: WebAssembly](https://caniuse.com/wasm)
- [CNCF State of WebAssembly](https://www.cncf.io/wp-content/uploads/2023/09/The-State-of-WebAssembly-2023.pdf)
- [Chrome Platform Status: Wasm adoption](https://chromestatus.com)

### Market and Investment
- [WebAssembly Cloud Platform Market Report](https://www.researchandmarkets.com/reports/6215521/webassembly-cloud-platform-global-market-report)
- [Wasm Runtime Market Report](https://growthmarketreports.com/report/webassembly-runtime-market)
- [Akamai acquires Fermyon](https://siliconangle.com/2025/12/01/akamai-acquires-webassembly-function-service-startup-fermyon/)
- [Sapphire Ventures: Compute's next paradigm shift](https://sapphireventures.com/blog/whats-up-with-webassembly-computes-next-paradigm-shift/)

### Performance Research
- [IEEE: Systematic Review of Wasm vs JS Performance](https://ieeexplore.ieee.org/document/10277917/)
- [BenchmarkingWebAssembly](https://benchmarkingwasm.github.io/BenchmarkingWebAssembly/)
- [Rust Wasm Performance: 8-10x faster](https://byteiota.com/rust-webassembly-performance-8-10x-faster-2025-benchmarks/)
- [Ecostack: Wasm TinyGo vs Rust vs AssemblyScript](https://ecostack.dev/posts/wasm-tinygo-vs-rust-vs-assemblyscript/)
- [Mozilla Hacks: JS-Wasm calls are fast](https://hacks.mozilla.org/2018/10/calls-between-javascript-and-webassembly-are-finally-fast-%F0%9F%8E%89/)
- [Serialization overhead research (arxiv)](https://arxiv.org/pdf/2511.01888)

### Technical References
- [V8 Wasm Compilation Pipeline](https://v8.dev/docs/wasm-compilation-pipeline)
- [V8 Liftoff Baseline Compiler](https://v8.dev/blog/liftoff)
- [Emscripten Pthreads](https://emscripten.org/docs/porting/pthreads.html)
- [wasm-bindgen Browser Support](https://rustwasm.github.io/docs/wasm-bindgen/reference/browser-support.html)
- [Shrinking .wasm Size (Rust Wasm Book)](https://rustwasm.github.io/book/game-of-life/code-size.html)
- [Chrome DevTools: Debug Wasm](https://developer.chrome.com/docs/devtools/wasm)

### Failure Stories
- [Blazor Wasm size issue (GitHub, 500+ upvotes)](https://github.com/dotnet/aspnetcore/issues/41909)
- [Wasm for microservices: lessons learned](https://thenewstack.io/case-study-a-webassembly-failure-and-lessons-learned/)
- [C program compilation: 42% survival rate](https://arxiv.org/html/2311.00646v2)
- [CNCF: Wasm adoption is complicated](https://thenewstack.io/webassembly-adoption-its-complicated-says-cncf-survey/)

### Developer Costs
- [Glassdoor: Rust developer salary](https://www.glassdoor.com/Salaries/rust-developer-salary-SRCH_KO0,14.htm)
- [ZipRecruiter: Rust developer salary](https://www.ziprecruiter.com/Salaries/Rust-Developer-Salary)
- [K&C: International Rust developer salary ranges](https://kruschecompany.com/international-rust-developer-salary-rate-ranges/)

---

*This report was compiled in February 2026 based on four research documents totaling 3,323 lines of analysis. WebAssembly is evolving rapidly -- WASI 1.0 and ESM Integration milestones in 2026-2027 may shift the landscape. The triggers defined in Section 7 ensure we re-evaluate when circumstances change rather than on an arbitrary schedule.*

*For questions about this analysis, refer to the research documents indexed in Appendix I or contact the Engineering Strategy team.*
