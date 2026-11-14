/*
 * ALice S8+ non-invasive 80/20 reserve indicator (Exynos 8895).
 *
 * Copyright (C) 2026 ALice
 * SPDX-License-Identifier: GPL-2.0
 *
 * This does NOT alter the fuel gauge, battery reporting to Android,
 * Samsung thermal/current protection, or the AFC 5V/9V charging driver.
 * Samsung Ultra Power Saving Mode is controlled by Android/One UI;
 * this kernel module exposes a request and sends a transition uevent.
 */

#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/kobject.h>
#include <linux/spinlock.h>
#include <linux/sysfs.h>

#include <linux/alice_battery_reserve.h>

struct alice_reserve_snapshot {
	int real_percent;
	int normal_percent;
	int display_percent;
	bool charging;
	bool emergency;
	bool full_charge_seen;
	bool valid;
};

static struct alice_reserve_snapshot reserve_state;
static DEFINE_SPINLOCK(reserve_lock);
static struct kobject *reserve_kobj;

/*
 * Real 100% => virtual 100%.
 * Real 24% => virtual 5%, triggering emergency and displaying REAL 24%.
 * Below this threshold the display follows the real gauge (24 -> 0).
 *
 * Do not spoof /sys/class/power_supply/battery/capacity: Android and the
 * charging/safety stack must continue to see the actual SOC.
 */
static int alice_normal_percent(int real_percent)
{
	int remaining = clamp(real_percent, 0, 100) - 20;

	return clamp((max(remaining, 0) * 100 + 40) / 80, 0, 100);
}

void alice_battery_reserve_update(int actual, bool charging)
{
	unsigned long flags;
	int real = clamp(actual, 0, 100);
	int virtual = alice_normal_percent(real);
	bool changed;
	bool emergency;
	bool full_charge_seen;
	struct kobject *kobj;
	char *env_enter[] = {
		"ALICE_BATTERY_EMERGENCY=1",
		"ALICE_BATTERY_UPSM_REQUEST=1",
		"ALICE_BATTERY_UPSM_LOCKED=1",
		NULL
	};
	char *env_exit[] = {
		"ALICE_BATTERY_EMERGENCY=0",
		"ALICE_BATTERY_UPSM_REQUEST=0",
		"ALICE_BATTERY_UPSM_LOCKED=0",
		NULL
	};

	spin_lock_irqsave(&reserve_lock, flags);
	emergency = reserve_state.emergency;
	full_charge_seen = reserve_state.full_charge_seen;
	/*
	 * Reserve mode is released ONLY AFTER a genuine full charge AND
	 * removal of the charger. Some gauges drop to 99% on unplug, so
	 * use the latched "was full" event, not the unplugged SOC value.
	 */
	if (emergency) {
		if (charging && real >= 100)
			full_charge_seen = true;
		if (full_charge_seen && !charging) {
			emergency = false;
			full_charge_seen = false;
		}
	} else if (!charging && virtual <= 5) {
		emergency = true;
		full_charge_seen = false;
	}
	if (!emergency)
		full_charge_seen = false;

	changed = !reserve_state.valid ||
			(emergency != reserve_state.emergency);
	reserve_state.real_percent = real;
	reserve_state.normal_percent = virtual;
	reserve_state.display_percent = emergency ? real : virtual;
	reserve_state.charging = charging;
	reserve_state.emergency = emergency;
	reserve_state.full_charge_seen = full_charge_seen;
	reserve_state.valid = true;
	kobj = reserve_kobj;
	spin_unlock_irqrestore(&reserve_lock, flags);

	if (!kobj)
		return;

	sysfs_notify(kobj, NULL, "display_percent");
	if (changed) {
		sysfs_notify(kobj, NULL, "emergency_active");
		sysfs_notify(kobj, NULL, "upsm_requested");
		sysfs_notify(kobj, NULL, "upsm_locked");
		/* OneUI/vendor userspace must implement the real UPSM switch. */
		kobject_uevent_env(kobj, KOBJ_CHANGE,
				   emergency ? env_enter : env_exit);
	}
}

bool alice_battery_reserve_emergency(void)
{
	return READ_ONCE(reserve_state.emergency);
}

static struct alice_reserve_snapshot alice_read_snapshot(void)
{
	struct alice_reserve_snapshot copy;
	unsigned long flags;

	spin_lock_irqsave(&reserve_lock, flags);
	copy = reserve_state;
	spin_unlock_irqrestore(&reserve_lock, flags);
	return copy;
}

static ssize_t real_percent_show(struct kobject *kobj,
				 struct kobj_attribute *attr, char *buf)
{
	struct alice_reserve_snapshot s = alice_read_snapshot();

