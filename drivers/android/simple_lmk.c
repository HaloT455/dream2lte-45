// SPDX-License-Identifier: GPL-2.0
/*
 * Copyright (C) 2019-2023 Sultan Alsawaf <sultan@kerneltoast.com>.
 */

#define pr_fmt(fmt) "simple_lmk: " fmt

#include <linux/freezer.h>
#include <linux/kthread.h>
#include <linux/mm.h>
#include <linux/moduleparam.h>
#include <linux/oom.h>
#include <linux/ratelimit.h>
#include <linux/sort.h>
#include <linux/vmpressure.h>

#define MIN_FREE_PAGES \
	(CONFIG_ANDROID_SIMPLE_LMK_MINFREE * SZ_1M / PAGE_SIZE)
#define MAX_VICTIMS 1024
#define RECLAIM_EXPIRES \
	msecs_to_jiffies(CONFIG_ANDROID_SIMPLE_LMK_TIMEOUT_MSEC)

struct victim_info {
	struct task_struct *tsk;
	struct mm_struct *mm;
	unsigned long size;
};

static struct victim_info victims[MAX_VICTIMS] __cacheline_aligned_in_smp;
static struct task_struct *task_bucket[SHRT_MAX + 1] __cacheline_aligned;
static DECLARE_WAIT_QUEUE_HEAD(oom_waitq);
static DECLARE_COMPLETION(reclaim_done);
static __cacheline_aligned_in_smp DEFINE_RWLOCK(mm_free_lock);
static int nr_victims;
static atomic_t nr_killed = ATOMIC_INIT(0);
static atomic_t lmk_ready = ATOMIC_INIT(0);
static atomic_t init_done = ATOMIC_INIT(0);

/*
 * Android's lmkd detects an in-kernel LMK through the legacy minfree node
 * and always writes the matching adj array afterwards. SimpleLMK only needs
 * oom_score_adj from each task, but exposing the companion node keeps the
 * userspace handshake intact without enabling the legacy shrinker too.
 */
static short simple_lmk_adj[6];
static int simple_lmk_adj_size;

enum simple_lmk_reclaim_state {
	SIMPLE_LMK_IDLE,
	SIMPLE_LMK_QUEUED,
	SIMPLE_LMK_RUNNING,
};

static atomic_t reclaim_state = ATOMIC_INIT(SIMPLE_LMK_IDLE);

static int victim_cmp(const void *lhs_ptr, const void *rhs_ptr)
{
	const struct victim_info *lhs = (typeof(lhs))lhs_ptr;
	const struct victim_info *rhs = (typeof(rhs))rhs_ptr;

	if (lhs->size < rhs->size)
		return 1;
	if (lhs->size > rhs->size)
		return -1;
	return 0;
}

static void victim_swap(void *lhs_ptr, void *rhs_ptr, int size)
{
	struct victim_info *lhs = (typeof(lhs))lhs_ptr;
	struct victim_info *rhs = (typeof(rhs))rhs_ptr;

	swap(*lhs, *rhs);
}

static unsigned long get_total_mm_pages(struct mm_struct *mm)
{
	unsigned long pages = 0;
	int i;

	for (i = 0; i < NR_MM_COUNTERS; i++)
		pages += get_mm_counter(mm, i);

	return pages;
}

