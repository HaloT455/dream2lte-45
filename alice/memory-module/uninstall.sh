#!/system/bin/sh
MODDIR=${0%/*}
sh "$MODDIR/low-swap.sh" restore || echo ALICE_LOW_SWAP_RESTORE_REQUIRES_REVIEW
