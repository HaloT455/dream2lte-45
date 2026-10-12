ALICE V12R61 Android APK: non-privileged dashboard reading /sys/kernel/alice and /proc.
Uses root only after confirmation to select a safe KernelSU module policy mode.
No automatic MGLRU, clock, thermal, SELinux or DTB modifications. Hardware VPU
inference is not implemented; "voice" invokes the Android speech-recognition
provider when present (which may be online). AI assistant is deterministic rules,
not a bundled trained language model. On-device boot/runtime not yet validated. V12R61 directly reads /sys/kernel/alice/assessment and /sys/kernel/alice/capabilities; users may select sysfs mode 0-5 and explicitly opt into a bounded vm.swappiness-only policy via KernelSU root. Kernel resets to stability and policy OFF on every boot.
This in-repo lite companion does not replace the more complete standalone
V12R5Z source package; in-repo APK can be compiled by the GitHub workflow.
