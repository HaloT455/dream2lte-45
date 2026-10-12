/* SPDX-License-Identifier: GPL-2.0
 *
 * ALICE bridge for kernel MM -> Android userspace.
 * Read-only instrumentation only: no clocks, SELinux, thermal, GPU masks,
 * MGLRU switches or memory-reclaim operations are accessible here.
 */
#include <linux/init.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/kernel.h>
#include <linux/mm.h>
#include <linux/swap.h>
#include <linux/atomic.h>
#include <linux/timekeeping.h>
#include <linux/alice_sysintel.h>

static atomic64_t alice_scanned = ATOMIC64_INIT(0);
static atomic64_t alice_reclaimed = ATOMIC64_INIT(0);
static atomic64_t alice_stalls = ATOMIC64_INIT(0);
static atomic64_t alice_backoffs = ATOMIC64_INIT(0);
static struct kobject *alice_kobj;

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

static ssize_t version_show(struct kobject *kobj,
			    struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE, "V12R60 kernel bridge v1\n");
}

static ssize_t safety_show(struct kobject *kobj,
			   struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE,
		"observe_only=1 mglru_offload=0 root_tuning=0 gpu_compute=external vpu=external\n");
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
	struct sysinfo info;
	struct sysinfo swap;

	si_meminfo(&info);
	si_swapinfo(&swap);
	return scnprintf(buf, PAGE_SIZE,
		"total_pages=%lu free_pages=%lu bufferram_pages=%lu swap_total_pages=%lu swap_free_pages=%lu\n",
		info.totalram, info.freeram, info.bufferram,
		swap.totalswap, swap.freeswap);
}

static struct kobj_attribute version_attr = __ATTR_RO(version);
static struct kobj_attribute safety_attr = __ATTR_RO(safety);
static struct kobj_attribute mm_reclaim_attr = __ATTR_RO(mm_reclaim);
static struct kobj_attribute memory_attr = __ATTR_RO(memory);

static struct attribute *alice_attrs[] = {
	&version_attr.attr,
	&safety_attr.attr,
	&mm_reclaim_attr.attr,
	&memory_attr.attr,
	NULL,
};

static const struct attribute_group alice_attr_group = {
	.attrs = alice_attrs,
};

static int __init alice_sysintel_init(void)
{
	int err;

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
