#!/usr/bin/env python3
"""Execute real PSI collection, task-change and polling code across idle gaps.

Scheduler/page accounting stubs isolate wake decisions. This does not measure
phone battery life or prove the actual ROM's LMKD thresholds are appropriate.
"""
from pathlib import Path
import os
import subprocess
import tempfile

source=Path(os.environ.get('PSI_TEST_SOURCE','kernel/sched/psi.c')).read_text()
wq=Path('kernel/workqueue.c').read_text()
def function(s,marker):
    start=s.index(marker); opening=s.index('{',start); depth,end=1,opening+1
    while depth:
        depth+=(s[end]=='{')-(s[end]=='}');end+=1
    return s[start:end]

stub=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef uint64_t u64;
typedef uint32_t u32;
typedef void (*work_func_t)(struct work_struct *);
struct work_struct { int dummy; };
struct delayed_work { struct work_struct work; bool pending; };
struct worker { work_func_t last_func; };
struct task_struct { int pid,psi_flags; unsigned long flags; const char *comm; struct worker *worker; };
enum { PSI_IO_SOME,PSI_IO_FULL,PSI_MEM_SOME,PSI_MEM_FULL,PSI_CPU_SOME,PSI_NONIDLE,NR_PSI_STATES };
#define TSK_RUNNING 4
#define PF_WQ_WORKER 16
#define PSI_FREQ 501
#define UPDATES_PER_WINDOW 10
#define ULLONG_MAX UINT64_MAX
#define unlikely(x) (x)
#define KERN_ERR ""
#define printk_deferred printf
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define to_delayed_work(p) container_of(p,struct delayed_work,work)
struct psi_group {
    struct delayed_work clock_work;
    int update_lock,polling;
    u64 polling_next_update,polling_until,trigger_min_period,avg_next_update;
    u64 total[NR_PSI_STATES-1];
    u32 pending_states,trigger_states;
};
static struct psi_group psi_system;
static bool psi_initialized=true;
static int psi_bug;
static void *system_wq=(void *)1;
static u64 now;
static int scheduled,modified,averages,triggers,collected;
static u32 state_mask,cpu_times[2][NR_PSI_STATES];
static unsigned long delay;
static struct worker worker;
static void *kthread_data(struct task_struct *t) { return t->worker; }
static int task_cpu(struct task_struct *t) { (void)t;return 0; }
static u64 sched_clock(void) { return now; }
static u32 nsecs_to_jiffies(u64 ns) { return ns/4000000; }
static u64 div_u64(u64 a,u32 b) { assert(b);return a/b; }
#define for_each_possible_cpu(c) for((c)=0;(c)<2;(c)++)
static void get_recent_times(struct psi_group *g,int c,u32 *times,u32 *changed)
{ (void)g;*changed=0;for(int s=0;s<NR_PSI_STATES;s++) {
    times[s]=cpu_times[c][s];if(times[s])*changed|=1U<<s;cpu_times[c][s]=0;
  } ++collected; }
