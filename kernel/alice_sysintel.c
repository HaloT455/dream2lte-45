/* SPDX-License-Identifier: GPL-2.0
 * ALICE V12R68 research boot: built-in telemetry, bounded VM policy.
 * MGLRU defaults ON through CONFIG_LRU_GEN_ENABLED=y; sysfs still allows OFF.
 * No model weights/inference in kernel, no GPU/VPU reclaim offload.
 */
#include <linux/init.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/kernel.h>
#include <linux/mm.h>
#include <linux/swap.h>
#include <linux/atomic.h>
#include <linux/mutex.h>
#include <linux/alice_sysintel.h>

static atomic64_t alice_scanned = ATOMIC64_INIT(0);
static atomic64_t alice_reclaimed = ATOMIC64_INIT(0);
static atomic64_t alice_stalls = ATOMIC64_INIT(0);
static atomic64_t alice_backoffs = ATOMIC64_INIT(0);
static struct kobject *alice_kobj;

/* 0=balanced 1=performance 2=gaming 3=battery 4=stability 5=research */
static DEFINE_MUTEX(alice_policy_lock);
static int alice_mode = 4;  /* stability by default */
static bool alice_policy_enabled;
static int alice_saved_swappiness;
static int alice_applied_swappiness;

void alice_sysintel_reclaim(unsigned long scanned, unsigned long reclaimed)
{
	if (scanned)
		atomic64_add(scanned, &alice_scanned);
	if (reclaimed)
		atomic64_add(reclaimed, &alice_reclaimed);
}

void alice_sysintel_no_progress(bool backoff)
{
	atomic64_inc(&alice_stalls);
	if (backoff)
		atomic64_inc(&alice_backoffs);
}

/* Targets deliberately narrow. Mode 4/5 preserve original swappiness. */
static int alice_target_locked(void)
{
	switch (alice_mode) {
	case 1: return 140;
	case 2: return 150;
	case 3: return 160;
	case 0: return 160;
	default: return alice_saved_swappiness;
	}
}

/* Never override a setting modified independently by the ROM/sysctl. */
static int alice_apply_locked(void)
{
	int target = alice_target_locked();

	if (target < 100 || target > 180)
		return -ERANGE;
	if (READ_ONCE(vm_swappiness) != alice_applied_swappiness)
		return -EBUSY;
	WRITE_ONCE(vm_swappiness, target);
	alice_applied_swappiness = target;
	return 0;
}

static ssize_t version_show(struct kobject *kobj,
			    struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE, "V12R68 ALICE boot-kernel bridge v5 ENERGY-STEP-COMPAT MGLRU-ON RESEARCH\n");
}

static ssize_t safety_show(struct kobject *kobj,
			   struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE,
		"mglru_offload=0 mglru_auto_enable=0 gpu_vpu_inference=0 "
		"policy_requires_root=1 default_stability=1 cpu_clocks_unchanged=1 "
		"mglru_boot_default=1 mglru_auto_rollback=0 "
		"oneui_early_shell_off_bypass_once=1\n");
}

static ssize_t capabilities_show(struct kobject *kobj,
				 struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE,
		"kernel_telemetry=1 memory_assessment=heuristic "
		"manual_vm_policy=1 gpu_compute_partition_compiled=%d "
		"vpu_driver_compiled=%d model_inference=0 "
		"mglru_cpu_only=1 app_control=sysfs_root\n",
#ifdef CONFIG_MALI_HALO_NPU_PARTITION
		1,
#else
		0,
#endif
#ifdef CONFIG_EXYNOS_VPU
		1
#else
		0
#endif
	);
}

static ssize_t mm_reclaim_show(struct kobject *kobj,
			       struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE,
		"scanned=%lld reclaimed=%lld no_progress=%lld backoffs=%lld\n",
		(long long)atomic64_read(&alice_scanned),
		(long long)atomic64_read(&alice_reclaimed),
		(long long)atomic64_read(&alice_stalls),
		(long long)atomic64_read(&alice_backoffs));
}

static ssize_t memory_show(struct kobject *kobj,
			   struct kobj_attribute *attr, char *buf)
{
	struct sysinfo info, swap;

	si_meminfo(&info);
	si_swapinfo(&swap);
	return scnprintf(buf, PAGE_SIZE,
		"total_pages=%lu free_pages=%lu bufferram_pages=%lu "
		"swap_total_pages=%lu swap_free_pages=%lu\n",
		info.totalram, info.freeram, info.bufferram,
		swap.totalswap, swap.freeswap);
}

/* Transparent resource-pressure heuristic, NOT a trained AI model. */
static ssize_t assessment_show(struct kobject *kobj,
			       struct kobj_attribute *attr, char *buf)
{
	struct sysinfo info, swap;
	unsigned long free_pct, swap_used_pct;
	long long no_progress;
	const char *risk, *advice;
	int mode = READ_ONCE(alice_mode);

