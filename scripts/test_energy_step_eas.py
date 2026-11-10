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
    assert(energy_step_target_capacity(ordinary,4,180,256,128,1024,8) == 360);
    /* Same capacities/load, different power costs => different target. */
    assert(energy_step_target_capacity(costly_mid,4,180,256,128,1024,8) == 720);
    assert(energy_step_target_capacity(ordinary,4,180,256,128,1024,2) == 720);
    assert(energy_step_target_capacity(ordinary,4,180,256,128,1024,0) == 225);
    assert(energy_step_target_capacity(NULL,0,180,256,128,1024,8) == 225);
    assert(energy_step_target_capacity(ordinary,4,4096,256,128,305,8) == 305);
    assert(energy_step_target_capacity(ordinary,4,180,0,128,1024,8) == 512);

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
    puts("PASS: power costs change selection; zero/full load and policy caps");
    puts("PASS: monotonic capacity across load/current/thermal-limit combinations");
    puts("PASS: actual EAS capacity-index search cannot overrun the model");
    return 0;
}
'''


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

        # Exercise the new governor's actual deferred-work functions with the
        # established queue/driver-interleaving suite, including publication.
        governor = (ROOT / "kernel/sched/cpufreq_energy_step.c").read_text()
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
