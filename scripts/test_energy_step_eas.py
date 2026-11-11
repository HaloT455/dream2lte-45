#!/usr/bin/env python3
"""Execute the shared governor/EAS capacity math and actual EAS index search.

Host arithmetic and boundary tests; not an Exynos hardware/power measurement.
"""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import test_schedutil_work as deferred

ROOT = Path(__file__).resolve().parents[1]

PREAMBLE = r'''
#include <assert.h>
#include <stdio.h>
struct capacity_state { unsigned long cap, power; };
#include "energy_step_math.h"
struct sched_group_energy {
    unsigned int nr_cap_states;
    struct capacity_state *cap_states;
};
struct energy_env { int cap_idx; unsigned long util; };
static unsigned long group_max_util(struct energy_env *env) { return env->util; }
'''

TESTS = r'''
int main(void)
{
    struct capacity_state ordinary[] = {{128,10},{256,20},{512,50},{1024,130}};
    struct capacity_state costly_mid[] = {{128,10},{256,100},{512,110},{1024,130}};
    struct sched_group_energy energy = {4, ordinary};
    struct energy_env env;
    unsigned long util, current, last, result;
    unsigned long limits[][2] = {{0,1024},{128,1024},{200,700},{500,500},{700,200}};
    unsigned int k;

    assert(energy_step_target_capacity(ordinary,4,0,256,128,1024,8) == 128);
    assert(energy_step_target_capacity(ordinary,4,180,256,128,1024,8) == 180);
    assert(energy_step_target_capacity(costly_mid,4,256,256,128,1024,8) == 256);
    /* Same capacities/load, different power costs => different target. */
    assert(energy_step_target_capacity(ordinary,4,512,256,128,1024,8) == 576);
    assert(energy_step_target_capacity(costly_mid,4,512,256,128,1024,8) == 768);
    assert(energy_step_target_capacity(ordinary,4,512,256,128,1024,2) == 768);
    assert(energy_step_target_capacity(ordinary,4,512,256,128,1024,0) == 576);
    assert(energy_step_target_capacity(NULL,0,512,256,128,1024,8) == 576);
    assert(energy_step_target_capacity(NULL,0,800,256,128,1024,8) == 1000);
    assert(energy_step_target_capacity(ordinary,4,4096,256,128,305,8) == 305);
    assert(energy_step_target_capacity(ordinary,4,180,0,128,1024,8) == 180);

    for (k = 0; k < sizeof(limits)/sizeof(limits[0]); k++) {
        unsigned long low = limits[k][0], high = limits[k][1];
        if (low > high) low = high;
        for (current = 1; current <= 1024; current += 31) {
            last = 0;
            for (util = 0; util <= 2048; util++) {
                result = energy_step_target_capacity(ordinary,4,util,current,
                                                      low,high,8);
                assert(result >= low && result <= high);
                assert(result >= last);
                last = result;
            }
        }
    }
    /* The scheduler must stay in the last state at/above model saturation. */
    for (util = 0; util < 4096; util++) {
        env.util = util;
        assert(find_new_capacity(&env, &energy) >= 0);
        assert(env.cap_idx < 4);
        if (env.cap_idx < 3) assert(ordinary[env.cap_idx].cap >= util);
    }
    puts("PASS: light load skips boost; heavy load retains headroom and power steps");
    puts("PASS: monotonic capacity across load/current/thermal-limit combinations");
    puts("PASS: actual EAS capacity-index search cannot overrun the model");
    return 0;
}
'''

