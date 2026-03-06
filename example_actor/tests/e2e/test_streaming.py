"""E2E streaming test — verifies SSE chunks arrive progressively, not buffered.

Uses Playwright's page.evaluate() to run a raw fetch + ReadableStream against
the countdown SSE endpoint, recording timestamps for each chunk. Asserts that
chunks arrive with real delays (not all at once).
"""
import pytest
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"  # Patched by conftest


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    p = ctx.new_page()
    yield p
    p.close()
    ctx.close()


def test_sse_chunks_arrive_progressively(page, e2e_server):
    """Chunks from /products/1/countdown must arrive with real delays."""
    base = e2e_server

    # Navigate to the app so we have a page context
    page.goto(f"{base}/")
    page.wait_for_load_state("networkidle")

    # Run a fetch-based SSE reader in the browser and record chunk timestamps
    result = page.evaluate("""async (base) => {
        const url = `${base}/products/1/countdown`;
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ n: 5 }),
        });
        if (!resp.ok) return { error: `HTTP ${resp.status}` };

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        const timestamps = [];
        const chunks = [];
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\\n');
            buffer = lines.pop();
            let eventType = 'chunk';
            for (const line of lines) {
                if (line.startsWith('event: ')) eventType = line.slice(7).trim();
                else if (line.startsWith('data: ')) {
                    try {
                        const parsed = JSON.parse(line.slice(6));
                        timestamps.push(performance.now());
                        chunks.push({ type: eventType, data: parsed });
                    } catch (e) {}
                }
            }
        }
        return { timestamps, chunks };
    }""", base)

    assert "error" not in result, f"Fetch failed: {result.get('error')}"

    timestamps = result["timestamps"]
    chunks = result["chunks"]

    # We expect 5 countdown chunks + 1 done event = 6 events
    assert len(chunks) >= 5, f"Expected >= 5 chunks, got {len(chunks)}: {chunks}"

    # Verify progressive delivery: total time span should be > 1 second
    # (5 chunks at 0.3s delay each = ~1.5s total)
    total_time_ms = timestamps[-1] - timestamps[0]
    print(f"\n  Chunks: {len(chunks)}")
    print(f"  Total time span: {total_time_ms:.0f}ms")
    for i, (ts, chunk) in enumerate(zip(timestamps, chunks)):
        delta = ts - timestamps[0] if i > 0 else 0
        print(f"  [{i}] +{delta:.0f}ms  {chunk['type']}: {chunk['data']}")

    # The critical assertion: if all chunks arrive at once, total_time < 100ms.
    # With real streaming, it should be > 1000ms (5 x 0.3s delays).
    assert total_time_ms > 800, (
        f"Chunks arrived too fast ({total_time_ms:.0f}ms) — likely buffered. "
        f"Expected > 800ms for 5 chunks with 0.3s delays."
    )
