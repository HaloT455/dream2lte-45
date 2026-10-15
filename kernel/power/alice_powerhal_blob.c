// SPDX-License-Identifier: GPL-2.0
/* Public-source service compiled in CI; never carries vendor/ROM bytes. */
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/string.h>
#include "alice_powerhal_blob.h"

static ssize_t alice_powerhal_read(struct file *file, struct kobject *kobj,
		struct bin_attribute *attr, char *buf, loff_t offset, size_t count)
{
	if (offset < 0)
		return -EINVAL;
	if (offset >= sizeof(alice_powerhal_elf))
		return 0;
	count = min_t(size_t, count, sizeof(alice_powerhal_elf) - offset);
	memcpy(buf, alice_powerhal_elf + offset, count);
	return count;
}
static struct bin_attribute blob_attr = {
	.attr = { .name = "alice_powerhal", .mode = 0400 },
	.size = sizeof(alice_powerhal_elf),
	.read = alice_powerhal_read,
};
static int __init alice_powerhal_blob_init(void)
{
	return sysfs_create_bin_file(kernel_kobj, &blob_attr);
}
late_initcall(alice_powerhal_blob_init);
