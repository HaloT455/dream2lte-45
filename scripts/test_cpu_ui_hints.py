#!/usr/bin/env python3
"""Compile actual UI-hint C and SchedTune entry points against host mocks.

Checks policy/lifetime wiring, not a running scheduler or hardware performance.
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

PREAMBLE = r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#define __read_mostly
#define __rcu
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define READ_ONCE(x) (x)
#define max(a,b) ((a) > (b) ? (a) : (b))
#define unlikely(x) (x)
#define container_of(p,t,m) ((t *)((char *)(p) - offsetof(t,m)))
static int rcu_depth, cgroup_locked, name_reads;
static bool on_dfl = true;
#define cgroup_subsys_on_dfl(ss) (on_dfl)
#define rcu_read_lock() (++rcu_depth)
#define rcu_read_unlock() do { assert(rcu_depth > 0); --rcu_depth; } while (0)
#define rcu_dereference(p) (assert(rcu_depth), (p))
#define rcu_access_pointer(p) (assert(cgroup_locked), (p))
#define rcu_assign_pointer(p,v) do { assert(cgroup_locked); (p) = (v); } while (0)
#define RCU_INIT_POINTER(p,v) rcu_assign_pointer(p,v)
struct cgroup { const char *name; };
struct cgroup_subsys_state { struct cgroup *cgroup; };
struct cfs_rq { unsigned int h_nr_running; int throttle_count; };
struct task_group {
    struct cgroup_subsys_state css;
    struct task_group *parent;
    unsigned int ui_hint;
    struct cfs_rq *cfs_rq[2];
};
static struct task_group root_task_group;
struct task_struct { struct task_group *tg; };
#define task_css(p,id) (assert(rcu_depth), &(p)->tg->css)
static int cgroup_name(struct cgroup *cg, char *buf, size_t size)
{
    assert(cgroup_locked);
    name_reads++;
    return snprintf(buf, size, "%s", cg->name);
}
"""

TUNE_MOCKS = r"""
static bool schedtune_initialized = true;
struct boost_groups { int boost_max; };
static struct boost_groups cpu_boost_groups[2];
#define per_cpu(v,cpu) ((v)[cpu])
struct schedtune { int boost, prefer_idle, perf_boost_idx, perf_constrain_idx; };
static struct schedtune native;
static struct schedtune *task_schedtune(struct task_struct *p)
{
    assert(rcu_depth);
    return &native;
}
#define trace_sched_tune_filter(...) ((void)0)
static int __schedtune_accept_deltas(int nrg, int cap, int boost, int constrain)
{
    return boost * 100 + constrain;
}
"""