	return scnprintf(buf, PAGE_SIZE, "%d\n", s.valid ? s.real_percent : -1);
}

static ssize_t normal_percent_show(struct kobject *kobj,
				   struct kobj_attribute *attr, char *buf)
{
	struct alice_reserve_snapshot s = alice_read_snapshot();

	return scnprintf(buf, PAGE_SIZE, "%d\n", s.valid ? s.normal_percent : -1);
}

static ssize_t display_percent_show(struct kobject *kobj,
				    struct kobj_attribute *attr, char *buf)
{
	struct alice_reserve_snapshot s = alice_read_snapshot();

	return scnprintf(buf, PAGE_SIZE, "%d\n", s.valid ? s.display_percent : -1);
}

static ssize_t emergency_active_show(struct kobject *kobj,
				     struct kobj_attribute *attr, char *buf)
{
	struct alice_reserve_snapshot s = alice_read_snapshot();

	return scnprintf(buf, PAGE_SIZE, "%d\n", s.emergency ? 1 : 0);
}

static ssize_t upsm_requested_show(struct kobject *kobj,
				   struct kobj_attribute *attr, char *buf)
{
	struct alice_reserve_snapshot s = alice_read_snapshot();

	return scnprintf(buf, PAGE_SIZE, "%d\n", s.emergency ? 1 : 0);
}

/*
 * Read-only lock intended for Samsung's trusted UPSM/PowerManager bridge.
 * Kernel never writes the real battery capacity and never tries to invoke
 * proprietary Android services from atomic battery/driver contexts.
 */
static ssize_t upsm_locked_show(struct kobject *kobj,
				struct kobj_attribute *attr, char *buf)
{
	struct alice_reserve_snapshot s = alice_read_snapshot();

	return scnprintf(buf, PAGE_SIZE, "%d\n", s.emergency ? 1 : 0);
}

static ssize_t normal_unrestricted_show(struct kobject *kobj,
					struct kobj_attribute *attr, char *buf)
{
	struct alice_reserve_snapshot s = alice_read_snapshot();

	/* No additional CPU/GPU throttle is applied by this reserve monitor. */
	return scnprintf(buf, PAGE_SIZE, "%d\n", s.emergency ? 0 : 1);
}

static ssize_t full_charge_seen_show(struct kobject *kobj,
				     struct kobj_attribute *attr, char *buf)
{
	struct alice_reserve_snapshot s = alice_read_snapshot();

	return scnprintf(buf, PAGE_SIZE, "%d\n", s.full_charge_seen ? 1 : 0);
}

static ssize_t actual_charging_show(struct kobject *kobj,
				    struct kobj_attribute *attr, char *buf)
{
	struct alice_reserve_snapshot s = alice_read_snapshot();

	return scnprintf(buf, PAGE_SIZE, "%d\n", s.charging ? 1 : 0);
}

static struct kobj_attribute real_percent_attr = __ATTR_RO(real_percent);
static struct kobj_attribute normal_percent_attr = __ATTR_RO(normal_percent);
static struct kobj_attribute display_percent_attr = __ATTR_RO(display_percent);
static struct kobj_attribute emergency_active_attr = __ATTR_RO(emergency_active);
static struct kobj_attribute upsm_requested_attr = __ATTR_RO(upsm_requested);
static struct kobj_attribute actual_charging_attr = __ATTR_RO(actual_charging);
static struct kobj_attribute upsm_locked_attr = __ATTR_RO(upsm_locked);
static struct kobj_attribute normal_unrestricted_attr = __ATTR_RO(normal_unrestricted);
static struct kobj_attribute full_charge_seen_attr = __ATTR_RO(full_charge_seen);

static struct attribute *alice_reserve_attrs[] = {
	&real_percent_attr.attr,
	&normal_percent_attr.attr,
	&display_percent_attr.attr,
	&emergency_active_attr.attr,
	&upsm_requested_attr.attr,
	&upsm_locked_attr.attr,
	&normal_unrestricted_attr.attr,
	&full_charge_seen_attr.attr,
	&actual_charging_attr.attr,
	NULL
};

static const struct attribute_group alice_reserve_group = {
	.attrs = alice_reserve_attrs
};

static int __init alice_battery_reserve_init(void)
{
	int ret;

	reserve_kobj = kobject_create_and_add("alice_battery_reserve", kernel_kobj);
	if (!reserve_kobj)
		return -ENOMEM;
	ret = sysfs_create_group(reserve_kobj, &alice_reserve_group);
	if (ret) {
		kobject_put(reserve_kobj);
		reserve_kobj = NULL;
	}
	return ret;
}
subsys_initcall(alice_battery_reserve_init);
