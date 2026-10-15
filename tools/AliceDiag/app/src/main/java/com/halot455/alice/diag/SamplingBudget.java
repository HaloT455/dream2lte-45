package com.halot455.alice.diag;

/** Monotonic backoff: a slow collection can never increase its own polling rate. */
final class SamplingBudget {
    private long delay;
    SamplingBudget(long baseDelay) { delay = baseDelay; }
    long observe(long costMs) {
        if (costMs >= 2000) delay = Math.max(delay, 60_000);
        else if (costMs >= 750) delay = Math.max(delay, 30_000);
        return delay;
    }
    long delay() { return delay; }
}