TESTS = r"""
struct fixture {
    struct task_group tg;
    struct cgroup cg;
    struct cfs_rq rq[2];
};
static void group(struct fixture *f, const char *name, struct task_group *parent)
{
    memset(f, 0, sizeof(*f));
    f->cg.name = name;
    f->tg.css.cgroup = &f->cg;
    f->tg.parent = parent;
    f->tg.cfs_rq[0] = &f->rq[0];
    f->tg.cfs_rq[1] = &f->rq[1];
    cgroup_locked = 1;
    sched_cpu_ui_online(&f->tg);
    cgroup_locked = 0;
}
static void release(struct fixture *f)
{
    cgroup_locked = 1;
    sched_cpu_ui_released(&f->tg);
    cgroup_locked = 0;
    assert(!rcu_depth);
}
int main(void)
{
    struct fixture top, fg, window, bg, child, impostor, duplicate, replacement;
    struct task_struct task;
    cgroup_locked = 1;
    sched_cpu_ui_online(&root_task_group);
    cgroup_locked = 0;
    assert(root_task_group.ui_hint == 0 && !name_reads);
    group(&top, "top-app", &root_task_group);
    group(&fg, "foreground", &root_task_group);
    group(&window, "foreground_window", &root_task_group);
    group(&bg, "background", &root_task_group);
    group(&child, "pid_123", &top.tg);
    group(&impostor, "top-app", &bg.tg);
    assert(name_reads == 4);  /* No child-name matching or hot-path lookup. */
    assert(sched_cpu_ui_group_boost(&top.tg) == 10);
    assert(sched_cpu_ui_group_idle(&top.tg) == 1);
    assert(sched_cpu_ui_group_boost(&fg.tg) == 5);
    assert(sched_cpu_ui_group_boost(&window.tg) == 5);
    assert(sched_cpu_ui_group_idle(&fg.tg) == 0);
    assert(sched_cpu_ui_group_boost(&bg.tg) == 0);
    assert(sched_cpu_ui_group_boost(&child.tg) == 10);
    assert(sched_cpu_ui_group_boost(&impostor.tg) == 0);
    task.tg = &child.tg;
    assert(schedtune_task_boost(&task) == 10);
    assert(schedtune_prefer_idle(&task) == 1);
    assert(schedtune_accept_deltas(1, 1, &task) == 101);
    assert(schedtune_accept_deltas(-1, 1, &task) == INT_MAX);
    assert(schedtune_accept_deltas(1, -1, &task) == -INT_MAX);

    /* Existing CFS counts drive the hint; no parallel accounting to repair. */
    assert(schedtune_cpu_boost(0) == 0);
    fg.rq[0].h_nr_running = 2;
    assert(schedtune_cpu_boost(0) == 5);
    top.rq[0].h_nr_running = 1;
    assert(schedtune_cpu_boost(0) == 10);
    assert(schedtune_cpu_boost(1) == 0);
    top.rq[0].h_nr_running = 0;
    top.rq[1].h_nr_running = 1;
    assert(schedtune_cpu_boost(0) == 5 && schedtune_cpu_boost(1) == 10);
#ifdef CONFIG_CFS_BANDWIDTH
    top.rq[1].throttle_count = 1;
    assert(schedtune_cpu_boost(1) == 0);
    top.rq[1].throttle_count = 0;
    assert(schedtune_cpu_boost(1) == 10);
#endif
    top.rq[1].h_nr_running = 0;
    fg.rq[0].h_nr_running = 0;
    window.rq[1].h_nr_running = 1;
    assert(schedtune_cpu_boost(0) == 0 && schedtune_cpu_boost(1) == 5);
    window.rq[1].h_nr_running = 0;
    assert(schedtune_cpu_boost(1) == 0);
    task.tg = &fg.tg;
    assert(schedtune_task_boost(&task) == 5);
    assert(!schedtune_prefer_idle(&task));
    assert(schedtune_accept_deltas(1, 1, &task) == 0);
    task.tg = &bg.tg;
    assert(!schedtune_task_boost(&task));
    assert(name_reads == 4);

    /* Native mounted SchedTune wins, including zero and negative policy. */
    task.tg = &top.tg;
    top.rq[0].h_nr_running = 1;
    on_dfl = false;
    for (int value = -100; value <= 100; value += 10) {
        native.boost = cpu_boost_groups[0].boost_max = value;
        native.prefer_idle = 0;
        assert(!sched_cpu_ui_active());
        assert(schedtune_cpu_boost(0) == value);
        assert(schedtune_task_boost(&task) == value);
        assert(!schedtune_prefer_idle(&task));
    }
    native.perf_boost_idx = 3;
    native.perf_constrain_idx = 4;
    assert(schedtune_accept_deltas(1, 1, &task) == 304);
    on_dfl = true;
    assert(schedtune_task_boost(&task) == 10);
    sysctl_sched_cpu_ui_hints = 0;
    assert(!sched_cpu_ui_active());
    assert(schedtune_task_boost(&task) == 100);
    sysctl_sched_cpu_ui_hints = 1;
    assert(schedtune_cpu_boost(0) == 10);
    schedtune_initialized = false;
    assert(!schedtune_task_boost(&task) && !schedtune_prefer_idle(&task));
    schedtune_initialized = true;

    /* A live rename cannot overwrite the registered group; release is RCU. */
    top.cg.name = "renamed-top";
    group(&duplicate, "top-app", &root_task_group);
    assert(!duplicate.tg.ui_hint);
    release(&duplicate);
    release(&child);
    assert(schedtune_cpu_boost(0) == 10);
    top.rq[0].h_nr_running = 0;
    release(&top);
    assert(!cpu_ui_groups[0] && !schedtune_cpu_boost(0));
    group(&replacement, "top-app", &root_task_group);
    assert(replacement.tg.ui_hint == 1);
    replacement.rq[0].h_nr_running = 1;
    assert(schedtune_cpu_boost(0) == 10);
    assert(!rcu_depth && !cgroup_locked);
    puts("PASS: CPU UI identities, CFS snapshots, throttle, RCU wiring, native precedence");
}
"""


def extract(source, name):
    match = re.search(r"^int\s+" + name + r"\(", source, re.M)
    if not match:
        raise ValueError(f"missing {name}")
    return source[match.start():source.index("\n}", match.start()) + 2]


def main():
    source = (ROOT / "kernel/sched/cpu_ui.c").read_text()
    source = re.sub(r'^#include "[^"]+"\n', "", source, flags=re.M)
    tune = (ROOT / "kernel/sched/tune.c").read_text()
    entry_points = "\n".join(extract(tune, name) for name in (
        "schedtune_cpu_boost", "schedtune_task_boost", "schedtune_prefer_idle",
        "schedtune_accept_deltas"))
    code = PREAMBLE + source + TUNE_MOCKS + entry_points + TESTS
    header = (ROOT / "kernel/sched/cpu_ui.h").read_text()
    stubs = "#include <stdbool.h>\n#include <assert.h>\n" + header + r"""
int main(void) {
    assert(!sched_cpu_ui_active());
    sched_cpu_ui_online(0);
    sched_cpu_ui_released(0);
    assert(!sched_cpu_ui_cpu_boost(0));
    assert(!sched_cpu_ui_task_boost(0));
    assert(!sched_cpu_ui_prefer_idle(0));
}
"""
    with tempfile.TemporaryDirectory(prefix="cpu-ui-test-") as tmp:
        for name, unit, defines in (
            ("bandwidth", code, ["-DCONFIG_CFS_BANDWIDTH=1"]),
            ("no-bandwidth", code, []), ("disabled", stubs, []),
        ):
            src = Path(tmp) / f"{name}.c"
            binary = Path(tmp) / name
            src.write_text(unit)
            subprocess.run(shlex.split(os.environ.get("HOSTCC", "cc")) + [
                "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-fsanitize=undefined",
                *defines, str(src), "-o", str(binary),
            ], check=True)
            subprocess.run([str(binary)], check=True)
    print("PASS: feature-disabled stubs; host mocks do not prove SMP/device behavior")


if __name__ == "__main__":
    main()