static unsigned long find_victims(int *vindex)
{
	short i, min_adj = SHRT_MAX, max_adj = 0;
	unsigned long pages_found = 0;
	struct task_struct *tsk;

	rcu_read_lock();
	for_each_process(tsk) {
		struct signal_struct *sig;
		short adj;

		sig = tsk->signal;
		adj = READ_ONCE(sig->oom_score_adj);
		if (adj < 0 ||
		    sig->flags & (SIGNAL_GROUP_EXIT | SIGNAL_GROUP_COREDUMP) ||
		    (thread_group_empty(tsk) && tsk->flags & PF_EXITING))
			continue;

		tsk->simple_lmk_next = task_bucket[adj];
		task_bucket[adj] = tsk;

		if (adj > max_adj)
			max_adj = adj;
		if (adj < min_adj)
			min_adj = adj;
	}

	for (i = max_adj; i >= min_adj; i--) {
		int old_vindex;

		tsk = task_bucket[i];
		if (!tsk)
			continue;

		task_bucket[i] = NULL;
		old_vindex = *vindex;
		do {
			struct task_struct *vtsk;

			vtsk = find_lock_task_mm(tsk);
			if (!vtsk)
				continue;

			victims[*vindex].tsk = vtsk;
			victims[*vindex].mm = vtsk->mm;
			victims[*vindex].size = get_total_mm_pages(vtsk->mm);
			pages_found += victims[*vindex].size;

			if (++*vindex == MAX_VICTIMS)
				break;
		} while ((tsk = tsk->simple_lmk_next));

		if (*vindex == old_vindex)
			continue;

		sort(&victims[old_vindex], *vindex - old_vindex,
		     sizeof(*victims), victim_cmp, victim_swap);

		if (*vindex == MAX_VICTIMS || pages_found >= MIN_FREE_PAGES) {
			if (i > min_adj)
				memset(&task_bucket[min_adj], 0,
				       (i - min_adj) * sizeof(*task_bucket));
			break;
		}
	}
	rcu_read_unlock();

	return pages_found;
}

static int process_victims(int vlen)
{
	unsigned long pages_found = 0;
	int i, nr_to_kill = 0;

	for (i = 0; i < vlen; i++) {
		struct victim_info *victim = &victims[i];
		struct task_struct *vtsk = victim->tsk;

		if (pages_found >= MIN_FREE_PAGES) {
			task_unlock(vtsk);
		} else {
			pages_found += victim->size;
			nr_to_kill++;
		}
	}

	return nr_to_kill;
}

static void scan_and_kill(void)
{
	int i, nr_to_kill, nr_found = 0;
	unsigned long pages_found;
	bool completed;

	/* Serialize TIF_MEMDIE accounting with regular and memcg OOM paths. */
	mutex_lock(&oom_lock);
	if (oom_killer_disabled) {
		mutex_unlock(&oom_lock);
		return;
	}

	pages_found = find_victims(&nr_found);
	if (unlikely(!nr_found)) {
		pr_err_ratelimited("No processes available to kill\n");
		mutex_unlock(&oom_lock);
		return;
	}

	if (pages_found > MIN_FREE_PAGES) {
		nr_to_kill = process_victims(nr_found);
		sort(victims, nr_to_kill, sizeof(*victims), victim_cmp,
		     victim_swap);
		nr_to_kill = process_victims(nr_to_kill);
	} else {
		nr_to_kill = nr_found;
	}

	write_lock(&mm_free_lock);
	nr_victims = nr_to_kill;
	write_unlock(&mm_free_lock);

	for (i = 0; i < nr_to_kill; i++) {
		static const struct sched_param min_rt_prio = {
			.sched_priority = 1
		};
		struct victim_info *victim = &victims[i];
		struct task_struct *t, *vtsk = victim->tsk;

		pr_info("Killing %s with adj %d to free %lu KiB\n", vtsk->comm,
			vtsk->signal->oom_score_adj,
			victim->size << (PAGE_SHIFT - 10));

		do_send_sig_info(SIGKILL, SEND_SIG_FORCED, vtsk, true);

		/*
		 * Account exactly one victim per process, as the regular OOM
		 * killer does. vtsk is task-locked with a live mm, so exit_mm()
		 * cannot race the mark and miss exit_oom_victim().
		 */
		mark_oom_victim(vtsk);

		rcu_read_lock();
		for_each_thread(vtsk, t)
			sched_setscheduler_nocheck(t, SCHED_RR, &min_rt_prio);
		rcu_read_unlock();

		set_cpus_allowed_ptr(vtsk, cpu_all_mask);
		__thaw_task(vtsk);
		task_unlock(vtsk);
	}
	mutex_unlock(&oom_lock);

	completed = wait_for_completion_timeout(&reclaim_done, RECLAIM_EXPIRES);
	if (!completed)
		pr_info("Timeout waiting for victims, continuing\n");

	write_lock(&mm_free_lock);
	reinit_completion(&reclaim_done);
	nr_victims = 0;
	atomic_set(&nr_killed, 0);
	write_unlock(&mm_free_lock);
}

