#!/usr/bin/env python3
"""Execute actual Mali load-bias, CL gating and sysfs store code on a host.

The frequency governor/clock driver are stubs; real Mali frame performance,
thermal locks and battery savings are not established by this test.
"""
from pathlib import Path
import os
import subprocess
import tempfile

base=Path('drivers/gpu/arm/b_r19p0/platform/exynos')
source=(base/'gpu_dvfs_governor.c').read_text()
sysfs=(base/'gpu_custom_interface.c').read_text()
def function(s,marker):
    start=s.index(marker);opening=s.index('{',start);depth,end=1,opening+1
    while depth:
        depth+=(s[end]=='{')-(s[end]=='}');end+=1
    return s[start:end]
stub=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <errno.h>
#include <stdlib.h>
#include <sys/types.h>
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define clamp(v,a,b) ((v)<(a)?(a):(v)>(b)?(b):(v))
#define CONFIG_MALI_SEC_CL_BOOST 1
#define CONFIG_CPU_THERMAL_IPA 1
#define DVFS_ASSERT assert
struct kobject { int unused; };
struct kobj_attribute { int unused; };
static int gpu_load_boost=-5,gpu_last_dvfs_load;
struct entry { int clock; };
struct exynos_context { int gpu_dvfs_spinlock,step,gpu_max_clock; bool cl_boost_disable; struct entry *table; };
struct kbase_device { void *platform_context;struct { struct { struct { bool is_full_compute_util; } metrics; } backend; } pm; };
static int governor_util,ipa_clock;
static void spin_lock_irqsave(int *p,unsigned long f) { (void)f;assert(!*p);*p=1; }
static void spin_unlock_irqrestore(int *p,unsigned long f) { (void)f;assert(*p);*p=0; }
static void gpu_dvfs_decide_next_governor(struct exynos_context *p) { assert(p->gpu_dvfs_spinlock); }
static void gpu_dvfs_get_next_level(struct exynos_context *p,int util)
{ assert(p->gpu_dvfs_spinlock);governor_util=util;p->step=util>=90?0:1; }
static int gpu_dvfs_get_level(int clock) { assert(clock==800);return 0; }
static void ipa_mali_dvfs_requested(unsigned int clock) { ipa_clock=clock; }
static int kstrtoint(const char *s,int base,int *v)
{ char *end;long n=strtol(s,&end,base);if(end==s||(*end && *end!='\n')||n>2147483647L||n<(-2147483647L-1))return -EINVAL;*v=n;return 0; }
'''
main=r'''
int main(void)
{
    assert(gpu_dvfs_get_load_boost()==-5);
    assert(gpu_dvfs_apply_load_boost(50)==48);
    assert(gpu_dvfs_apply_load_boost(80)==76);
    assert(gpu_dvfs_apply_load_boost(90)==89);
    assert(gpu_dvfs_apply_load_boost(95)==95);
    assert(gpu_dvfs_apply_load_boost(100)==100);
    for(int boost=-10;boost<=20;boost++) {
        assert(!gpu_dvfs_set_load_boost(boost));
        int last=-1;
        for(int load=0;load<=100;load++) {
            int effective=gpu_dvfs_apply_load_boost(load);
            assert(effective>=0 && effective<=100 && effective>=last);last=effective;
            if(boost<0)assert(effective<=load);
            if(boost>=0)assert(effective>=load);
        }
        assert(gpu_dvfs_apply_load_boost(-20)==0 && gpu_dvfs_apply_load_boost(200)==100);
    }
    assert(set_gpu_load_boost(NULL,NULL,"-5\n",3)==3);
    assert(set_gpu_load_boost(NULL,NULL,"21",2)==-EINVAL && gpu_dvfs_get_load_boost()==-5);
    assert(set_gpu_load_boost(NULL,NULL,"-11",3)==-EINVAL && gpu_dvfs_get_load_boost()==-5);
    assert(set_gpu_load_boost(NULL,NULL,"bad",3)==-EINVAL && gpu_dvfs_get_load_boost()==-5);
    struct entry table[]={{800},{400}};
    struct exynos_context p={.table=table,.gpu_max_clock=800};
    struct kbase_device d={.platform_context=&p};
    d.pm.backend.metrics.is_full_compute_util=true;
    assert(gpu_dvfs_decide_next_freq(&d,50)==400 && governor_util==48 && ipa_clock==400);
    assert(gpu_dvfs_get_effective_load()==48 && !p.gpu_dvfs_spinlock);
    assert(gpu_dvfs_decide_next_freq(&d,100)==800 && governor_util==100 && ipa_clock==800);
    assert(gpu_dvfs_get_effective_load()==100 && !p.gpu_dvfs_spinlock);
    assert(!gpu_dvfs_set_load_boost(20));
    assert(gpu_dvfs_decide_next_freq(&d,80)==800 && governor_util==96);
    puts("PASS: GPU bias range, monotonic load, saturated-load recovery and invalid-write preservation");
    puts("PASS: real governor receives adjusted load; light compute does not force maximum");
    puts("PASS: selected clock is captured under DVFS lock and passed consistently to IPA");
}
'''
parts=[function(source,m) for m in ['int gpu_dvfs_get_load_boost(', 'int gpu_dvfs_set_load_boost(',
    'int gpu_dvfs_get_effective_load(', 'static int gpu_dvfs_apply_load_boost(', 'int gpu_dvfs_decide_next_freq(']]
parts.append(function(sysfs,'static ssize_t set_gpu_load_boost('))
# The real implementation initializes irq-save flags through the macro.
stub=stub.replace('static void spin_lock_irqsave(int *p,unsigned long f)', 'static void lock_irqsave(int *p,unsigned long f)')
stub+='\n#define spin_lock_irqsave(p,f) do { (f)=0;lock_irqsave(p,f); } while(0)\n'
with tempfile.TemporaryDirectory(prefix='r8-gpu-') as tmp:
    c,exe=Path(tmp)/'gpu.c',Path(tmp)/'gpu';c.write_text(stub+'\n'.join(parts)+main)
    subprocess.run([os.environ.get('HOSTCC','cc'),'-std=gnu99','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=10)
assert '__ATTR(gpu_boost, S_IRUGO|S_IWUSR' in sysfs
assert '&gpu_load_boost_attribute.attr' in sysfs
assert '&gpu_effective_load_attribute.attr' in sysfs
assert 'platform->env_data.utilization =' not in function(source,'int gpu_dvfs_decide_next_freq(')
