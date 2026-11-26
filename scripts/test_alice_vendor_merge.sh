#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
T="$(mktemp -d)"
trap 'sudo rm -rf "$T"' EXIT
cd "$T"
mkdir -p base-tree/etc donor-tree/etc
printf 'old-radio\n' > base-tree/etc/ril-test.conf
printf 'new-radio\n' > donor-tree/etc/ril-test.conf
printf 'unchanged\n' > base-tree/etc/keep.conf
cp base-tree/etc/keep.conf donor-tree/etc/keep.conf
truncate -s 16M base.raw
truncate -s 16M donor.raw
mke2fs -q -t ext4 -F -b 4096 -d base-tree base.raw
mke2fs -q -t ext4 -F -b 4096 -d donor-tree donor.raw
printf '4\n4096\n0\n0\nnew 2,0,4096\n' > vendor.transfer.list
brotli -q 3 -o vendor.new.dat.br base.raw
sudo python3 "$ROOT/scripts/alice_vendor_merge.py" --base vendor.new.dat.br --transfer vendor.transfer.list --donor donor.raw --out audit
test ! -e audit/vendor-MERGED-UNTESTED.img
cmp base.raw audit/vendor-base.img
python3 - <<'PY'
import json
from pathlib import Path
items=json.loads(Path('audit/vendor-diff.json').read_text())
x=next(i for i in items if i['path']=='etc/ril-test.conf')
assert x['category']=='radio'
Path('plan.json').write_text(json.dumps([{'path':x['path'],'base_sha256':x['base']['sha256'],'donor_sha256':x['donor']['sha256']}]))
PY
sudo python3 "$ROOT/scripts/alice_vendor_merge.py" --base vendor.new.dat.br --transfer vendor.transfer.list --donor donor.raw --out merged --plan plan.json
(cd merged && sha256sum -c SHA256SUMS)
debugfs -R 'cat /etc/ril-test.conf' merged/vendor-MERGED-UNTESTED.img > actual
cmp actual donor-tree/etc/ril-test.conf
debugfs -R 'cat /etc/keep.conf' merged/vendor-MERGED-UNTESTED.img > actual
cmp actual base-tree/etc/keep.conf
# Test7 is EROFS; exercise an actual EROFS donor, not only two ext4 images.
mkfs.erofs -T0 donor.erofs donor-tree
sudo python3 "$ROOT/scripts/alice_vendor_merge.py" --base vendor.new.dat.br --transfer vendor.transfer.list --donor donor.erofs --out erofs-audit
test ! -e erofs-audit/vendor-MERGED-UNTESTED.img
sudo python3 "$ROOT/scripts/alice_vendor_merge.py" --base vendor.new.dat.br --transfer vendor.transfer.list --donor donor.erofs --out erofs-merged --plan plan.json
(cd erofs-merged && sha256sum -c SHA256SUMS)
debugfs -R 'cat /etc/ril-test.conf' erofs-merged/vendor-MERGED-UNTESTED.img > actual
cmp actual donor-tree/etc/ril-test.conf
debugfs -R 'cat /etc/keep.conf' erofs-merged/vendor-MERGED-UNTESTED.img > actual
cmp actual base-tree/etc/keep.conf
printf 'Synthetic test passed. No actual phone firmware used or produced.\n'
