#!/usr/bin/env python3
"""Exercise the actual sysfs store against a serialized, in-progress OFF switch.

The simulated conversion holds the same state mutex across list migration and
static-key publication. The test checks that a concurrent ON request is kept.
"""
from pathlib import Path
import os
import subprocess
import tempfile

s = Path("mm/vmscan.c").read_text()
begin = s.index("static ssize_t lru_gen_enabled_store(")
end = s.index("static struct kobj_attribute lru_gen_enabled_attr", begin)
store = s[begin:end]
stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include <sys/types.h>
#include <errno.h>
struct kobject { int dummy; };
struct kobj_attribute { int dummy; };
struct task { const char *comm; };
static struct task task={"test"};
#define current (&task)
static int task_pid_nr(struct task *p) { (void)p; return 2; }
static int task_ppid_nr(struct task *p) { (void)p; return 1; }
static pthread_mutex_t state_mutex=PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t ready=PTHREAD_COND_INITIALIZER;
static bool enabled=true;
static bool setter_entered, caller_returned;
static bool lru_gen_enabled(void) { return enabled; }
static int kstrtoint(const char *p, int base, int *out)
{ *out=(int)strtol(p,NULL,base); return 0; }
static void log_request(const char *fmt, const char *state, int pid, int ppid,
                        const char *comm, int value)
{ (void)fmt; (void)state; (void)pid; (void)ppid; (void)comm; (void)value; }
#define pr_info_ratelimited log_request
#define pr_info(...) do {} while (0)
static void lru_gen_set_state(bool target, bool main, bool swap)
{
    (void)main; (void)swap;
    pthread_mutex_lock(&gate);
    setter_entered=true;
    pthread_cond_broadcast(&ready);
    pthread_mutex_unlock(&gate);
    pthread_mutex_lock(&state_mutex);
    enabled=target;
    pthread_mutex_unlock(&state_mutex);
}
'''
main = r'''
static void *request_on(void *unused)
{
    (void)unused;
    assert(lru_gen_enabled_store(NULL,NULL,"1",1)==1);
    pthread_mutex_lock(&gate);
    caller_returned=true;
    pthread_cond_broadcast(&ready);
    pthread_mutex_unlock(&gate);
    return NULL;
}
int main(void)
{
    pthread_t caller;
    /* OFF migration started: key remains ON until conversion completes. */
    pthread_mutex_lock(&state_mutex);
    pthread_create(&caller,NULL,request_on,NULL);
    pthread_mutex_lock(&gate);
    while (!setter_entered && !caller_returned)
        pthread_cond_wait(&ready,&gate);
    pthread_mutex_unlock(&gate);
    /* Publish OFF; a waiting ON writer must now restore the state. */
    enabled=false;
    pthread_mutex_unlock(&state_mutex);
    pthread_join(caller,NULL);
    assert(enabled && setter_entered);
    assert(lru_gen_enabled_store(NULL,NULL,"0",1)==1 && !enabled);
    assert(lru_gen_enabled_store(NULL,NULL,"2",1)==-EINVAL && !enabled);
    puts("PASS: ON during OFF conversion is not lost; OFF and invalid input handled");
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="mglru-store-") as tmp:
    c = Path(tmp) / "store.c"
    exe = Path(tmp) / "store"
    c.write_text(stub + store + main)
    subprocess.run([os.environ.get("HOSTCC", "cc"), "-std=gnu99", "-Wall",
                    "-Wextra", "-Werror", "-Wno-unused-parameter", "-pthread",
                    str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)
