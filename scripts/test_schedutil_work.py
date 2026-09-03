#!/usr/bin/env python3
"""Host regression test of the actual schedutil deferred-work functions.

This models the queue/driver boundary; it is not a kernel or device test.
Use --ref COMMIT to check the same assertions against an older revision.
"""

import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "kernel/sched/cpufreq_schedutil.c"


def function(source, name):
    match = re.search(r"^static [^\n]*\b" + name + r"\(", source, re.M)
    if not match:
        raise ValueError(f"missing function: {name}")
    end = source.index("\n}", match.start()) + 2
    return source[match.start():end]


PREAMBLE = r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint64_t u64;
typedef int64_t s64;
struct cpufreq_policy { bool fast_switch_enabled; unsigned int cur; };
struct irq_work { int unused; };
struct kthread_work { int unused; };
struct kthread_worker { int unused; };
struct sugov_policy {
    struct cpufreq_policy *policy;
    int update_lock, work_lock;
    u64 last_freq_update_time;
    s64 up_rate_delay_ns, down_rate_delay_ns;
    unsigned int next_freq, cached_raw_freq;
    struct irq_work irq_work;
    struct kthread_work work;
    struct kthread_worker worker;
    bool work_in_progress;
};
#define container_of(ptr, type, member) \
    ((type *)((char *)(ptr) - offsetof(type, member)))
#define CPUFREQ_ENTRY_INVALID (~0U)
#define CPUFREQ_RELATION_L 0
#define cpufreq_driver_fast_switch(policy, freq) (freq)
#define smp_processor_id() 0
#define trace_cpu_frequency(freq, cpu) ((void)0)
#define raw_spin_lock_irqsave(lock, flags) do { \
    (flags) = 0; assert(!*(lock)); *(lock) = 1; \
} while (0)
#define raw_spin_unlock_irqrestore(lock, flags) do { \
    (void)(flags); assert(*(lock)); *(lock) = 0; \
} while (0)

static unsigned int irq_calls, work_calls, driver_calls, last_applied;
static bool irq_pending, work_pending;
static unsigned int inject_freq;
static u64 inject_time;
static int inject_stage;
static struct sugov_policy state;
static struct cpufreq_policy policy;
static void inject_update(void);

static void irq_work_queue(struct irq_work *work)
{
    assert(state.update_lock);
    irq_calls++;
    irq_pending = true;
}
static void queue_kthread_work(struct kthread_worker *worker,
                              struct kthread_work *work)
{
    work_calls++;
    work_pending = true;
}
static void mutex_lock(int *lock)
{
    assert(!state.update_lock);
    assert(!*lock);
    *lock = 1;
    if (inject_stage == 1)
        inject_update();
}
static void mutex_unlock(int *lock)
{
    assert(*lock);
    *lock = 0;
    if (inject_stage == 3)
        inject_update();
}
static void __cpufreq_driver_target(struct cpufreq_policy *p,
                                   unsigned int freq, int relation)
{
    assert(state.work_lock);
    assert(!state.update_lock);
    driver_calls++;
    last_applied = freq;
    p->cur = freq;
    if (inject_stage == 2)
        inject_update();
}
"""

TESTS = r"""
static void request(u64 time, unsigned int freq)
{
    assert(!state.update_lock);
    state.update_lock = 1;
    sugov_update_commit(&state, time, freq);
    state.update_lock = 0;
}
static void inject_update(void)
{
    inject_stage = 0;
    request(inject_time, inject_freq);
}
static void reset(void)
{
    memset(&state, 0, sizeof(state));
    memset(&policy, 0, sizeof(policy));
    state.policy = &policy;
    state.up_rate_delay_ns = 2500000;
    state.down_rate_delay_ns = 8000000;
    irq_calls = work_calls = driver_calls = last_applied = 0;
    irq_pending = work_pending = false;
    inject_stage = 0;
}
static void dispatch_irq(void)
{
    assert(irq_pending);
    irq_pending = false;
    sugov_irq_work(&state.irq_work);
}
static void run_work(void)
{
    assert(work_pending);
    work_pending = false;
    sugov_work(&state.work);
}
static void drain(void)
{
    unsigned int budget = 10;
    while (irq_pending || work_pending) {
        assert(budget--);
        if (irq_pending)
            dispatch_irq();
        if (work_pending)
            run_work();
    }
    assert(!state.work_in_progress);
}
int main(void)
{
    /* Later requests replace the pending target without another IRQ. */
    reset();
    request(10000000, 800000);
    request(14000000, 1200000);
    request(18000000, 1600000);
    assert(irq_calls == 1);
    drain();
    assert(driver_calls == 1 && last_applied == 1600000);

    /* Same coalescing after the IRQ has queued the worker. */
    reset();
    request(10000000, 800000);
    dispatch_irq();
    request(14000000, 1200000);
    assert(irq_calls == 1);
    drain();
    assert(driver_calls == 1 && last_applied == 1200000);

    /* An update before, during, or just after the driver must survive. */
    for (int stage = 1; stage <= 3; stage++) {
        reset();
        request(10000000, 800000);
        inject_stage = stage;
        inject_time = 14000000;
        inject_freq = 1600000;
        drain();
        assert(driver_calls == 2 && last_applied == 1600000);
    }

    /* Neither up/down delays nor the unchanged-frequency fast exit change. */
    reset();
    request(10000000, 800000);
    drain();
    request(11000000, 1200000);
    assert(irq_calls == 1 && state.cached_raw_freq == 0);
    request(12500000, 1200000);
    drain();
    request(13000000, 800000);
    assert(irq_calls == 2);
    request(20500000, 800000);
    drain();
    assert(driver_calls == 3 && last_applied == 800000);
    request(40000000, 800000);
    assert(irq_calls == 3);

    /* A lower request is also retained while a higher target is applied. */
    reset();
    request(10000000, 1600000);
    inject_stage = 2;
    inject_time = 18000000;
    inject_freq = 800000;
    drain();
    assert(driver_calls == 2 && last_applied == 800000);

    /* Fast-switch path (stubbed in this kernel) must not queue slow work. */
    reset();
    policy.fast_switch_enabled = true;
    request(10000000, 1200000);
    assert(policy.cur == 1200000 && !irq_calls && !driver_calls);

    puts("PASS: coalescing, latest target, driver interleavings, rate limits, fast path");
    return 0;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", help="read source from this git revision")
    args = parser.parse_args()
    if args.ref:
        source = subprocess.check_output(
            ["git", "show", f"{args.ref}:{SOURCE}"], cwd=ROOT, text=True
        )
    else:
        source = (ROOT / SOURCE).read_text()
    names = ("sugov_up_down_rate_limit", "sugov_update_commit",
             "sugov_work", "sugov_irq_work")
    code = PREAMBLE + "\n".join(function(source, n) for n in names) + TESTS
    with tempfile.TemporaryDirectory(prefix="sugov-test-") as tmp:
        test = Path(tmp) / "test.c"
        binary = Path(tmp) / "test"
        test.write_text(code)
        subprocess.run(shlex.split(os.environ.get("HOSTCC", "cc")) + [
            "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter", "-fsanitize=undefined",
            str(test), "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, cwd=tmp)


if __name__ == "__main__":
    main()
