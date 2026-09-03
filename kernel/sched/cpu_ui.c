// SPDX-License-Identifier: GPL-2.0
/* Android CPU-cgroup hints for ROMs which do not mount SchedTune. */
#include "sched.h"
#include "cpu_ui.h"

int sysctl_sched_cpu_ui_hints __read_mostly = 1;

static const struct {
	const char *name;
	int boost;
	int prefer_idle;
} cpu_ui_profiles[] = {
	{ "top-app", 10, 1 },
	{ "foreground", 5, 0 },
	{ "foreground_window", 5, 0 },
};

/* Writers hold cgroup_mutex; readers use RCU, including remote CPU readers. */
static struct task_group __rcu *cpu_ui_groups[ARRAY_SIZE(cpu_ui_profiles)];

bool sched_cpu_ui_active(void)
{
	/* Mounted SchedTune always wins, including an explicit zero boost. */
	return READ_ONCE(sysctl_sched_cpu_ui_hints) &&
		cgroup_subsys_on_dfl(schedtune_cgrp_subsys);
}

void sched_cpu_ui_online(struct task_group *tg)
{
	char name[32];
	unsigned int i;

	if (!tg->parent)
		return;

	/* Children inherit their root-level Android group's identity. */
	tg->ui_hint = tg->parent->ui_hint;
	if (tg->parent != &root_task_group)
		return;

	cgroup_name(tg->css.cgroup, name, sizeof(name));
	for (i = 0; i < ARRAY_SIZE(cpu_ui_profiles); i++) {
		if (strcmp(name, cpu_ui_profiles[i].name))
			continue;
		/* A rename must not replace a live group's identity. */
		if (rcu_access_pointer(cpu_ui_groups[i]))
			return;
		tg->ui_hint = i + 1;
		rcu_assign_pointer(cpu_ui_groups[i], tg);
		return;
	}
}

void sched_cpu_ui_released(struct task_group *tg)
{
	unsigned int hint = tg->ui_hint;

	if (hint && rcu_access_pointer(cpu_ui_groups[hint - 1]) == tg)
		RCU_INIT_POINTER(cpu_ui_groups[hint - 1], NULL);
	/* The cgroup core waits for RCU before freeing tg and its cfs_rqs. */
}

int sched_cpu_ui_group_boost(struct task_group *tg)
{
	return tg->ui_hint ? cpu_ui_profiles[tg->ui_hint - 1].boost : 0;
}

int sched_cpu_ui_group_idle(struct task_group *tg)
{
	return tg->ui_hint ? cpu_ui_profiles[tg->ui_hint - 1].prefer_idle : 0;
}

int sched_cpu_ui_task_boost(struct task_struct *p)
{
	struct task_group *tg;
	int boost;

	rcu_read_lock();
	tg = container_of(task_css(p, cpu_cgrp_id), struct task_group, css);
	boost = sched_cpu_ui_group_boost(tg);
	rcu_read_unlock();
	return boost;
}

int sched_cpu_ui_prefer_idle(struct task_struct *p)
{
	struct task_group *tg;
	int idle;

	rcu_read_lock();
	tg = container_of(task_css(p, cpu_cgrp_id), struct task_group, css);
	idle = sched_cpu_ui_group_idle(tg);
	rcu_read_unlock();
	return idle;
}

int sched_cpu_ui_cpu_boost(int cpu)
{
	struct task_group *tg;
	struct cfs_rq *cfs_rq;
	unsigned int i;
	int boost = 0;

	rcu_read_lock();
	for (i = 0; i < ARRAY_SIZE(cpu_ui_profiles); i++) {
		tg = rcu_dereference(cpu_ui_groups[i]);
		if (!tg)
			continue;
		cfs_rq = tg->cfs_rq[cpu];
#ifdef CONFIG_CFS_BANDWIDTH
		if (READ_ONCE(cfs_rq->throttle_count))
			continue;
#endif
		/*
		 * Reuse CFS accounting: includes runnable descendants, excludes
		 * sleeping tasks and throttled child queues. No extra per-task
		 * counter or exit/migration hook can get out of balance here.
		 * Remote queries are advisory snapshots, like CPU utilization.
		 */
		if (READ_ONCE(cfs_rq->h_nr_running))
			boost = max(boost, cpu_ui_profiles[i].boost);
	}
	rcu_read_unlock();
	return boost;
}
