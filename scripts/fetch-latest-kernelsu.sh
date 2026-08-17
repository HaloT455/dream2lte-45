#!/bin/bash
set -e
exec 9>.kernelsu-fetch-lock
flock -n 9 || exit 0
[[ $(( $(date +%s) - $(stat -c %Y "drivers/kernelsu/.check" 2>/dev/null || echo 0) )) -gt 86400 ]] || exit 0

AUTHOR="KernelSU-Next"
REPO="KernelSU-Next"
GIT_VERSION=`curl -s -I -k "https://api.github.com/repos/$AUTHOR/$REPO/commits?sha=legacy&per_page=1" | sed -n 's/.*page=\([0-9]*\)>; rel="last".*/\1/p'`
TAG=`curl -s https://api.github.com/repos/$AUTHOR/$REPO/tags | jq -r '.[0].name'`

if [[ -f drivers/kernelsu/.version && *$(cat drivers/kernelsu/.version)* == *$GIT_VERSION* ]]; then
	touch drivers/kernelsu/.check
	exit 0
fi

# printf "$REPO updating to $((10000+$VERSION+200))\n"
rm -rf drivers/kernelsu
mkdir -p drivers/kernelsu
cd drivers/kernelsu
wget -q -O - https://github.com/$AUTHOR/$REPO/archive/refs/heads/legacy.tar.gz | tar -xz --strip=2 "$REPO-legacy/kernel"
wget -q -O - https://github.com/$AUTHOR/$REPO/archive/refs/heads/legacy.tar.gz | tar -xz --strip=1 "$REPO-legacy/uapi" -C "uapi"
echo $GIT_VERSION >> .version
touch .check

# You can patch for your kernel here
OFFSET=$(grep 'KSU_VERSION=' Kbuild | sed -n 's/.*+ \([0-9]\+\)).*/\1/p')
VAL=$((30000 + GIT_VERSION + OFFSET))
echo "" >> Makefile
sed -i '/error -- KernelSU-Next/d' Kbuild
sed -i "s/^KSU_VERSION_FALLBACK := 1/KSU_VERSION_FALLBACK := $VAL/" Kbuild
sed -i "s/^KSU_VERSION_TAG_FALLBACK := v0.0.1/KSU_VERSION_TAG_FALLBACK := \"$TAG\"/" Kbuild
