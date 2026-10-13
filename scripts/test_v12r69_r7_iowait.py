#!/usr/bin/env python3
"""Execute real EnergyStep I/O functions across burst/idle/shared-CPU gaps."""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path(os.environ.get("ENERGYSTEP_TEST_SOURCE", "kernel/sched/cpufreq_energy_step.c")).read_text()

def function(marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]

reset = function("static bool esgov_iowait_reset(") if "static bool esgov_iowait_reset(" in source else ""
apply = function("static void esgov_iowait_boost(")
has_time = "u64 time" in apply.split("{", 1)[0]
stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint64_t u64;
typedef int64_t s64;
#define TICK_NSEC 4000000
#define SCHED_CPUFREQ_IOWAIT 1
struct cpufreq_policy { unsigned int min; };
struct esgov_policy { struct cpufreq_policy *policy; };
struct esgov_cpu {
    struct esgov_policy *sg_policy;
    bool iowait_boost_pending;
    unsigned int iowait_boost, iowait_boost_max;
    u64 last_update;
};
'''
main = r'''
static void apply_boost(struct esgov_cpu *cpu, u64 time, unsigned long *u, unsigned long *m)
{ (void)time; APPLY; }
int main(void)
{
    struct cpufreq_policy policy={.min=200};
    struct esgov_policy sg={.policy=&policy};
    struct esgov_cpu cpu={.sg_policy=&sg,.iowait_boost_max=1600};
    unsigned long u, m;
    /* I/O after an idle gap must restart even if the old request is pending. */
    for (int pending=0; pending<=1; pending++) {
        cpu.last_update=10000000;
        cpu.iowait_boost=1600;
        cpu.iowait_boost_pending=pending;
        esgov_set_iowait_boost(&cpu, 20000000, SCHED_CPUFREQ_IOWAIT);
        assert(cpu.iowait_boost==200 && cpu.iowait_boost_pending);
    }
    cpu.last_update=20000000;
    u=0; m=1024; apply_boost(&cpu, 20000000, &u, &m);
    assert(u==200 && m==1600 && !cpu.iowait_boost_pending);
    /* Frequent I/O still boosts; duplicate unconsumed requests do not double. */
    esgov_set_iowait_boost(&cpu, 21000000, SCHED_CPUFREQ_IOWAIT);
    assert(cpu.iowait_boost==400);
    esgov_set_iowait_boost(&cpu, 22000000, SCHED_CPUFREQ_IOWAIT);
    assert(cpu.iowait_boost==400);
    cpu.last_update=22000000;
    u=0; m=1024; apply_boost(&cpu, 22000000, &u, &m);
    u=0; m=1024; apply_boost(&cpu, 23000000, &u, &m);
    assert(cpu.iowait_boost==200 && u==200);
    u=0; m=1024; apply_boost(&cpu, 24000000, &u, &m);
    assert(!cpu.iowait_boost && !u);
    /* Shared-policy sibling remains a valid WALT sample, but I/O boost expires. */
    cpu.last_update=30000000; cpu.iowait_boost=1600; cpu.iowait_boost_pending=true;
    u=100; m=1024; apply_boost(&cpu, 35000001, &u, &m);
    assert(!cpu.iowait_boost && !cpu.iowait_boost_pending && u==100 && m==1024);
    cpu.last_update=40000000; cpu.iowait_boost=1600; cpu.iowait_boost_pending=true;
    esgov_set_iowait_boost(&cpu, 45000001, 0);
    assert(!cpu.iowait_boost && !cpu.iowait_boost_pending);
    puts("PASS: sporadic I/O restarts from minimum, including pending boost");
    puts("PASS: shared CPU boost expires independently of WALT sample lifetime");
    puts("PASS: burst ramp, duplicate requests and decay remain functional");
}
'''.replace("APPLY", "esgov_iowait_boost(cpu, " + ("time, " if has_time else "") + "u, m)")
with tempfile.TemporaryDirectory(prefix="r7-iowait-") as tmp:
    c, exe = Path(tmp)/"iowait.c", Path(tmp)/"iowait"
    c.write_text(stub + reset + function("static void esgov_set_iowait_boost(") + apply + main)
    subprocess.run([os.environ.get("HOSTCC", "cc"), "-std=gnu99", "-Wall", "-Wextra",
                    "-Werror", str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)
