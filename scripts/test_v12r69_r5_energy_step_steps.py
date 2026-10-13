#!/usr/bin/env python3
"""Compile actual governor/table C: avoid extra rounding and artificial DL load."""
from pathlib import Path
import os
import subprocess
import tempfile

es = Path(os.environ.get('ENERGYSTEP_TEST_SOURCE', 'kernel/sched/cpufreq_energy_step.c')).read_text()
ft = Path('drivers/cpufreq/freq_table.c').read_text()
def function(source, marker):
    start=source.index(marker); opening=source.index('{',start); depth,end=1,opening+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}'); end+=1
    return source[start:end]
stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
typedef uint64_t u64;
typedef int64_t s64;
#define unlikely(x) (x)
#define clamp(v,lo,hi) ((v)<(lo)?(lo):((v)>(hi)?(hi):(v)))
#define div64_u64(a,b) ((a)/(b))
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define DIV_ROUND_UP(a,b) (((a)+(b)-1)/(b))
#define pr_debug(...) ((void)0)
#undef abs
#define abs(x) ({ int value=(int)(x); value<0?-value:value; })
#define CPUFREQ_RELATION_L 0
#define CPUFREQ_RELATION_H 1
#define CPUFREQ_RELATION_C 2
#define CPUFREQ_ENTRY_INVALID (~0U-1)
#define CPUFREQ_TABLE_END (~0U)
#define SCHED_CPUFREQ_DL 2U
#define cpufreq_for_each_valid_entry(p,t) for((p)=(t); (p)->frequency!=CPUFREQ_TABLE_END; ++(p)) if((p)->frequency!=CPUFREQ_ENTRY_INVALID)
#define for_each_cpu(j,cpus) for((j)=0; (j)<(cpus); ++(j))
#define per_cpu(array,j) ((array)[j])
struct cpufreq_frequency_table { unsigned int flags,driver_data,frequency; };
struct cpufreq_policy { unsigned int cpu,min,max,cur,cpus; struct { unsigned int max_freq; } cpuinfo; struct cpufreq_frequency_table *freq_table; };
struct esgov_policy { struct cpufreq_policy *policy; unsigned int cached_raw_freq,next_freq; bool need_freq_update; };
struct esgov_cpu { struct esgov_policy *sg_policy; unsigned long util,max; unsigned int flags,iowait_boost; bool iowait_boost_pending; u64 last_update; };
static struct esgov_cpu esgov_cpu[4];
static unsigned int stale_ns=20000000;
static bool invariant=true;
static bool arch_scale_freq_invariant(void) { return invariant; }
/* Exynos legacy .target makes resolve_freq return the unquantized request. */
static unsigned int cpufreq_driver_resolve_freq(struct cpufreq_policy *p,unsigned int f)
{ return clamp(f,p->min,p->max); }
static void esgov_iowait_boost(struct esgov_cpu *cpu,unsigned long *u,unsigned long *m)
{ (void)cpu; (void)u; (void)m; }
'''
main=r'''
int main(void)
{
    struct cpufreq_frequency_table table[]={
      {0,0,2002000},{0,0,455000},{0,0,CPUFREQ_ENTRY_INVALID},{0,0,624000},
      {0,0,832000},{0,0,1053000},{0,0,1248000},{0,0,1456000},
      {0,0,1703000},{0,0,CPUFREQ_TABLE_END}};
    struct cpufreq_policy p={.min=455000,.max=2002000,.cur=832000,.cpus=4,
                            .cpuinfo={2002000},.freq_table=table};
    struct esgov_policy sg={.policy=&p};
    assert(esgov_step_target(&p,624000)==624000);
    assert(esgov_step_target(&p,624001)==832000);
    assert(esgov_step_target(&p,500000)==624000);
    for(unsigned int requested=0;requested<2400000;requested+=791) {
        unsigned int bounded=clamp(requested,p.min,p.max),expected=~0U;
        for(unsigned int i=0;i<9;i++) {
            unsigned int f=table[i].frequency;
            if(f>=bounded && f<=p.max && f>=p.min && f<expected) expected=f;
        }
        assert(esgov_step_target(&p,requested)==expected);
    }
    /* Thermal/QoS max between hardware steps: never choose the next higher OPP. */
    p.max=1600000; assert(esgov_step_target(&p,2002000)==1456000);
    p.min=700000; assert(esgov_step_target(&p,0)==832000);
    p.min=p.max=832000; assert(esgov_step_target(&p,2002000)==832000);
    p.min=455000; p.max=2002000;
    for(unsigned long u=0;u<=1024;u++) {
        sg.need_freq_update=true;
        unsigned int f=get_next_freq(&sg,u,1024);
        assert(f>=p.min && f<=p.max);
        assert(f==esgov_step_target(&p,(unsigned int)((u64)(2002000+(2002000>>3))*u/1024)));
        sg.next_freq=f;
        assert(get_next_freq(&sg,u,1024)==f);
    }
    assert(get_next_freq(&sg,1,0)==p.min);
    invariant=false; sg.need_freq_update=true;
    assert(get_next_freq(&sg,1024,1024)==esgov_step_target(&p,936000));
    invariant=true;
    for(unsigned int i=0;i<4;i++) { esgov_cpu[i].sg_policy=&sg; esgov_cpu[i].flags=SCHED_CPUFREQ_DL; }
    esgov_cpu[0].max=1024; esgov_cpu[0].util=128; esgov_cpu[0].flags=0;
    esgov_cpu[0].last_update=1000000; sg.need_freq_update=true;
    /* Unsampled siblings (max=0) must neither force max nor erase current load. */
    assert(esgov_next_freq_shared(&esgov_cpu[0],1000000)==455000);
    p.max=1456000; esgov_cpu[1].max=1024; esgov_cpu[1].last_update=1000000;
    assert(esgov_next_freq_shared(&esgov_cpu[0],1000000)==1456000);
    esgov_cpu[1].last_update=0; sg.need_freq_update=true;
    esgov_cpu[0].last_update=30000000;
    assert(esgov_next_freq_shared(&esgov_cpu[0],30000000)==455000);
    p.freq_table=NULL; assert(esgov_step_target(&p,500000)==500000);
    puts("PASS: actual governor and cpufreq table helper select minimum sufficient hardware step");
    puts("PASS: thermal limits, cached target, invariant/noninvariant load and unsampled/stale sibling");
}
'''
code=stub
if '#define ALICE_ESGOV_STEPS\t8U' in es:
    code+='\n#define ALICE_ESGOV_STEPS 8U\n'
code+=function(ft,'int cpufreq_frequency_table_target(')
for marker in ('static unsigned int esgov_step_target(', 'static unsigned int get_next_freq(', 'static unsigned int esgov_next_freq_shared('):
    code+='\n'+function(es,marker)
code+=main
with tempfile.TemporaryDirectory(prefix='energy-step-r5-') as tmp:
    c,exe=Path(tmp)/'steps.c',Path(tmp)/'steps'
    c.write_text(code)
    subprocess.run([os.environ.get('HOSTCC','cc'),'-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=10)
