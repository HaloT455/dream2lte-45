// SPDX-License-Identifier: GPL-2.0-only
/*
 * KernelSU built-in automatic LSM registration for Linux 4.4.
 *
 * The existing lsm_hooks_list.c hijacks the first LSM callback pointer
 * and may write to read-only memory.  Exynos8895 Linux 4.4 instead has
 * a mutable RCU-protected security_hook_heads list.  Register our own
 * callbacks at its HEAD, preserving the current manual-hook precedence
 * without overwriting SELinux/capability hook function pointers.
 *
 * Do not compile the manual security/security.c call sites alongside this
 * implementation: each KernelSU observer must run exactly once.
 *
 * This is an ALice Linux 4.4 adaptation. Not upstream KernelSU code.
 */

static int ksu_auto44_bprm_check(struct linux_binprm *bprm)
{
#ifdef CONFIG_KSU_FEATURE_SULOG
	ksu_sulog_emit_bprm((const char *)bprm->filename);
#endif
	return 0;
}

static int ksu_auto44_inode_rename(struct inode *old_dir,
				  struct dentry *old_dentry,
				  struct inode *new_dir,
				  struct dentry *new_dentry)
{
	ksu_rename_observer(old_dentry, new_dentry);
	return 0;
}

static int ksu_auto44_task_fix_setuid(struct cred *new, const struct cred *old,
				     int flags)
{
	if (flags == LSM_SETID_RES)
		ksu_handle_setresuid_cred(new, old);
	return 0;
}

static int ksu_auto44_file_permission(struct file *file, int mask)
{
#if !defined(CONFIG_KSU_TAMPER_SYSCALL_TABLE)
	if (unlikely(ksu_vfs_read_hook))
		ksu_install_rc_hook(file);
#endif
	return 0;
}

static int ksu_auto44_setprocattr(struct task_struct *p, char *name,
				 void *value, size_t size)
{
	ksu_hide_setprocattr_inline(name, value, size);
	return 0;
}

/*
 * Linux 4.4 has struct list_head entries in its LSM hook table and
 * LSM_HOOK_INIT, so this needs no write-protect bypass or hook hijacking.
 * It is intentionally not __initdata: hook nodes must remain allocated.
 */
static struct security_hook_list ksu_auto44_hooks[] = {
	LSM_HOOK_INIT(bprm_check_security, ksu_auto44_bprm_check),
	LSM_HOOK_INIT(inode_rename, ksu_auto44_inode_rename),
	LSM_HOOK_INIT(task_fix_setuid, ksu_auto44_task_fix_setuid),
	LSM_HOOK_INIT(file_permission, ksu_auto44_file_permission),
	LSM_HOOK_INIT(setprocattr, ksu_auto44_setprocattr),
};

/*
 * This boot-only VFS read observer must not run on every file permission
 * event forever.  Once ksud disables its boot VFS hook, unlink OUR list
 * entry using RCU, not another LSM's function pointer.
 */
#define KSU_AUTO44_FILE_PERMISSION_SLOT 3
static int ksu_auto44_release_vfs_hook(void *unused)
{
	struct security_hook_list *hook =
		&ksu_auto44_hooks[KSU_AUTO44_FILE_PERMISSION_SLOT];

	set_user_nice(current, 19);
	do {
		msleep(1000);
	} while (READ_ONCE(ksu_vfs_read_hook));

	/* Avoid racing a just-scheduled boot read callback. */
	msleep(1000);
	list_del_rcu(&hook->list);
	synchronize_rcu();
	pr_info("KernelSU: removed boot-only file_permission LSM callback\n");
	return 0;
}

static void __init ksu_core_init(void)
{
	struct task_struct *worker;
	unsigned int i;

	/*
	 * The legacy ALice manual hooks ran before call_int_hook().  Keep
	 * that ordering with list_add_rcu() at the head, not at the tail;
	 * later SELinux hooks still run unless a policy hook denies.
	 */
	for (i = 0; i < ARRAY_SIZE(ksu_auto44_hooks); i++)
		list_add_rcu(&ksu_auto44_hooks[i].list,
			     ksu_auto44_hooks[i].head);

	pr_info("KernelSU: registered %zu automatic Linux 4.4 LSM callbacks (no pointer hijack)\n",
		ARRAY_SIZE(ksu_auto44_hooks));

	worker = kthread_run(ksu_auto44_release_vfs_hook, NULL,
			     "ksu_lsm_vfs44");
	if (IS_ERR(worker))
		pr_warn("KernelSU: file_permission cleanup worker unavailable (%ld); hook stays active\n",
			PTR_ERR(worker));
}
