#!/usr/bin/env python3
"""Execute the actual EGO-port request/worker C functions with driver interleavings."""
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    start = re.search(r"^static [^\n]*\b" + name + r"\(", source, re.M)
    if not start:
        raise ValueError(name)
    return source[start.start():source.index("\n}", start.start()) + 2]


PREAMBLE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include "energy_aware_model.h"
typedef uint64_t u64;
typedef int64_t s64;
#define NR_CPUS 2
#define CPUFREQ_RELATION_L 0
#define SCHED_CPUFREQ_DL 1
#define EAGOV_SCAN_NS 2000000ULL
#define EAGOV_MARGIN 12U
#define READ_ONCE(x) (x)
static bool eagov_allow_oc;
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
#define max(a, b) ((a) > (b) ? (a) : (b))
#define min(a, b) ((a) < (b) ? (a) : (b))
#define clamp_val(v, low, high) min(max(v, low), high)
#define WARN_ON_ONCE(x) (x)
#define per_cpu(name, cpu) (name[cpu])
#define for_each_cpu(cpu, mask) for (cpu = 0; cpu < NR_CPUS; cpu++) if (*(mask) & (1U << cpu))
static unsigned int cpumask_weight(const unsigned int *mask) { return __builtin_popcount(*mask); }
struct cpufreq_policy { unsigned int min, max, cur; unsigned int *cpus; };
struct irq_work { int dummy; };
struct kthread_work { int dummy; };
struct kthread_worker { int dummy; };
struct eagov_policy {
    struct cpufreq_policy *policy;
    unsigned int qos_min_class, qos_max_class;
    struct eagov_energy_model model;
    int lock, work_lock;
    struct irq_work irq_work;
    struct kthread_work work;
    struct kthread_worker worker;
    unsigned int target_state, applied_state, org_freq, eng_freq;
    unsigned int nr_native_states, last_peak, last_low, last_high;
    u64 last_scan;
    unsigned long long target_energy;
    s64 power_delta;
    bool enabled, queued;
};
struct eagov_cpu { u64 time; unsigned int util; bool valid; };
static struct eagov_cpu eagov_cpus[NR_CPUS];
static struct eagov_policy state;
static struct cpufreq_policy policy;
static unsigned int mask;
static int qos_min, qos_max;
static int pm_qos_request(unsigned int cls) { return cls == 1 ? qos_min : qos_max; }
static struct eagov_energy_state states[] = {
    {100, 100, 100, 10}, {200, 200, 250, 10}, {300, 300, 900, 10}
};
static bool irq_pending, work_pending, fail_driver, clamp_driver, stop_in_driver;
static unsigned int irq_calls, driver_calls, last_applied, inject_count;
static u64 now;
static void request(unsigned int util);
#define raw_spin_lock_irqsave(lock, flags) do { (flags) = 0; assert(!*(lock)); *(lock) = 1; } while (0)
#define raw_spin_unlock_irqrestore(lock, flags) do { (void)(flags); assert(*(lock)); *(lock) = 0; } while (0)
static u64 eagov_sample_window(void) { return 20000000; }
static unsigned int ego_compute_cpu_idle_ratio(unsigned int cpu) { return 1024; }
static void irq_work_queue(struct irq_work *irq) {
    assert(state.lock); irq_calls++; irq_pending = true;
}
static void queue_kthread_work(struct kthread_worker *worker, struct kthread_work *work) {
    work_pending = true;
}
static void mutex_lock(int *lock) { assert(!state.lock && !*lock); *lock = 1; }
static void mutex_unlock(int *lock) { assert(*lock); *lock = 0; }
static int __cpufreq_driver_target(struct cpufreq_policy *p, unsigned int freq, int rel) {
    assert(state.work_lock && !state.lock);
    driver_calls++;
    if (stop_in_driver) state.enabled = false;
    if (inject_count) { inject_count--; request(freq == 100 ? 120 : 40); }
    if (fail_driver) { fail_driver = false; return -5; }
    p->cur = clamp_driver ? 150 : freq;
    last_applied = p->cur;
    return 0;
}
'''

TESTS = r'''
static void reset(void) {
    memset(&state, 0, sizeof(state)); memset(eagov_cpus, 0, sizeof(eagov_cpus));
    mask = 1; policy = (struct cpufreq_policy){100, 300, 100, &mask};
    state.policy = &policy;
    state.qos_min_class = 1; state.qos_max_class = 2;
    qos_min = 0; qos_max = 300;
    state.model = (struct eagov_energy_model){states, 3, 0, 0, 0};
    state.nr_native_states = 2;
    eagov_allow_oc = true;
    state.target_state = state.applied_state = EAGOV_NO_STATE;
    state.enabled = true;
    irq_pending = work_pending = fail_driver = clamp_driver = stop_in_driver = false;
    irq_calls = driver_calls = last_applied = inject_count = 0;
    now = 1;
}
static void request(unsigned int util) {
    unsigned long flags;
    raw_spin_lock_irqsave(&state.lock, flags);
    eagov_cpus[0] = (struct eagov_cpu){now++, util, true};
    eagov_request(&state, eagov_cpus[0].time);
    raw_spin_unlock_irqrestore(&state.lock, flags);
}
static void run_once(void) {
    if (irq_pending) { irq_pending = false; eagov_irq_work(&state.irq_work); }
    if (work_pending) { work_pending = false; eagov_work(&state.work); }
}
static void drain(void) {
    unsigned int budget = 10;
    while (irq_pending || work_pending) { assert(budget--); run_once(); }
    assert(!state.queued);
}
int main(void) {
    reset(); request(40); request(120); drain();
    assert(driver_calls == 1 && last_applied == 200 && state.applied_state == 1);
    assert(state.org_freq == 134 && state.eng_freq == 200);
    request(120); assert(!irq_pending);  /* unchanged OPP */

    reset(); request(40); inject_count = 1; drain();
    assert(driver_calls == 2 && last_applied == 200 && state.applied_state == 1);

    reset(); request(40); inject_count = 5; run_once();
    assert(driver_calls == 2 && irq_pending && state.queued); /* bounded replay */
    drain(); assert(last_applied == 200);

    reset(); request(40); fail_driver = true; drain();
    assert(state.applied_state == EAGOV_NO_STATE);
    request(40); drain(); assert(state.applied_state == 0 && driver_calls == 2);

    reset(); request(40); clamp_driver = true; drain();
    assert(state.applied_state == EAGOV_NO_STATE); /* QoS clamp is not acknowledged */
    clamp_driver = false; request(40); drain(); assert(state.applied_state == 0);

    reset(); request(40); stop_in_driver = true; inject_count = 1; drain();
    assert(!state.enabled && driver_calls == 1 && !irq_pending);

    reset(); request(40); drain(); request(120); drain();
    assert(state.power_delta == 150); request(40); drain(); assert(state.power_delta == -150);

    reset(); mask = 3;
    eagov_cpus[1] = (struct eagov_cpu){5, 270, true};
    request(40); assert(state.target_state == 2); drain();
    now = 30000000; request(40); drain(); assert(state.target_state == 0); /* stale peer */
    policy.max = 200; request(300); drain(); assert(last_applied == 200); /* thermal */

    reset(); qos_max = 200; request(300); drain();
    assert(last_applied == 200); request(300); assert(!irq_pending);
    qos_max = 300; request(300); drain(); assert(last_applied == 300);
    qos_min = 200; request(40); drain(); assert(last_applied == 200);
    qos_min = 300; qos_max = 200; request(300); drain(); assert(last_applied == 200);
    policy.cur = 100; request(300); drain(); assert(last_applied == 200);

    reset(); eagov_allow_oc = false;
    request(300); drain(); assert(last_applied == 200);
    assert(!eagov_should_scan(&state, now, 300, 0));
    assert(eagov_should_scan(&state, now, 300, SCHED_CPUFREQ_DL));
    assert(eagov_should_scan(&state, now + EAGOV_SCAN_NS, 300, 0));
    eagov_allow_oc = true;
    assert(eagov_should_scan(&state, now, 300, 0));
    request(300); drain(); assert(last_applied == 300);
    eagov_allow_oc = false; qos_max = 100;
    assert(eagov_should_scan(&state, now, 300, 0));
    request(300); drain(); assert(last_applied == 100);
    reset(); request(40); drain();
    assert(!eagov_should_scan(&state, now, 41, 0));
    assert(eagov_should_scan(&state, now, 100, 0));
    puts("PASS: EGO worker, QoS, native cap, OC opt-in, scan throttle and urgent bypass");
    return 0;
}
'''

source = (ROOT / "kernel/sched/cpufreq_energy_aware.c").read_text()
names = ("eagov_qos_range", "eagov_busy_power", "eagov_request", "eagov_should_scan", "eagov_work", "eagov_irq_work")
code = PREAMBLE + "\n".join(function(source, name) for name in names) + TESTS
with tempfile.TemporaryDirectory(prefix="ego-port-test-") as tmp:
    test = Path(tmp) / "test.c"
    binary = Path(tmp) / "test"
    test.write_text(code)
    subprocess.run(shlex.split(os.environ.get("HOSTCC", "cc")) + [
        "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-parameter", "-fsanitize=undefined", "-fno-sanitize-recover=all",
        "-iquote" + str(ROOT / "kernel/sched"), str(test), "-o", str(binary)
    ], check=True)
    subprocess.run([str(binary)], check=True, cwd=tmp)