	si_meminfo(&info);
	si_swapinfo(&swap);
	free_pct = info.totalram ? (100UL * info.freeram / info.totalram) : 0;
	swap_used_pct = swap.totalswap ?
			100UL - 100UL * swap.freeswap / swap.totalswap : 0;
	no_progress = (long long)atomic64_read(&alice_stalls);
	if (free_pct < 4 && swap_used_pct >= 70) {
		risk = "high";
		advice = "inspect_psi_and_lmkd_logs";
	} else if (free_pct < 10 || swap_used_pct >= 50) {
		risk = "moderate";
		advice = "monitor_swap_and_app_pressure";
	} else {
		risk = "low";
		advice = "maintain_current_policy";
	}
	return scnprintf(buf, PAGE_SIZE,
		"risk=%s free_pct=%lu swap_used_pct=%lu mode=%d "
		"advice=%s mglru_stalls_total=%lld confidence=heuristic_only\n",
		risk, free_pct, swap_used_pct, mode, advice, no_progress);
}

static ssize_t mode_show(struct kobject *kobj,
			 struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE, "%d\n", READ_ONCE(alice_mode));
}

static ssize_t mode_store(struct kobject *kobj, struct kobj_attribute *attr,
			  const char *buf, size_t count)
{
	int mode, err;

	if (kstrtoint(buf, 10, &mode) || mode < 0 || mode > 5)
		return -EINVAL;
	mutex_lock(&alice_policy_lock);
	if (alice_policy_enabled) {
		/* The mode must not be updated if an active policy cannot apply. */
		int old_mode = alice_mode;
		alice_mode = mode;
		err = alice_apply_locked();
		if (err)
			alice_mode = old_mode;
	} else {
		WRITE_ONCE(alice_mode, mode);
		err = 0;
	}
	mutex_unlock(&alice_policy_lock);
	return err ? err : count;
}

static ssize_t policy_enabled_show(struct kobject *kobj,
				   struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE, "%d\n",
			 READ_ONCE(alice_policy_enabled) ? 1 : 0);
}

static ssize_t policy_enabled_store(struct kobject *kobj,
				    struct kobj_attribute *attr,
				    const char *buf, size_t count)
{
	int enable, err = 0;

	if (kstrtoint(buf, 10, &enable) || (enable != 0 && enable != 1))
		return -EINVAL;
	mutex_lock(&alice_policy_lock);
	if (enable && !alice_policy_enabled) {
		alice_saved_swappiness = READ_ONCE(vm_swappiness);
		alice_applied_swappiness = alice_saved_swappiness;
		/* Refuse changing a ROM-defined value outside conservative bounds. */
		if (alice_saved_swappiness < 100 ||
		    alice_saved_swappiness > 180)
			err = -ERANGE;
		else
			err = alice_apply_locked();
		if (!err)
			alice_policy_enabled = true;
	} else if (!enable && alice_policy_enabled) {
		if (READ_ONCE(vm_swappiness) == alice_applied_swappiness)
			WRITE_ONCE(vm_swappiness, alice_saved_swappiness);
		else
			err = -EBUSY;
		/* Always disarm even if another component changed the setting. */
		alice_policy_enabled = false;
	}
	mutex_unlock(&alice_policy_lock);
	return err ? err : count;
}

static ssize_t vm_policy_show(struct kobject *kobj,
			      struct kobj_attribute *attr, char *buf)
{
	int saved, applied, enabled, mode, current_swappiness;

	mutex_lock(&alice_policy_lock);
	saved = alice_saved_swappiness;
	applied = alice_applied_swappiness;
	mode = alice_mode;
	enabled = alice_policy_enabled;
	current_swappiness = READ_ONCE(vm_swappiness);
	mutex_unlock(&alice_policy_lock);
	return scnprintf(buf, PAGE_SIZE,
		"mode=%d enabled=%d current_swappiness=%d "
		"saved_swappiness=%d last_applied=%d "
		"mglru_automatic_enable=0 mglru_boot_default=1\n",
		mode, enabled, current_swappiness, saved, applied);
}

static struct kobj_attribute version_attr = __ATTR_RO(version);
static struct kobj_attribute safety_attr = __ATTR_RO(safety);
static struct kobj_attribute capabilities_attr = __ATTR_RO(capabilities);
static struct kobj_attribute mm_reclaim_attr = __ATTR_RO(mm_reclaim);
static struct kobj_attribute memory_attr = __ATTR_RO(memory);
static struct kobj_attribute assessment_attr = __ATTR_RO(assessment);
static struct kobj_attribute vm_policy_attr = __ATTR_RO(vm_policy);
static struct kobj_attribute mode_attr = __ATTR(mode, 0644, mode_show, mode_store);
static struct kobj_attribute policy_enabled_attr =
	__ATTR(policy_enabled, 0644,
	       policy_enabled_show, policy_enabled_store);

static struct attribute *alice_attrs[] = {
	&version_attr.attr, &safety_attr.attr, &capabilities_attr.attr,
	&mm_reclaim_attr.attr, &memory_attr.attr, &assessment_attr.attr,
	&vm_policy_attr.attr, &mode_attr.attr, &policy_enabled_attr.attr,
	NULL,
};

static const struct attribute_group alice_attr_group = {
	.attrs = alice_attrs,
};

static int __init alice_sysintel_init(void)
{
	int err;

	alice_saved_swappiness = READ_ONCE(vm_swappiness);
	alice_applied_swappiness = alice_saved_swappiness;
	alice_kobj = kobject_create_and_add("alice", kernel_kobj);
	if (!alice_kobj)
		return -ENOMEM;

	err = sysfs_create_group(alice_kobj, &alice_attr_group);
	if (err) {
		kobject_put(alice_kobj);
		alice_kobj = NULL;
	}
	return err;
}
subsys_initcall(alice_sysintel_init);
