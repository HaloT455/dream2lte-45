#!/usr/bin/env python3
"""Exercise actual PSI init/task/group C through the 4.4 boot ordering.

Tasks fork and enqueue after sched_init but before core initcalls. Their first
dequeue must never subtract an enqueue that accounting skipped. Workqueue
creation is separately delayed; early accounting must not queue onto NULL.
"""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path(os.environ.get('PSI_TEST_SOURCE', 'kernel/sched/psi.c')).read_text()
def function(marker):
    begin = source.index(marker)
    opening = source.index('{', begin)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[begin:end]

stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <limits.h>
#define __init
#define unlikely(x) (x)
#define KERN_ERR ""
#define printk_deferred printf
#define TSK_RUNNING (1U << 2)
#define PF_WQ_WORKER 32
#define PSI_FREQ 501
typedef uint32_t u32;
typedef uint64_t u64;
enum psi_states { PSI_IO_SOME, PSI_IO_FULL, PSI_MEM_SOME, PSI_MEM_FULL,
                  PSI_CPU_SOME, PSI_NONIDLE, NR_PSI_STATES };
enum { NR_IOWAIT, NR_MEMSTALL, NR_RUNNING };
struct work_struct { int unused; };
struct delayed_work { bool pending; };
struct psi_group_cpu { unsigned int tasks[3], state_mask; int seq; };
struct psi_group { struct psi_group_cpu *pcpu; struct delayed_work clock_work;
                   unsigned int trigger_states; int polling; };
struct task_struct { int pid, psi_flags; unsigned long flags; const char *comm; };
static struct psi_group_cpu cpus[2];
static struct psi_group psi_system = { .pcpu = cpus };
static bool psi_enable = true, psi_initialized;
static int psi_disabled, psi_bug, queued;
static int cpu;
static u64 psi_period;
static void *system_wq;
static void group_init(struct psi_group *g) { (void)g; }
static u64 jiffies_to_nsecs(unsigned int j) { return (u64)j * 4000000; }
static void static_branch_enable(int *key) { *key = 1; }
static void smp_wmb(void) {}
static int task_cpu(struct task_struct *t) { (void)t; return cpu; }
#define per_cpu_ptr(p,c) (&(p)[c])
static void write_seqcount_begin(int *s) { ++*s; }
static void write_seqcount_end(int *s) { ++*s; }
static void record_times(struct psi_group_cpu *c, int n, bool tick)
{ (void)c; (void)n; (void)tick; }
static void psi_update_work(struct work_struct *w) { (void)w; }
static void (*wq_worker_last_func(struct task_struct *t))(struct work_struct *)
{ (void)t; return NULL; }
static bool delayed_work_pending(struct delayed_work *w) { return w->pending; }
static void schedule_delayed_work(struct delayed_work *w, unsigned int delay)
{ assert(system_wq); assert(delay); w->pending = true; ++queued; }
static void mod_delayed_work(void *q, struct delayed_work *w, unsigned int delay)
{ assert(q); assert(delay); w->pending = true; ++queued; }
static int atomic_cmpxchg(int *p, int old, int value)
{ int before = *p; if (before == old) *p = value; return before; }
'''
markers = ['void __init psi_init(', 'static bool test_state(',
           'static u32 psi_group_change(', 'static struct psi_group *iterate_groups(',
           'void psi_task_change(']
activation = 'static int __init psi_enable_accounting('
late = function(activation) if activation in source else ''
main = r'''
int main(void)
{
    struct task_struct init = { .pid = 1, .comm = "init" };
    struct task_struct kthreadd = { .pid = 2, .comm = "kthreadd" };
    psi_init();
    assert(psi_period);
    /* rest_init forks init/kthreadd before early/core initcalls. */
    cpu = 0;
    psi_task_change(&init, 0, TSK_RUNNING);
    psi_task_change(&kthreadd, 0, TSK_RUNNING);
    assert(!queued); /* system_wq does not exist yet */
    LATE_ACTIVATION
    psi_task_change(&kthreadd, TSK_RUNNING, 0);
    psi_task_change(&init, TSK_RUNNING, 0);
    printf("bootstrap running=%u psi_bug=%d\n", cpus[0].tasks[NR_RUNNING], psi_bug);
    fflush(stdout);
    assert(!psi_bug && cpus[0].tasks[NR_RUNNING] == 0);
    assert(psi_initialized && !queued);
    /* Subsequent workqueue-backed activity is counted on both CPUs. */
    system_wq = &queued;
    cpu = 1;
    psi_task_change(&init, 0, TSK_RUNNING);
    assert(cpus[1].tasks[NR_RUNNING] == 1 && queued == 1);
    psi_task_change(&init, TSK_RUNNING, 0);
    assert(cpus[1].tasks[NR_RUNNING] == 0 && !psi_bug && !init.psi_flags);
    psi_system.clock_work.pending = false;
    psi_system.trigger_states = 1U << PSI_MEM_SOME;
    psi_task_change(&init, 0, 1U << NR_MEMSTALL);
    assert(cpus[1].tasks[NR_MEMSTALL] == 1 && psi_system.polling == 1 && queued == 2);
    psi_task_change(&init, 1U << NR_MEMSTALL, 0);
    assert(cpus[1].tasks[NR_MEMSTALL] == 0 && !psi_bug && !init.psi_flags);
    psi_enable = false;
    psi_initialized = false;
    psi_init();
    assert(psi_disabled && !psi_initialized);
    puts("PASS: boot enqueue/dequeue balanced before workqueues exist; late activity and PSI triggers work");
}
'''.replace('LATE_ACTIVATION', 'psi_enable_accounting();' if late else '')
with tempfile.TemporaryDirectory(prefix='r9-psi-bootstrap-') as tmp:
    c, exe = Path(tmp)/'bootstrap.c', Path(tmp)/'bootstrap'
    c.write_text(stub + '\n'.join(function(m) for m in markers) + late + main)
    subprocess.run([os.environ.get('HOSTCC', 'cc'), '-std=gnu99', '-Wall', '-Wextra',
                    '-Werror', '-Wno-unused-function', '-Wno-unused-parameter',
                    str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)