static void mutex_lock(int *p) { assert(!*p);*p=1; }
static void mutex_unlock(int *p) { assert(*p);*p=0; }
static int atomic_read(int *p) { return *p; }
static void atomic_set(int *p,int n) { *p=n; }
static int atomic_cmpxchg(int *p,int old,int n) { int r=*p;if(r==old)*p=n;return r; }
static void smp_mb(void) {}
static bool delayed_work_pending(struct delayed_work *w) { return w->pending; }
static void mod_delayed_work(void *q,struct delayed_work *w,unsigned long d)
{ assert(q);w->pending=true;delay=d;++modified; }
static void schedule_delayed_work(struct delayed_work *w,unsigned long d)
{ w->pending=true;delay=d;++scheduled; }
static u32 psi_group_change(struct psi_group *g,int c,int clear,int set)
{ (void)g;(void)c;(void)clear;(void)set;return state_mask; }
static void init_triggers(struct psi_group *g,u64 t) { g->polling_next_update=t+g->trigger_min_period; }
static u64 update_averages(struct psi_group *g,u64 t) { (void)g;++averages;return t+2000000000ULL; }
static u64 update_triggers(struct psi_group *g,u64 t) { ++triggers;return t+g->trigger_min_period; }
'''.replace('typedef void (*work_func_t)(struct work_struct *);','struct work_struct;\ntypedef void (*work_func_t)(struct work_struct *);')
main=r'''
static void other_work(struct work_struct *w) { (void)w; }
static void reset(void)
{
    psi_system=(struct psi_group){.trigger_min_period=100000000,.avg_next_update=2000000000ULL};
    scheduled=modified=averages=triggers=collected=0;state_mask=0;delay=0;
    memset(cpu_times,0,sizeof(cpu_times));worker.last_func=psi_update_work;now=1000000000ULL;
}
int main(int argc,char **argv)
{
    (void)argv;
    if(argc==1) {
        reset();struct task_struct t={.pid=1,.psi_flags=TSK_RUNNING,.flags=PF_WQ_WORKER,.comm="kworker",.worker=&worker};
        psi_task_change(&t,TSK_RUNNING,0);
        assert(!scheduled && !modified && !t.psi_flags);
        reset();worker.last_func=other_work;t.psi_flags=TSK_RUNNING;
        psi_task_change(&t,TSK_RUNNING,0);assert(scheduled==1 && delay==PSI_FREQ);
        reset();t.flags=0;t.psi_flags=0;psi_task_change(&t,0,TSK_RUNNING);assert(scheduled==1);
        /* Real pressure can still activate polling during aggregator dequeue. */
        reset();t.flags=PF_WQ_WORKER;t.psi_flags=TSK_RUNNING;
        state_mask=psi_system.trigger_states=1U<<PSI_MEM_SOME;
        psi_task_change(&t,TSK_RUNNING,0);assert(modified==1 && delay==1 && psi_system.polling==1);
        reset();u32 changed;
        cpu_times[0][PSI_NONIDLE]=100000;cpu_times[0][PSI_MEM_SOME]=100000;
        collect_percpu_times(&psi_system,&changed);
        assert(psi_system.total[PSI_MEM_SOME]==100000);
        assert((changed&(1U<<PSI_MEM_SOME)) && !(changed&(1U<<PSI_NONIDLE)));
        cpu_times[0][PSI_NONIDLE]=4000000;
        collect_percpu_times(&psi_system,&changed);assert(changed&(1U<<PSI_NONIDLE));
        puts("PASS: aggregator sleep cannot restart its idle clock; genuine tasks/stalls can");
        puts("PASS: short stall samples retained without sub-tick self-activity requeue");
    } else {
        reset();psi_system.polling=1;psi_system.polling_until=2000000000ULL;
        psi_system.polling_next_update=900000000;psi_system.avg_next_update=900000000;
        psi_update_work(&psi_system.clock_work.work);
        assert(triggers==1 && averages==1 && modified==1 && delay==26);
        now+=104000000;psi_system.clock_work.pending=false;
        psi_update_work(&psi_system.clock_work.work);
        assert(triggers==2 && modified==2 && delay==26);
        now=2000000001ULL;psi_system.clock_work.pending=false;
        psi_update_work(&psi_system.clock_work.work);
        assert(!psi_system.polling && !psi_system.clock_work.pending && modified==2);
        reset();cpu_times[0][PSI_NONIDLE]=100000;
        psi_update_work(&psi_system.clock_work.work);assert(!modified && !scheduled);
        puts("PASS: idle polling advances deadlines instead of requeueing every tick");
        puts("PASS: monitor grace expiry stops polling and idle collection stops scheduling");
    }
}
'''
markers=['static void collect_percpu_times(','static void psi_update_work(struct work_struct *work)\n{','static struct psi_group *iterate_groups(','void psi_task_change(']
with tempfile.TemporaryDirectory(prefix='r8-psi-idle-') as tmp:
    c,exe=Path(tmp)/'idle.c',Path(tmp)/'idle'
    c.write_text(stub+function(wq,'work_func_t wq_worker_last_func(')+'\n'.join(function(source,m) for m in markers)+main)
    subprocess.run([os.environ.get('HOSTCC','cc'),'-std=gnu99','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=10)
    subprocess.run([str(exe),'polling'],check=True,timeout=10)
# Completing work must publish identity before clearing current_func.
completion=function(wq,'static void process_one_work(')
assert completion.index('worker->last_func = worker->current_func;')<completion.index('worker->current_func = NULL;')
