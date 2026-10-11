#!/usr/bin/env python3
"""P30: eliminate demonstrated Linux 5.10 ACPM NULL dereference during fs_initcall.

Input: disposable Linux 5.10.262 source staged with pinned P16 Samsung
4.4 ACPM donor files. No bypass to permit ACPM access. If the DT/IPC/firmware
is not initialized, skip the ACPM plugin update and preserve safety gate.
"""
from pathlib import Path
import sys
if len(sys.argv) != 2:
    raise SystemExit("P30 usage: python3 research/k510/p30-stage-acpm-null-guard.py /linux510")
tree = Path(sys.argv[1])
acpm = tree / "drivers/soc/samsung/acpm/acpm.c"
ipc = tree / "drivers/soc/samsung/acpm/acpm_ipc.c"
header = tree / "drivers/soc/samsung/acpm/acpm_ipc.h"
for p in (acpm, ipc, header):
    if not p.is_file():
        raise SystemExit("P30 prerequisite missing: " + str(p))
a, i, h = (p.read_text() for p in (acpm, ipc, header))

def replace_once(s, old, new, target):
    if s.count(old) != 1:
        raise SystemExit("P30 REFUSED: donor source ABI changed: " + target)
    return s.replace(old, new, 1)

# Donor unconditional pointer write was the exact PC in P29 dmesg-ramoops:
# acpm_ipc_set_waiting_mode+0x10/0x20 -> null + 0x30 during fs_initcall_sync.
i = replace_once(i,
    '''static struct acpm_ipc_info *acpm_ipc;
''',
    '''static struct acpm_ipc_info *acpm_ipc;
/* Only set after successful IPC channel initialization, never by Kbuild. */
static bool acpm_ipc_initialized;

bool acpm_ipc_runtime_ready(void)
{
    return READ_ONCE(acpm_ipc_initialized);
}
''', "ACPM IPC global")
i = replace_once(i,
    '''void acpm_ipc_set_waiting_mode(bool mode)
{
\tacpm_ipc->w_mode = mode;
}''',
    '''void acpm_ipc_set_waiting_mode(bool mode)
{
    if (!acpm_ipc_runtime_ready() || !acpm_ipc) {
        pr_warn_once("ALICE_P30_ACPM_IPC_NOT_READY: refused waiting mode write\\n");
        return;
    }
    acpm_ipc->w_mode = mode;
}''', "donor acpm_ipc_set_waiting_mode")
i = replace_once(i,
    '''\tchannel_init();

\tif (acpm_debug->period) {''',
    '''\tret = channel_init();
    if (ret) {
        dev_err(&pdev->dev, "ALICE_P30_ACPM_IPC_CHANNEL_INIT_FAILED: %d\\n", ret);
        return ret;
    }
    /* Never assume ACPM firmware, regulator or UFS are runtime verified. */
    WRITE_ONCE(acpm_ipc_initialized, true);

\tif (acpm_debug->period) {''',
    "ACPM IPC channel init")
i = replace_once(i,
    '''static int acpm_ipc_remove(struct platform_device *pdev)
{
\treturn 0;
}''',
    '''static int acpm_ipc_remove(struct platform_device *pdev)
{
    WRITE_ONCE(acpm_ipc_initialized, false);
    return 0;
}''',
    "ACPM IPC remove")

h = replace_once(h,
    '''extern void acpm_ipc_set_waiting_mode(bool mode);''',
    '''extern bool acpm_ipc_runtime_ready(void);
extern void acpm_ipc_set_waiting_mode(bool mode);''',
    "ACPM IPC ready declaration")

a = replace_once(a,
    '''static int __init exynos_acpm_binary_update(void)
{
\tint ret;

\tacpm_ipc_set_waiting_mode(BUSY_WAIT);

\tret = plugins_init();

\treturn ret;
}''',
    '''static int __init exynos_acpm_binary_update(void)
{
    int ret;

    /* Proven P29 kernel panic: donor fs_initcall_sync ran with acpm_ipc
     * NULL (PC acpm_ipc_set_waiting_mode+0x10/0x20, FAR 0x30).
     * There is currently NO native ACPM firmware/IPC DT binding in
     * the Exynos8895 Linux 5.10 research board.
     * Do not access plugins/SRAM or invent a firmware-ready state.
     */
    if (!exynos_acpm || !exynos_acpm->dev || !acpm_initdata ||
        !acpm_srambase || !acpm_ipc_runtime_ready()) {
        pr_warn("ALICE_P30_ACPM_FIRMWARE_UPDATE_SKIPPED: firmware/IPC unavailable\\n");
        return 0; /* optional firmware stage absent; not hardware ready */
    }
    /* A working probe alone is not evidence plugin firmware has been
     * vetted. Require a dedicated explicit research opt-in in DT.
     */
    if (!of_property_read_bool(exynos_acpm->dev->of_node,
                               "alice,acpm-plugin-firmware-reviewed")) {
        pr_warn("ALICE_P30_ACPM_PLUGIN_UNREVIEWED: firmware writes blocked\\n");
        return 0;
    }

    acpm_ipc_set_waiting_mode(BUSY_WAIT);
    ret = plugins_init();
    return ret;
}''',
    "ACPM fs_initcall_sync")

for p, s in ((acpm, a), (ipc, i), (header, h)):
    p.write_text(s)
print("P30: repaired donor fs_initcall ACPM IPC null dereference")
print("P30: runtime readiness only after channel_init succeeds; no fake firmware state")
print("P30: firmware plugin update remains gated by explicit DT audit property")
print("P30: no UFS DT activation; NO-FLASH kernel research")
