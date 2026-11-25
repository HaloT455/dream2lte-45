# ALice vendor merge
Base: vendor.new.dat.br plus vendor.transfer.list. Donor: vendor-a16-sim2-lte-ril-ab-video6-UNTESTED.img. Actual binaries were inaccessible to the assistant; no donor files have been reviewed or applied. This is a conservative tool, not a device-tested fix.
Run on Ubuntu with sufficient free disk (at least 5 GB), only with trusted images, preferably in a VM:
```bash
sudo apt install brotli e2fsprogs android-sdk-libsparse-utils python3
sudo python3 scripts/alice_vendor_merge.py --base vendor.new.dat.br --transfer vendor.transfer.list --donor vendor-a16-sim2-lte-ril-ab-video6-UNTESTED.img --out vendor-audit
```
Audit reconstructs the full transfer image including its trailing blocks, verifies ext4, mounts both read-only and records all file hashes, owners, modes, links and xattrs. No merged image without an explicitly reviewed plan. Non-ext4/unclean filesystems stop. The report's category tags are heuristics, not proof of fixes.
Review radio/dual SIM/LTE, lights/LED, media codec changes together with dependencies, init, VINTF, SELinux and target system. Plan format: JSON array with path (relative to vendor root), base_sha256, donor_sha256 from audit. No automatic addition or removal of files, no symlink or metadata changes. Use a NEW output directory and append --plan reviewed.json to the command to build. Output is UNTESTED raw ext4; AVB metadata is not regenerated, do not flash until partition size/AVB and runtime compatibility checked. No automatic flash.
