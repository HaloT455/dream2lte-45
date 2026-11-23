#!/usr/bin/env python3
"""Compile and execute ALice's real KernelSU 4.4 auto-LSM callback code.

The host harness checks that exactly five hooks register in the kernel's
LSM list, and each KernelSU observer runs once without replacing SELinux
function pointers.  This is not a hardware boot or SELinux policy test.
"""
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SECURITY = (ROOT / "security/security.c").read_text()
KSU = (ROOT / "drivers/kernelsu/ksu.c").read_text()
CONFIG = (ROOT / "arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
AUTO = (ROOT / "drivers/kernelsu/hook/lsm_hooks_register_44.c").read_text()
LSM = (ROOT / "include/linux/lsm_hooks.h").read_text()
BOARD = (ROOT / "arch/arm64/boot/dts/exynos/exynos8895-dream2lte_common.dtsi").read_text()

assert "CONFIG_KSU_LSM_SECURITY_HOOKS=y" in CONFIG
assert "# CONFIG_KSU_THRONE_TRACKER_ALWAYS_THREADED is not set" in CONFIG
assert SECURITY.count("#if defined(CONFIG_KSU) && !defined(CONFIG_KSU_LSM_SECURITY_HOOKS)") == 6
assert SECURITY.count("#ifdef CONFIG_KSU") == 0
assert 'include "hook/lsm_hooks_register_44.c"' in KSU
assert "KERNEL_VERSION(4, 5, 0)" in KSU
assert "struct list_head" in LSM
assert "list_add_rcu" in AUTO
assert "ksu_write_to_readonly_slot" not in AUTO
assert "ksu_hack_lsm_slot" not in AUTO
assert "max-freq = <2002000>;" in BOARD
assert "max-freq = <2704000>;" in BOARD
assert len(re.findall(r"LSM_HOOK_INIT\(", AUTO)) == 5

SOURCE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define __init
#define CONFIG_KSU_FEATURE_SULOG 1
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define LSM_SETID_RES 1
#define unlikely(x) (x)
#define pr_info(...) ((void)0)
struct linux_binprm { const char *filename; };
struct inode { int id; };
struct dentry { int id; };
struct cred { int id; };
struct file { int id; };
struct task_struct { int id; };
struct list_head { struct list_head *prev, *next; };
struct security_hook_heads {
    struct list_head bprm_check_security, inode_rename, task_fix_setuid;
    struct list_head file_permission, setprocattr;
};
static struct security_hook_heads security_hook_heads;
union security_list_options {
    int (*bprm_check_security)(struct linux_binprm *);
    int (*inode_rename)(struct inode *, struct dentry *, struct inode *, struct dentry *);
    int (*task_fix_setuid)(struct cred *, const struct cred *, int);
    int (*file_permission)(struct file *, int);
    int (*setprocattr)(struct task_struct *, char *, void *, size_t);
};
struct security_hook_list {
    struct list_head list, *head;
    union security_list_options hook;
};
#define LSM_HOOK_INIT(name, fn) { .head = &security_hook_heads.name, .hook = { .name = (fn) } }
static unsigned int added, logged, renamed, setuid, readhook, procattr;
static bool ksu_vfs_read_hook;
static void ksu_sulog_emit_bprm(const char *name) {
    assert(name && name[0]); logged++;
}
static void ksu_rename_observer(struct dentry *old, struct dentry *new) {
    assert(old && new); renamed++;
}
static void ksu_handle_setresuid_cred(struct cred *new, const struct cred *old) {
    assert(new && old); setuid++;
}
static void ksu_install_rc_hook(struct file *file) {
    assert(file); readhook++;
}
static int ksu_hide_setprocattr_inline(const char *name, void *val, size_t size) {
    assert(name && val && size); procattr++;
    return 0;
}
static void init_head(struct list_head *head) {
    head->next = head->prev = head;
}
static void list_add_rcu(struct list_head *node, struct list_head *head) {
    node->next = head->next;
    node->prev = head;
    head->next->prev = node;
    head->next = node;
    added++;
}
#include "drivers/kernelsu/hook/lsm_hooks_register_44.c"
int main(void) {
    struct linux_binprm bin = {"ksud"};
    struct dentry a = {1}, b = {2};
    struct inode in = {1};
    struct cred cr = {1};
    struct file fi = {1};
    struct task_struct task = {1};
    char attr[] = "current";
    char value[] = "u:r:su:s0";
    struct list_head *heads[] = {
        &security_hook_heads.bprm_check_security,
        &security_hook_heads.inode_rename,
        &security_hook_heads.task_fix_setuid,
        &security_hook_heads.file_permission,
        &security_hook_heads.setprocattr,
    };
    unsigned int i;
    for (i = 0; i < ARRAY_SIZE(heads); i++) init_head(heads[i]);
    ksu_core_init();
    assert(added == 5);
    for (i = 0; i < ARRAY_SIZE(heads); i++) {
        assert(heads[i]->next != heads[i]);
        assert(heads[i]->next->next == heads[i]);
    }
    assert(ksu_auto44_hooks[0].hook.bprm_check_security(&bin) == 0);
    assert(ksu_auto44_hooks[1].hook.inode_rename(&in, &a, &in, &b) == 0);
    assert(ksu_auto44_hooks[2].hook.task_fix_setuid(&cr, &cr, LSM_SETID_RES) == 0);
    assert(ksu_auto44_hooks[2].hook.task_fix_setuid(&cr, &cr, 0) == 0);
    assert(ksu_auto44_hooks[3].hook.file_permission(&fi, 4) == 0);
    ksu_vfs_read_hook = true;
    assert(ksu_auto44_hooks[3].hook.file_permission(&fi, 4) == 0);
    assert(ksu_auto44_hooks[4].hook.setprocattr(&task, attr, value, sizeof(value)) == 0);
    assert(logged == 1 && renamed == 1 && setuid == 1);
    assert(readhook == 1 && procattr == 1);
    puts("PASS: 5 native KernelSU auto LSM callbacks; one observer each; no hijack");
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="alice-ksu-lsm44-") as tmp:
    src = Path(tmp) / "auto_hook_test.c"
    exe = Path(tmp) / "auto_hook_test"
    src.write_text(SOURCE)
    subprocess.run(shlex.split(os.getenv("HOSTCC", "cc")) + [
        "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-parameter",
        "-iquote" + str(ROOT), str(src), "-o", str(exe)
    ], check=True)
    subprocess.run([str(exe)], check=True)
print("PASS: KernelSU auto LSM source/defconfig/transport/OC guards validated")
