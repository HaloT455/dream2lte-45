/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _SCHED_CPU_UI_H
#define _SCHED_CPU_UI_H

struct task_group;
struct task_struct;

#ifdef CONFIG_SCHED_CPU_UI_HINTS
bool sched_cpu_ui_active(void);
void sched_cpu_ui_online(struct task_group *tg);
void sched_cpu_ui_released(struct task_group *tg);
int sched_cpu_ui_cpu_boost(int cpu);
int sched_cpu_ui_task_boost(struct task_struct *p);
int sched_cpu_ui_prefer_idle(struct task_struct *p);
int sched_cpu_ui_group_boost(struct task_group *tg);
int sched_cpu_ui_group_idle(struct task_group *tg);
#else
static inline bool sched_cpu_ui_active(void) { return false; }
static inline void sched_cpu_ui_online(struct task_group *tg) { }
static inline void sched_cpu_ui_released(struct task_group *tg) { }
static inline int sched_cpu_ui_cpu_boost(int cpu) { return 0; }
static inline int sched_cpu_ui_task_boost(struct task_struct *p) { return 0; }
static inline int sched_cpu_ui_prefer_idle(struct task_struct *p) { return 0; }
#endif

#endif