static int simple_lmk_reclaim_thread(void *data)
{
	int old_state;

	/* Avoid starving Android's unlock path with a FIFO 99 process scan. */
	set_user_nice(current, -10);
	set_freezable();

	while (1) {
		if (wait_event_freezable(oom_waitq,
					 atomic_read(&reclaim_state) ==
					 SIMPLE_LMK_QUEUED))
			continue;

		old_state = atomic_cmpxchg_acquire(
			&reclaim_state, SIMPLE_LMK_QUEUED, SIMPLE_LMK_RUNNING);
		if (old_state != SIMPLE_LMK_QUEUED)
			continue;

		scan_and_kill();

		atomic_set_release(&reclaim_state, SIMPLE_LMK_IDLE);
	}

	return 0;
}

static bool simple_lmk_queue_reclaim(void)
{
	if (!atomic_read(&lmk_ready))
		return false;

	if (atomic_cmpxchg_acquire(&reclaim_state, SIMPLE_LMK_IDLE,
				   SIMPLE_LMK_QUEUED) != SIMPLE_LMK_IDLE)
		return false;

	wake_up(&oom_waitq);
	return true;
}

bool simple_lmk_oom_reclaim(void)
{
	if (!atomic_read_acquire(&lmk_ready))
		return false;

	/* A queued or running reclaim already represents OOM progress. */
	simple_lmk_queue_reclaim();
	return true;
}

void simple_lmk_mm_freed(struct mm_struct *mm)
{
	int i;

	if (!read_trylock(&mm_free_lock))
		return;

	for (i = 0; i < nr_victims; i++) {
		if (victims[i].mm == mm) {
			victims[i].mm = NULL;
			if (atomic_inc_return_relaxed(&nr_killed) == nr_victims)
				complete(&reclaim_done);
			break;
		}
	}
	read_unlock(&mm_free_lock);
}

static int simple_lmk_vmpressure_cb(struct notifier_block *nb,
				    unsigned long pressure, void *data)
{
	if (pressure >= 100)
		simple_lmk_queue_reclaim();

	return NOTIFY_OK;
}

static struct notifier_block vmpressure_notif = {
	.notifier_call = simple_lmk_vmpressure_cb,
	.priority = INT_MAX,
};

static int simple_lmk_start(void)
{
	struct task_struct *thread;
	int ret;

	if (atomic_cmpxchg(&init_done, 0, 1))
		return 0;

	ret = vmpressure_notifier_register(&vmpressure_notif);
	if (ret) {
		atomic_set(&init_done, 0);
		pr_err("Failed to register vmpressure notifier: %d\n", ret);
		return ret;
	}

	thread = kthread_run(simple_lmk_reclaim_thread, NULL, "simple_lmkd");
	if (IS_ERR(thread)) {
		vmpressure_notifier_unregister(&vmpressure_notif);
		atomic_set(&init_done, 0);
		pr_err("Failed to start reclaim thread: %ld\n",
		       PTR_ERR(thread));
		return PTR_ERR(thread);
	}

	atomic_set_release(&lmk_ready, 1);
	pr_info("Ready with global vmpressure and serialized reclaim\n");
	return 0;
}

static int simple_lmk_init_set(const char *val, const struct kernel_param *kp)
{
	/* Start only after Android configures lowmemorykiller.minfree. */
	simple_lmk_start();

	return 0;
}

static const struct kernel_param_ops simple_lmk_init_ops = {
	.set = simple_lmk_init_set
};

#undef MODULE_PARAM_PREFIX
#define MODULE_PARAM_PREFIX "lowmemorykiller."
module_param_cb(minfree, &simple_lmk_init_ops, NULL, 0200);
module_param_array_named(adj, simple_lmk_adj, short,
			 &simple_lmk_adj_size, 0200);
