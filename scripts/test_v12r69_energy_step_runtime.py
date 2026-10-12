#!/usr/bin/env python3
"""Run actual governor worker/stop C functions with deterministic host interleavings.

The driver/queue stubs model pending work and cancellation. This catches lost
targets and work queued after the IRQ drain; it does not emulate Exynos hardware.
"""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path(os.environ.get("ENERGYSTEP_TEST_SOURCE", "kernel/sched/cpufreq_energy_step.c")).read_text()

def function(marker):
    begin = source.index(marker)
    opening = source.index("{", begin)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]

stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <pthread.h>
#include <string.h>
#define container_of(p,t,m) ((t *)((char *)(p) - offsetof(t,m)))
#define CPUFREQ_RELATION_L 0
#define raw_spin_lock_irqsave(l,f) do { (f)=0; pthread_mutex_lock(l); } while (0)
#define raw_spin_unlock_irqrestore(l,f) do { (void)(f); pthread_mutex_unlock(l); } while (0)
#define mutex_lock pthread_mutex_lock
#define mutex_unlock pthread_mutex_unlock
#define for_each_cpu(c,p) for ((c)=0; (c)<(p); (c)++)
struct kthread_work { int dummy; };
struct kthread_worker { int dummy; };
struct irq_work { int dummy; };
struct cpufreq_policy { bool fast_switch_enabled; unsigned int cpus; void *governor_data; };
struct esgov_policy {
    struct cpufreq_policy *policy;
    pthread_mutex_t update_lock, work_lock;
    unsigned int next_freq, cached_raw_freq;
    bool work_in_progress, stopping, need_freq_update;
    struct kthread_work work;
    struct kthread_worker worker;
    struct irq_work irq_work;
};
static struct esgov_policy sg;
static struct cpufreq_policy policy;
static pthread_t worker_thread;
static pthread_mutex_t gate = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t ready = PTHREAD_COND_INITIALIZER;
static int mode, calls, pending, irq_pending, entered, drain_done;
static bool irq_running, worker_running;
static unsigned int applied[4];
static bool queue_kthread_work(struct kthread_worker *w, struct kthread_work *k)
{
    (void)w; (void)k;
    /* A sleeping cpufreq worker may be woken here. The scheduler takes
     * rq->lock and can re-enter the governor, which needs update_lock.
     * Taking that lock models this nested scheduler/governor callback.
     */
    assert(pthread_mutex_trylock(&sg.update_lock) == 0);
    pthread_mutex_unlock(&sg.update_lock);
    if (mode==5) {
        pthread_mutex_lock(&gate);
        entered=1;
        pthread_cond_broadcast(&ready);
        while (!drain_done) pthread_cond_wait(&ready, &gate);
        pending=1;
        pthread_mutex_unlock(&gate);
        return true;
    }
    pending=1;
    return true;
}
static bool irq_work_queue(struct irq_work *i)
{ (void)i; irq_pending=1; return true; }
static void cpufreq_remove_update_util_hook(unsigned int cpu) { (void)cpu; }
static void synchronize_sched(void) {}
static void irq_work_sync(struct irq_work *i)
{
    (void)i;
    pthread_mutex_lock(&gate);
    irq_pending=0;
    drain_done=1;
    pthread_cond_broadcast(&ready);
    while (irq_running) pthread_cond_wait(&ready, &gate);
    pthread_mutex_unlock(&gate);
}
static void kthread_cancel_work_sync(struct kthread_work *k)
{ (void)k; if (worker_running) pthread_join(worker_thread, NULL); pending=0; }
static int __cpufreq_driver_target(struct cpufreq_policy *p, unsigned int f, int r)
{
    (void)p; (void)r;
    applied[calls++]=f;
    if (mode==4) return -5;
    if (mode==3) {
        pthread_mutex_lock(&gate);
        entered=1;
        pthread_cond_broadcast(&ready);
        while (!drain_done) pthread_cond_wait(&ready, &gate);
        pthread_mutex_unlock(&gate);
    }
    if (mode==2 || mode==3 || (mode==1 && calls==1)) {
        pthread_mutex_lock(&sg.update_lock);
        sg.next_freq += 100;
        pthread_mutex_unlock(&sg.update_lock);
    }
    return 0;
}
'''
main = r'''
static void reset(int scenario)
{
    mode=scenario;
    calls=pending=irq_pending=entered=drain_done=0;
    irq_running=worker_running=false;
    sg.next_freq=100;
    sg.work_in_progress=true;
    sg.stopping=false;
    sg.need_freq_update=false;
    sg.cached_raw_freq=123;
}
static void *run_worker(void *unused)
{ (void)unused; esgov_work(&sg.work); return NULL; }
static void *run_irq(void *unused)
{
    (void)unused;
    pthread_mutex_lock(&gate);
    irq_running=true;
    pthread_mutex_unlock(&gate);
    esgov_irq_work(&sg.irq_work);
    pthread_mutex_lock(&gate);
    irq_running=false;
    pthread_cond_broadcast(&ready);
    pthread_mutex_unlock(&gate);
    return NULL;
}
int main(int argc, char **argv)
{
    (void)argv;
    pthread_mutex_init(&sg.update_lock, NULL);
    pthread_mutex_init(&sg.work_lock, NULL);
    policy.governor_data=&sg;
    policy.cpus=1;
    sg.policy=&policy;
    if (argc==1) {
        reset(0); pending=0; esgov_irq_work(&sg.irq_work);
        assert(pending==1 && !sg.stopping);
        reset(0); esgov_work(&sg.work);
        assert(calls==1 && applied[0]==100 && !sg.work_in_progress);
        reset(1); esgov_work(&sg.work);
        assert(calls==2 && applied[1]==200 && !sg.work_in_progress);
        reset(2); esgov_work(&sg.work);
        assert(calls==2 && pending==1 && irq_pending==0 && sg.work_in_progress);
        mode=0; pending=0; esgov_work(&sg.work);
        assert(calls==3 && applied[2]==300 && !sg.work_in_progress);
        sg.stopping=true; pending=0; esgov_irq_work(&sg.irq_work);
        assert(pending==0);
        reset(4); esgov_work(&sg.work);
        assert(calls==1 && sg.need_freq_update && sg.next_freq==0);
        assert(sg.cached_raw_freq==0 && !sg.work_in_progress);
        assert(!pending && !irq_pending);
        puts("PASS: stable target, replay bound, latest target, IRQ stop gate");
        puts("PASS: driver rejection invalidates target/cache without busy replay");
        puts("PASS: IRQ enqueue and worker replay release policy lock before scheduler wakeup");
    } else if (!strcmp(argv[1], "irq-stop")) {
        pthread_t irq_thread;
        reset(5);
        pthread_create(&irq_thread, NULL, run_irq, NULL);
        pthread_mutex_lock(&gate);
        while (!entered) pthread_cond_wait(&ready, &gate);
        pthread_mutex_unlock(&gate);
        /* stop changes stopping after IRQ captured its queue decision,
         * then waits for that enqueue before cancelling pending work.
         */
        esgov_stop(&policy);
        pthread_join(irq_thread, NULL);
        assert(sg.stopping && !pending && !irq_running);
        puts("PASS: stop drains IRQ enqueue in flight before cancelling work");
    } else {
        reset(3);
        worker_running=true;
        pthread_create(&worker_thread, NULL, run_worker, NULL);
        pthread_mutex_lock(&gate);
        while (!entered) pthread_cond_wait(&ready, &gate);
        pthread_mutex_unlock(&gate);
        esgov_stop(&policy);
        assert(calls==1 && irq_pending==0 && pending==0 && !sg.work_in_progress);
        puts("PASS: stop during driver transition leaves no IRQ or worker pending");
    }
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="esgov-test-") as tmp:
    c = Path(tmp) / "worker.c"
    exe = Path(tmp) / "worker"
    c.write_text(stub + "\n" + "\n".join(function(marker) for marker in (
        "static void esgov_work(", "static void esgov_irq_work(",
        "static int esgov_stop(")) + "\n" + main)
    subprocess.run([os.environ.get("HOSTCC", "cc"), "-std=gnu99", "-Wall",
                    "-Wextra", "-Werror", "-Wno-unused-function", "-pthread",
                    str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)
    subprocess.run([str(exe), "stop"], check=True, timeout=10)
    subprocess.run([str(exe), "irq-stop"], check=True, timeout=10)
