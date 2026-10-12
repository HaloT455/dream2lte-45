#!/usr/bin/env python3
"""Compile actual PSI read/write/accounting functions against a host clock.

Tests reader cadence, pending activity, monitor baselines and exact write data.
The stubs do not emulate the scheduler or establish handset stability.
"""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path(os.environ.get("PSI_TEST_SOURCE", "kernel/sched/psi.c")).read_text()
header = Path("include/linux/psi_types.h").read_text()
types = header[header.index("enum psi_task_count {"):header.index("#else")]

def function(marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]

stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <stdarg.h>
#include <sys/types.h>
typedef uint32_t u32;
typedef uint64_t u64;
typedef int seqcount_t;
typedef int wait_queue_head_t;
typedef int atomic_t;
struct delayed_work { int unused; };
struct mutex { int held; };
struct list_head { struct list_head *next, *prev; };
#define ____cacheline_aligned_in_smp
#define __percpu
#define __user
#define FSHIFT 11
#define FIXED_1 (1UL << FSHIFT)
#define EXP_10s 1677
#define EXP_60s 1981
#define EXP_300s 2034
#define LOAD_INT(x) ((x) >> FSHIFT)
#define LOAD_FRAC(x) LOAD_INT(((x) & (FIXED_1 - 1)) * 100)
#define WINDOW_MIN_US 500000
#define WINDOW_MAX_US 10000000
#define UPDATES_PER_WINDOW 10
#define NSEC_PER_USEC 1000ULL
#define GFP_KERNEL 0
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define kmalloc(n,g) malloc(n)
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define PTR_ERR(p) ((intptr_t)(p))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define per_cpu_ptr(p,c) (&(p)[c])
#define for_each_possible_cpu(c) for ((c)=0; (c)<2; (c)++)
static bool psi_disabled;
#define static_branch_likely(p) (*(p))
static u64 clock_now;
static u64 sched_clock(void) { return clock_now; }
static u64 cpu_clock(int cpu) { (void)cpu; return clock_now; }
static u64 div_u64(u64 a, u32 b) { assert(b); return a/b; }
static u32 nsecs_to_jiffies(u64 n) { return n/1000000ULL; }
static unsigned int read_seqcount_begin(seqcount_t *s) { (void)s; return 0; }
static bool read_seqcount_retry(seqcount_t *s, unsigned int n)
{ (void)s; (void)n; return false; }
static void mutex_lock(struct mutex *m) { assert(!m->held); m->held=1; }
static void mutex_unlock(struct mutex *m) { assert(m->held); m->held=0; }
static void init_waitqueue_head(wait_queue_head_t *q) { *q=0; }
static void list_add(struct list_head *n, struct list_head *h)
{ n->next=h->next; n->prev=h; h->next->prev=n; h->next=n; }
struct seq_file { struct mutex lock; void *private; char output[1024]; size_t len; };
struct file { void *private_data; };
static void seq_printf(struct seq_file *s, const char *fmt, ...)
{
    va_list ap; va_start(ap,fmt);
    s->len += vsnprintf(s->output+s->len,sizeof(s->output)-s->len,fmt,ap);
    va_end(ap);
}
static int copies, copy_fail, destroyed;
static int copy_from_user(void *d, const void *s, size_t n)
{ copies++; if (copy_fail) return 1; memcpy(d,s,n); return 0; }
#define rcu_assign_pointer(p,v) ((p)=(v))
static void synchronize_rcu(void) {}
'''
after_types = r'''
static struct psi_group psi_system;
static struct psi_group_cpu cpus[2];
static u64 psi_period=2000000000ULL;
static void psi_trigger_destroy(struct psi_trigger *t) { destroyed++; free(t); }
'''
main = r'''
static void reset_group(struct psi_group *g)
{
    memset(g,0,sizeof(*g)); memset(cpus,0,sizeof(cpus));
    g->pcpu=cpus; g->triggers.next=g->triggers.prev=&g->triggers;
    g->trigger_min_period=UINT32_MAX;
    g->avg_next_update=psi_period;
}
int main(int argc, char **argv)
{
    (void)argv;
    reset_group(&psi_system);
    if (argc==1) {
        struct seq_file seq={0};
        struct psi_group *g=&psi_system;
        /* A read within a period must not decay an existing nonzero average. */
        g->avg[PSI_MEM_SOME][0]=25*FIXED_1;
        clock_now=1000000000ULL;
        assert(psi_show(&seq,g,PSI_MEM)==0);
        assert(g->avg_next_update==psi_period);
        assert(g->avg[PSI_MEM_SOME][0]==25*FIXED_1);
        /* At the deadline, publish exactly one average update. */
        cpus[0].times[PSI_MEM_SOME]=100000000;
        cpus[0].times[PSI_NONIDLE]=100000000;
        clock_now=psi_period; seq.len=0;
        psi_show(&seq,g,PSI_MEM);
        assert(g->avg_next_update==2*psi_period);
        unsigned long average=g->avg[PSI_MEM_SOME][0];
        clock_now+=100000000ULL; seq.len=0;
        psi_show(&seq,g,PSI_MEM);
        assert(g->avg[PSI_MEM_SOME][0]==average);
        /* A worker sees the activity that a preceding reader collected. */
        u32 changed=0;
        collect_percpu_times(g,&changed);
        assert(changed & (1U << PSI_MEM_SOME));
        collect_percpu_times(g,&changed); assert(changed==0);
		/* Two close reads must retain a short stall instead of rounding it away. */
		reset_group(g);
		cpus[0].times[PSI_MEM_SOME]=100000;
		cpus[0].times[PSI_NONIDLE]=100000;
		collect_percpu_times(g,NULL);
		assert(g->total[PSI_MEM_SOME]==100000);
        /* A delayed average must retain a multi-second u64 backlog. */
        reset_group(g);
        g->total[PSI_MEM_SOME]=5000000000ULL;
        clock_now=5000000000ULL;
        g->avg_next_update=update_averages(g,clock_now);
        assert(g->avg_total[PSI_MEM_SOME]==3000000000ULL);
        puts("PASS: read cadence, deadline publication, reader activity and u64 backlog");
    } else {
        struct seq_file seq={0}; struct file f={&seq};
        const char *plain="some 70000 1000000";
        clock_now=10000000000ULL;
        psi_system.total[PSI_MEM_SOME]=8000000000ULL;
        /* Uncollected pressure before registration belongs to the baseline. */
        cpus[0].times[PSI_MEM_SOME]=100000000;
        cpus[0].times[PSI_NONIDLE]=100000000;
        assert(psi_write(&f,plain,strlen(plain),PSI_MEM)==(ssize_t)strlen(plain));
        struct psi_trigger *t=seq.private;
        assert(t->win.size==1000000000ULL);
        assert(t->threshold==70000000ULL);
        assert(t->win.start_value==psi_system.total[PSI_MEM_SOME]);
        assert(t->win.start_time==clock_now);
        assert(t->win.start_value==8100000000ULL);
        const char *newline="full 70000 1000000\n";
        assert(psi_write(&f,newline,strlen(newline),PSI_MEM)==(ssize_t)strlen(newline));
        assert(destroyed==1);
        assert(psi_write(&f,plain,strlen(plain)+1,PSI_MEM)==(ssize_t)strlen(plain)+1);
        assert(((struct psi_trigger *)seq.private)->win.size==1000000000ULL);
        int before=copies; void *old=seq.private;
        assert(psi_write(&f,"",0,PSI_MEM)==-EINVAL && copies==before);
        assert(psi_write(&f,"some 70000 1000000 trailing-data-xxxxxxxx",40,PSI_MEM)==-EINVAL);
        assert(seq.private==old);
        copy_fail=1; assert(psi_write(&f,plain,strlen(plain),PSI_MEM)==-EFAULT);
        assert(seq.private==old);
        copy_fail=0;
        assert(psi_write(&f,"some 0 1000000",14,PSI_MEM)==-EINVAL);
        assert(seq.private==old);
        psi_trigger_destroy(seq.private);
        puts("PASS: exact writes, fresh collected monitor baseline and invalid-input rejection");
    }
    return 0;
}
'''
markers = (
    "static unsigned long psi_fixed_power_int(", "static unsigned long psi_calc_load(",
    "static unsigned long psi_calc_load_n(", "static void get_recent_times(",
    "static void calc_avgs(", "static void collect_percpu_times(",
    "static u64 update_averages(", "static void window_reset(", "int psi_show(",
    "struct psi_trigger *psi_trigger_create(", "static ssize_t psi_write(",
)
with tempfile.TemporaryDirectory(prefix="psi-test-") as tmp:
    c = Path(tmp)/"psi.c"
    exe = Path(tmp)/"psi"
    c.write_text(stub+types+after_types+"\n".join(function(m) for m in markers)+main)
    subprocess.run([os.environ.get("HOSTCC","cc"),"-std=gnu99","-Wall","-Wextra",
                    "-Werror","-Wno-unused-parameter",str(c),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=10)
    subprocess.run([str(exe),"writes"],check=True,timeout=10)
