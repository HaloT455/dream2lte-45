#!/usr/bin/env python3
"""V12R5R: preserve stock compaction policy, activate zsmalloc migration."""
from pathlib import Path
cfg=Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
kc=Path("mm/Kconfig").read_text()
compaction=Path("mm/compaction.c").read_text()
zs=Path("mm/zsmalloc.c").read_text()
migrate=Path("mm/migrate.c").read_text()
flags=Path("include/linux/page-flags.h").read_text()
assert "CONFIG_ZRAM=y" in cfg
assert "CONFIG_ZSMALLOC=y" in cfg
assert "CONFIG_COMPACTION=y" in cfg
assert "CONFIG_ZSWAP_MIGRATION_SUPPORT=y" in cfg
assert "depends on (ZSWAP || ZRAM) && ZSMALLOC && COMPACTION" in kc
assert "#ifdef CONFIG_ZSWAP_MIGRATION_SUPPORT" in compaction
assert "if (unlikely(__PageMovable(page)) &&" in compaction
assert "isolate_movable_page(page, isolate_mode)" in compaction
assert "#ifdef CONFIG_ZSWAP_MIGRATION_SUPPORT\nstatic int zs_page_migration_enabled = 1;" in zs
assert "if (!zs_page_migration_enabled)" in zs
assert "SetZsPageMovable(pool, zspage);" in zs
assert "bool zs_page_isolate(struct page *page, isolate_mode_t mode)" in zs
assert "int zs_page_migrate(struct address_space *mapping" in zs
assert "bool isolate_movable_page(struct page *page, isolate_mode_t mode)" in migrate
assert "#define PAGE_MAPPING_MOVABLE\t0x2" in flags
print("PASS: V12R5R existing zsmalloc migration path enabled for zram")
print("WARNING: requires real device boot and CMA/crypto regression test")
