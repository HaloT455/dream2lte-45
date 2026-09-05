# ALice V8 flash package

The CI output uses AnyKernel3 to replace only the kernel `Image` and the
device-tree blob in the boot partition already installed on `dream2lte`.
The existing ramdisk and ROM-specific command line are retained, which keeps
the same package usable on supported One UI and AOSP installations.

The installer accepts `dream2lte`, `dream2ltexx`, `SM-G955F`, and `SM-G955FD`.
It does not target other Exynos8895 devices.
