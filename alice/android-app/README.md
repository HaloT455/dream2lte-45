ALICE V12R60 Android APK: non-privileged dashboard reading /sys/kernel/alice and /proc.
Uses root only after confirmation to select a safe KernelSU module policy mode.
No automatic MGLRU, clock, thermal, SELinux or DTB modifications. Hardware VPU
inference is not implemented; "voice" invokes the Android speech-recognition
provider when present (which may be online). AI assistant is deterministic rules,
not a bundled trained language model. On-device boot/runtime not yet validated.
This in-repo lite companion does not replace the more complete standalone
V12R5Z source package; in-repo APK can be compiled by the GitHub workflow.