SNAPSHOT_PREAMBLE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#define current get_current()
typedef uint64_t u64;
typedef struct { unsigned int sequence; } seqcount_t;
struct capacity_state { unsigned long cap, power; };
#include "energy_step_math.h"
struct sched_group_energy { unsigned int nr_cap_states; struct capacity_state *cap_states; };
struct esgov_policy { int update_lock; };
struct cpufreq_policy {
    unsigned int cpu, min, max, cur, related_cpus;
    struct { unsigned int max_freq; } cpuinfo;
    void *governor_data;
};
static struct sched_group_energy *sge_array[8][8];
#define SD_LEVEL0 0
#define ESGOV_POWER_STEPS 8U
#define per_cpu(array,cpu) ((array)[cpu])
#define for_each_cpu(cpu,mask) for ((cpu)=0; (cpu)<8; (cpu)++) if ((mask)&(1U<<(cpu)))
#define arch_scale_cpu_capacity(a,cpu) (1024UL)
#define div64_u64(a,b) ((a)/(b))
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define raw_spin_lock_irqsave(lock,flags) do { (flags)=0; assert(!*(lock)); *(lock)=1; } while (0)
#define raw_spin_unlock_irqrestore(lock,flags) do { (void)(flags); assert(*(lock)); *(lock)=0; } while (0)
static void write_seqcount_begin(seqcount_t *s) { s->sequence++; }
static void write_seqcount_end(seqcount_t *s) { s->sequence++; }
static unsigned int read_seqcount_begin(seqcount_t *s) { assert(!(s->sequence&1)); return s->sequence; }
static bool read_seqcount_retry(seqcount_t *s, unsigned int old) { return old != s->sequence; }
'''

SNAPSHOT_TESTS = r'''
int main(void)
{
    struct capacity_state states[] = {{128,10},{256,20},{512,50},{1024,130}};
    struct sched_group_energy model = {4, states};
    struct esgov_policy governor = {0};
    struct cpufreq_policy policy = {0,128000,1024000,256000,15,{1024000},&governor};
    unsigned int cpu;
    for (cpu=0; cpu<4; cpu++) sge_array[cpu][0] = &model;
    assert(energy_step_cpu_capacity(0,512) == 512);
    esgov_publish_capacity(&policy,true);
    for (cpu=0; cpu<4; cpu++) assert(energy_step_cpu_capacity(cpu,512) == 576);
    assert(energy_step_cpu_capacity(4,512) == 512);
    policy.max = 200000;
    esgov_publish_capacity(&policy,true);
    for (cpu=0; cpu<4; cpu++) assert(energy_step_cpu_capacity(cpu,1000) == 200);
    esgov_publish_capacity(&policy,false);
    for (cpu=0; cpu<4; cpu++) assert(energy_step_cpu_capacity(cpu,512) == 512);
    assert(!governor.update_lock);
    puts("PASS: actual shared-policy snapshots publish limits, disable on stop, and tolerate kernel current macro");
    return 0;
}
'''


def c_function(source, signature):
    start = source.index(signature)
    return source[start:source.index("\n}", start) + 2]


def main():
    fair = (ROOT / "kernel/sched/fair.c").read_text()
    start = fair.index("static int find_new_capacity(")
    end = fair.index("\n}", start) + 2
    with tempfile.TemporaryDirectory(prefix="energy-step-host-") as tmp:
        source = Path(tmp) / "test.c"
        binary = Path(tmp) / "test"
        source.write_text(PREAMBLE + fair[start:end] + TESTS)
        cc = shlex.split(os.environ.get("HOSTCC", "cc"))
        subprocess.run(cc + ["-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=undefined", "-fno-sanitize-recover=all",
                            "-iquote", str(ROOT / "kernel/sched"), str(source),
                            "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)

        governor = (ROOT / "kernel/sched/cpufreq_energy_step.c").read_text()
        start = governor.index("struct esgov_capacity_snapshot {")
        definition = governor[start:governor.index("\n};", start) + 3]
        source.write_text(SNAPSHOT_PREAMBLE + definition +
                          "\nstatic struct esgov_capacity_snapshot esgov_capacity[8];\n" +
                          c_function(governor, "static void esgov_publish_capacity(") +
                          c_function(governor, "unsigned long energy_step_cpu_capacity(") +
                          SNAPSHOT_TESTS)
        subprocess.run(cc + ["-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=undefined", "-fno-sanitize-recover=all",
                            "-iquote", str(ROOT / "kernel/sched"), str(source),
                            "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)

        # Exercise the new governor's actual deferred-work functions with the
        # established queue/driver-interleaving suite, including publication.
        governor = governor.replace("esgov", "sugov")
        names = ("sugov_up_down_rate_limit", "sugov_update_commit",
                 "sugov_work", "sugov_irq_work")
        publish = r'''
static void sugov_publish_capacity(struct cpufreq_policy *p, bool enabled)
{
    assert(enabled && p == state.policy);
    assert(!state.update_lock && !state.work_lock);
}
'''
        source.write_text(deferred.PREAMBLE + publish + "\n".join(
            deferred.function(governor, name) for name in names) + deferred.TESTS)
        subprocess.run(cc + ["-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                            "-Wno-unused-parameter", "-fsanitize=undefined",
                            "-fno-sanitize-recover=all", str(source),
                            "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
