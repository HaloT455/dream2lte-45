#include <linux/cred.h>
#include <linux/string.h>
#include <linux/susfs.h>
#include <linux/susfs_def.h>
#include <linux/uaccess.h>

/*
 * SUSFS userspace uses the legacy KernelSU prctl transport. KernelSU-Next
 * v3.3 uses an fd/ioctl transport, so keep the SUSFS ABI in a small adapter
 * instead of replacing the existing KernelSU implementation.
 */
long ksu_handle_susfs_prctl(unsigned long cmd, unsigned long arg3,
			    unsigned long arg5)
{
	void __user *data = (void __user *)arg3;
	int error = -1;
	u64 enabled_features = 0;

	if (current_uid().val != 0)
		goto out;

	switch (cmd) {
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
	case CMD_SUSFS_ADD_SUS_PATH:
		error = susfs_add_sus_path(data);
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
	case CMD_SUSFS_ADD_SUS_MOUNT:
		error = susfs_add_sus_mount(data);
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
	case CMD_SUSFS_ADD_SUS_KSTAT:
	case CMD_SUSFS_ADD_SUS_KSTAT_STATICALLY:
		error = susfs_add_sus_kstat(data);
		break;
	case CMD_SUSFS_UPDATE_SUS_KSTAT:
		error = susfs_update_sus_kstat(data);
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
	case CMD_SUSFS_SET_UNAME:
		error = susfs_set_uname(data);
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_ENABLE_LOG
	case CMD_SUSFS_ENABLE_LOG:
		if (arg3 <= 1) {
			susfs_set_log(arg3 != 0);
			error = 0;
		}
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
	case CMD_SUSFS_SET_CMDLINE_OR_BOOTCONFIG:
		error = susfs_set_cmdline_or_bootconfig(data);
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT
	case CMD_SUSFS_ADD_OPEN_REDIRECT:
		error = susfs_add_open_redirect(data);
		break;
#endif
	case CMD_SUSFS_SHOW_VERSION:
		error = copy_to_user(data, SUSFS_VERSION, sizeof(SUSFS_VERSION));
		break;
	case CMD_SUSFS_SHOW_VARIANT:
		error = copy_to_user(data, SUSFS_VARIANT, sizeof(SUSFS_VARIANT));
		break;
	case CMD_SUSFS_SHOW_ENABLED_FEATURES:
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
		enabled_features |= BIT_ULL(0);
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
		enabled_features |= BIT_ULL(1);
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
		enabled_features |= BIT_ULL(4);
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
		enabled_features |= BIT_ULL(8);
#endif
#ifdef CONFIG_KSU_SUSFS_ENABLE_LOG
		enabled_features |= BIT_ULL(9);
#endif
#ifdef CONFIG_KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS
		enabled_features |= BIT_ULL(10);
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
		enabled_features |= BIT_ULL(11);
#endif
#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT
		enabled_features |= BIT_ULL(12);
#endif
		error = copy_to_user(data, &enabled_features,
				     sizeof(enabled_features));
		break;
	default:
		break;
	}

out:
	if (arg5 && copy_to_user((void __user *)arg5, &error, sizeof(error)))
		return -EFAULT;
	return 0;
}
