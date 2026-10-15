// SPDX-License-Identifier: GPL-2.0
/* Bounded Power HAL hints. All frequency requests remain below native caps. */
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/mutex.h>
#include <linux/jiffies.h>
#include <linux/pm_qos.h>
#include <linux/thermal.h>
#include <linux/suspend.h>

#define ALICE_SESSIONS 16
#define ALICE_SLOTS (ALICE_SESSIONS + 2)
#define INTERACTION_SLOT ALICE_SESSIONS
#define LAUNCH_SLOT (ALICE_SESSIONS + 1)

struct alice_hint {
	unsigned long expires;
	unsigned int level;
};
static struct alice_hint hints[ALICE_SLOTS];
static DEFINE_MUTEX(hint_lock);
static struct pm_qos_request little_req, big_req;
static bool interactive = true, low_power, device_idle, display_inactive;
static unsigned int applied_level;
static unsigned long temperature_at;
static int temperature = -1;
static unsigned long commands, expirations;

static void alice_hint_work(struct work_struct *work);
static DECLARE_DELAYED_WORK(hint_work, alice_hint_work);

static int alice_hint_temperature(unsigned long now)
{
	struct thermal_zone_device *tz;
	int a, b;

	if (temperature_at && time_before(now, temperature_at + msecs_to_jiffies(200)))
		return temperature;
	temperature_at = now;
	temperature = -1;
	tz = thermal_zone_get_zone_by_name("mngs-thermal");
	if (IS_ERR(tz) || thermal_zone_get_temp(tz, &a))
		return temperature;
	tz = thermal_zone_get_zone_by_name("APOLLO");
	if (IS_ERR(tz) || thermal_zone_get_temp(tz, &b))
		return temperature;
	temperature = max(a, b);
	return temperature;
}

static void alice_hint_recompute(unsigned long now)
{
	/* Exact supported OPPs; no voltage, max-frequency or hotplug changes. */
	static const int little[] = { 0, 949000, 1053000, 1248000 };
	static const int big[] = { 0, 0, 1066000, 1261000 };
	unsigned long next = now + msecs_to_jiffies(200);
	unsigned int level = 0;
	int i, temp;
	bool pending = false;

	for (i = 0; i < ALICE_SLOTS; i++) {
		if (!hints[i].level)
			continue;
		if (time_after_eq(now, hints[i].expires)) {
			hints[i].level = 0;
			expirations++;
			continue;
		}
		level = max(level, hints[i].level);
		if (time_before(hints[i].expires, next))
			next = hints[i].expires;
		pending = true;
	}
	if (!interactive || device_idle || display_inactive)
		level = 0;
	if (low_power)
		level = min(level, 1U);
	if (level) {
		temp = alice_hint_temperature(now);
		/* Stop adding floors if sensors are unavailable or CPU is hot. */
		if (temp < 0 || temp >= 65000)
			level = 0;
		else if (temp >= 60000)
			level = min(level, 1U);
	}
	if (level != applied_level) {
		pm_qos_update_request(&little_req, little[level]);
		pm_qos_update_request(&big_req, big[level]);
		applied_level = level;
	}
	if (pending)
		mod_delayed_work(system_wq, &hint_work, max(1UL, next - now));
	else
		cancel_delayed_work(&hint_work);
}

static void alice_hint_work(struct work_struct *work)
{
	mutex_lock(&hint_lock);
	alice_hint_recompute(jiffies);
	mutex_unlock(&hint_lock);
}

static ssize_t alice_power_hint_show(struct kobject *kobj,
		struct kobj_attribute *attr, char *buf)
{
	ssize_t n;
	mutex_lock(&hint_lock);
	n = scnprintf(buf, PAGE_SIZE,
		"version=1 level=%u interactive=%d low_power=%d idle=%d "
		"display_inactive=%d temperature_mc=%d commands=%lu expirations=%lu\n",
		applied_level, interactive, low_power, device_idle,
		display_inactive, temperature, commands, expirations);
	mutex_unlock(&hint_lock);
	return n;
}

static ssize_t alice_power_hint_store(struct kobject *kobj,
		struct kobj_attribute *attr, const char *buf, size_t count)
{
	char op[16], tail;
	unsigned int id, value, ms;
	unsigned long now = jiffies;
	int ret = -EINVAL;

	mutex_lock(&hint_lock);
	if (sysfs_streq(buf, "reset")) {
		memset(hints, 0, sizeof(hints));
		interactive = true;
		low_power = device_idle = display_inactive = false;
		ret = 0;
	} else if (sscanf(buf, "%15s %u %u %u %c", op, &id, &value, &ms, &tail) == 4 &&
		   !strcmp(op, "session") && id < ALICE_SESSIONS && value <= 3 && ms <= 250) {
		hints[id].level = value;
		hints[id].expires = now + msecs_to_jiffies(ms);
		ret = 0;
	} else if (sscanf(buf, "%15s %u %u %c", op, &id, &value, &tail) == 3 &&
		   !strcmp(op, "mode") && value <= 1) {
		switch (id) {
		case 1: low_power = value; break;
		case 5:
			hints[LAUNCH_SLOT].level = value ? 3 : 0;
			hints[LAUNCH_SLOT].expires = now + msecs_to_jiffies(low_power ? 120 : 1000);
			break;
		case 7: interactive = value; break;
		case 8: device_idle = value; break;
		case 9: display_inactive = value; break;
		default: goto out;
		}
		if (!interactive || device_idle || display_inactive)
			memset(hints, 0, sizeof(hints));
		ret = 0;
	} else if (sscanf(buf, "%15s %u %u %c", op, &id, &ms, &tail) == 3 &&
		   !strcmp(op, "boost") && id <= 1 && ms <= 250) {
		hints[INTERACTION_SLOT].level = ms ? 2 : 0;
		hints[INTERACTION_SLOT].expires = now + msecs_to_jiffies(low_power ? min(ms, 120U) : ms);
		ret = 0;
	}
	if (!ret) {
		/* Hints arriving while asleep must not survive a screen-on event. */
		if (!interactive || device_idle || display_inactive)
			memset(hints, 0, sizeof(hints));
		commands++;
		alice_hint_recompute(now);
	}
out:
	mutex_unlock(&hint_lock);
	return ret ? ret : count;
}

static struct kobj_attribute hint_attr =
	__ATTR(alice_power_hint, 0600, alice_power_hint_show, alice_power_hint_store);

static int alice_hint_pm_notify(struct notifier_block *nb, unsigned long event, void *unused)
{
	if (event == PM_SUSPEND_PREPARE) {
		mutex_lock(&hint_lock);
		memset(hints, 0, sizeof(hints));
		alice_hint_recompute(jiffies);
		mutex_unlock(&hint_lock);
	}
	return NOTIFY_OK;
}
static struct notifier_block alice_hint_pm = { .notifier_call = alice_hint_pm_notify };

static int __init alice_power_hint_init(void)
{
	int ret;
	pm_qos_add_request(&little_req, PM_QOS_CLUSTER0_FREQ_MIN, 0);
	pm_qos_add_request(&big_req, PM_QOS_CLUSTER1_FREQ_MIN, 0);
	ret = sysfs_create_file(power_kobj, &hint_attr.attr);
	if (ret) {
		pm_qos_remove_request(&little_req);
		pm_qos_remove_request(&big_req);
		return ret;
	}
	register_pm_notifier(&alice_hint_pm);
	return 0;
}
late_initcall(alice_power_hint_init);
