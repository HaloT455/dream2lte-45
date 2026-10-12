#!/usr/bin/env python3
"""Compile real sysfs setters; assert a coherent locked policy update."""
from pathlib import Path
import os
import subprocess
import tempfile

s = Path(os.environ.get("ENERGYSTEP_TEST_SOURCE", "kernel/sched/cpufreq_energy_step.c")).read_text()
def function(marker):
    start=s.index(marker); opening=s.index("{",start); depth,end=1,opening+1
    while depth:
        depth+=(s[end]=="{")-(s[end]=="}"); end+=1
    return s[start:end]
stub = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <limits.h>
#include <sys/types.h>
typedef uint64_t u64;
#define NSEC_PER_USEC 1000ULL
struct esgov_policy { int update_lock; u64 up_rate_delay_ns,down_rate_delay_ns,min_rate_limit_ns; };
struct gov_attr_set { struct esgov_policy *policy_list; };
struct esgov_tunables { struct gov_attr_set attr_set; unsigned int up_rate_limit_us,down_rate_limit_us; };
static struct esgov_tunables tunables;
static struct esgov_policy policies[2];
static struct esgov_policy *current_policy;
static int min_rate_lock __attribute__((unused));
static void mutex_lock(int *l) { (void)l; }
static void mutex_unlock(int *l) { (void)l; }
#define list_for_each_entry(p,h,m) for ((p)=*(h),current_policy=(p); (p)<policies+2; ++(p),current_policy=(p))
#define raw_spin_lock_irqsave(l,f) do { assert(!*(l)); *(l)=1; (f)=0; } while(0)
#define raw_spin_unlock_irqrestore(l,f) do { (void)(f); assert(*(l)); *(l)=0; } while(0)
static u64 locked_min(u64 a,u64 b)
{
    /* A scheduler reader holding update_lock must not observe only the
     * directional delay changed while the aggregate gate is still old. */
    assert(current_policy->update_lock);
    return a<b?a:b;
}
#define min locked_min
static struct esgov_tunables *to_esgov_tunables(struct gov_attr_set *a)
{ assert(a==&tunables.attr_set); return &tunables; }
static int kstrtouint(const char *s,int base,unsigned int *out)
{ char *end; errno=0; unsigned long n=strtoul(s,&end,base);
  if (errno || n>UINT_MAX || end==s || (*end && *end!='\n') || *s=='-') return -EINVAL;
  *out=n; return 0; }
'''
main = r'''
int main(void)
{
    tunables.attr_set.policy_list=policies;
    policies[0].down_rate_delay_ns=12000000;
    policies[1].down_rate_delay_ns=5000000;
    assert(up_rate_limit_us_store(&tunables.attr_set,"3000",4)==4);
    for (int i=0;i<2;i++) assert(policies[i].up_rate_delay_ns==3000000 &&
        policies[i].min_rate_limit_ns==3000000 && !policies[i].update_lock);
    assert(down_rate_limit_us_store(&tunables.attr_set,"1000\n",5)==5);
    for (int i=0;i<2;i++) assert(policies[i].down_rate_delay_ns==1000000 &&
        policies[i].min_rate_limit_ns==1000000 && !policies[i].update_lock);
    assert(up_rate_limit_us_store(&tunables.attr_set,"4294967295",10)==10);
    assert(policies[0].up_rate_delay_ns==4294967295000ULL);
    assert(up_rate_limit_us_store(&tunables.attr_set,"-1",2)==-EINVAL);
    assert(down_rate_limit_us_store(&tunables.attr_set,"oops",4)==-EINVAL);
    assert(policies[0].down_rate_delay_ns==1000000);
    puts("PASS: directional and minimum rate limits update under the policy lock");
    puts("PASS: multiple policies, large values and invalid input handled");
}
'''
markers=("static void update_min_rate_limit_us(","static ssize_t up_rate_limit_us_store(",
         "static ssize_t down_rate_limit_us_store(")
with tempfile.TemporaryDirectory(prefix="energy-step-tunables-") as tmp:
    c,exe=Path(tmp)/"tunables.c",Path(tmp)/"tunables"
    c.write_text(stub+"\n".join(function(m) for m in markers)+main)
    subprocess.run([os.environ.get("HOSTCC","cc"),"-std=gnu99","-Wall","-Wextra",
                    "-Werror","-Wno-unused-function",str(c),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=10)
