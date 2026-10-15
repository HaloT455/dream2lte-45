#!/usr/bin/env python3
"""Compile actual Exynos QoS resolver, OPP table and EnergyStep commit C."""
from pathlib import Path
import os
import subprocess
import tempfile

es=Path(os.environ.get('ENERGYSTEP_TEST_SOURCE','kernel/sched/cpufreq_energy_step.c')).read_text()
driver=Path('drivers/cpufreq/exynos-acme.c').read_text()
table=Path('drivers/cpufreq/freq_table.c').read_text()
def fn(s,marker):
    a=s.index(marker); b=s.index('{',a); depth=1; c=b+1
    while depth:
        depth+=(s[c]=='{')-(s[c]=='}'); c+=1
    return s[a:c]+'\n'
stub=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
typedef uint64_t u64;
typedef int64_t s64;
#define CONFIG_ARM_EXYNOS_ACME 1
#define unlikely(x) (x)
#define READ_ONCE(x) (x)
#define clamp(v,lo,hi) ((v)<(lo)?(lo):((v)>(hi)?(hi):(v)))
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define div64_u64(a,b) ((a)/(b))
#define SCHED_CAPACITY_SCALE 1024
#define CPUFREQ_RELATION_L 0
#define CPUFREQ_RELATION_H 1
#define CPUFREQ_RELATION_C 2
#define CPUFREQ_ENTRY_INVALID (~0U-1)
#define CPUFREQ_TABLE_END (~0U)
#define pr_debug(...) ((void)0)
#undef abs
#define abs(x) ({int v=(int)(x);v<0?-v:v;})
#define cpufreq_for_each_valid_entry(p,t) for((p)=(t);(p)->frequency!=CPUFREQ_TABLE_END;++(p)) if((p)->frequency!=CPUFREQ_ENTRY_INVALID)
struct cpufreq_frequency_table {unsigned int flags,driver_data,frequency;};
struct cpufreq_policy {
 unsigned int cpu,min,max,cur; bool fast_switch_enabled;
 struct {unsigned int max_freq;} cpuinfo;
 struct cpufreq_frequency_table *freq_table;
};
struct exynos_cpufreq_domain {int pm_qos_min_class,pm_qos_max_class;};
struct irq_work {int dummy;};
struct esgov_policy {
 struct cpufreq_policy *policy;
 unsigned int cached_raw_freq,next_freq;
 bool need_freq_update,stopping,work_in_progress;
 u64 last_freq_update_time;
 s64 up_rate_delay_ns,down_rate_delay_ns;
 struct irq_work irq_work;
};
static struct exynos_cpufreq_domain domain={0,1};
static int qos[2]={0,3000000};
static unsigned int capacity_margin=1152,queued;
static bool is_static;
static struct exynos_cpufreq_domain *find_domain(unsigned int cpu)
{return cpu==0?&domain:NULL;}
static bool static_governor(struct cpufreq_policy *p) {(void)p;return is_static;}
static int pm_qos_request(int id) {return qos[id];}
static bool arch_scale_freq_invariant(void) {return true;}
static unsigned int cpufreq_driver_resolve_freq(struct cpufreq_policy *p,unsigned int f)
{return clamp(f,p->min,p->max);}
static int smp_processor_id(void) {return 0;}
static void trace_cpu_frequency(unsigned int f,int cpu) {(void)f;(void)cpu;}
static unsigned int cpufreq_driver_fast_switch(struct cpufreq_policy *p,unsigned int f)
{(void)p;return f;}
static void irq_work_queue(struct irq_work *w) {(void)w;queued++;}
'''
main=r'''
int main(void)
{
 struct cpufreq_frequency_table t[]={{0,0,2002000},{0,0,1703000},
 {0,0,1456000},{0,0,1248000},{0,0,1053000},{0,0,832000},{0,0,455000},{0,0,CPUFREQ_TABLE_END}};
 struct cpufreq_policy p={.min=455000,.max=2002000,.cur=1456000,.cpuinfo={2002000},.freq_table=t};
 struct esgov_policy sg={.policy=&p,.next_freq=1456000,
 .up_rate_delay_ns=3000000,.down_rate_delay_ns=12000000};
 qos[1]=1456000;
 /* Different raw demands all map to the same effective cap. */
 for(unsigned int i=0;i<100;i++) {
   unsigned int u=800+(i%5)*50;
   unsigned int f=get_next_freq(&sg,u,1024);
   assert(f==1456000);
   esgov_update_commit(&sg,40000000ULL*(i+1),f);
   sg.work_in_progress=false;
 }
 assert(queued==0);
 puts("PASS: 100 above-cap demand samples cause zero redundant slow-worker enqueues");
 /* Identical raw utilization must react to both tightening and releasing QoS. */
 unsigned int f=get_next_freq(&sg,1024,1024);assert(f==1456000);sg.next_freq=f;
 qos[1]=3000000;f=get_next_freq(&sg,1024,1024);assert(f==2002000);sg.next_freq=f;
 qos[1]=1248000;f=get_next_freq(&sg,1024,1024);assert(f==1248000);sg.next_freq=f;
 qos[1]=3000000;qos[0]=1600000;f=get_next_freq(&sg,1,1024);assert(f==1703000);sg.next_freq=f;
 qos[0]=0;assert(get_next_freq(&sg,1,1024)==455000);
 puts("PASS: unchanged utilization reacts to QoS cap/floor release instead of reusing stale raw cache");
 qos[0]=1800000;p.max=1500000;assert(esgov_step_target(&p,2002000)==1456000);
 p.max=2002000;qos[0]=-1;assert(esgov_step_target(&p,832000)==832000);
 qos[0]=1600000;is_static=true;assert(esgov_step_target(&p,832000)==832000);
 puts("PASS: policy limits retain priority, invalid QoS fallback and static-governor behavior are preserved");
}
'''
code=stub
code+=fn(table,'int cpufreq_frequency_table_target(')
code+=fn(driver,'static unsigned int apply_pm_qos(')
code+=fn(driver,'unsigned int exynos_cpufreq_apply_qos(')
for marker in ['static bool esgov_up_down_rate_limit(', 'static void esgov_update_commit(',
               'static unsigned int esgov_step_target(', 'static unsigned int get_next_freq(']:
    code+=fn(es,marker)
code+=main
with tempfile.TemporaryDirectory(prefix='alice-r11-qos-') as tmp:
    c,e=Path(tmp)/'qos.c',Path(tmp)/'qos'
    c.write_text(code)
    subprocess.run([os.environ.get('HOSTCC','cc'),'-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(e)],check=True)
    subprocess.run([str(e)],check=True,timeout=5)
