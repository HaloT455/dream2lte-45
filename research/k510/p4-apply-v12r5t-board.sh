#!/usr/bin/env bash
# P4A: transplant VERIFIED board facts from V12R5T SM-G955F FDT into
# genuine Linux 5.10 Exynos8895 DTS. Does not copy vendor 4.4 phandles.
# Safe research-only stage: UFS stays DISABLED pending PHY/PMIC bindings.
set -euo pipefail
TREE="$1"
OUT="$2"
DTS="$TREE/arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts"
test -s "$DTS"
test -f "$OUT/.config"
python3 - "$DTS" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
if "ALICE_K510_P4_V12R5T_BOARD" in s:
    raise SystemExit("P4 already applied; refusing duplicate nodes")
for key in ["ALICE_P1D_MEMORY_BEGIN","ALICE_K510_R1_PSTORE","ALICE_K510_P2_CHOSEN"]:
    if key not in s:
        raise SystemExit("P4 prerequisite not present: "+key)
anchor='#include "exynos8895.dtsi"'
if s.count(anchor)!=1:
    raise SystemExit("P4: Exynos8895 SoC include missing")
s=s.replace(anchor,anchor+'\n#include <dt-bindings/input/input.h>\n#include <dt-bindings/gpio/gpio.h>\n',1)
# Board names, pins and physical addresses verified against extracted
# V12R5T FDT SHA256 c53ccec95ec4eb428e8aa001060526c24b9a6ba734d678cc65cd579ce1357987.
# UART uses MAINLINE Linux 5.10 compatible + clock IDs, NOT vendor
# "samsung,exynos-uart" (unsupported by Linux 5.10 Samsung tty driver).
s += r"""
/* ALICE_K510_P4_V12R5T_BOARD: vetted subset. NOT Android/OneUI ready. */
&{/} {
    model = "Samsung Galaxy S8+ (SM-G955F) Linux 5.10 research";
    aliases {
        serial0 = &alice_dbg_uart;
    };
    gpio-keys {
        compatible = "gpio-keys";
        pinctrl-names = "default";
        pinctrl-0 = <&alice_key_power &alice_key_voldown
                     &alice_key_volup &alice_key_wink>;
        power-key {
            label = "Power";
            linux,code = <KEY_POWER>;
            gpios = <&gpa2 4 GPIO_ACTIVE_LOW>;
            wakeup-source;
        };
        voldown-key {
            label = "Volume Down";
            linux,code = <KEY_VOLUMEDOWN>;
            gpios = <&gpa0 4 GPIO_ACTIVE_LOW>;
        };
        volup-key {
            label = "Volume Up";
            linux,code = <KEY_VOLUMEUP>;
            gpios = <&gpa0 3 GPIO_ACTIVE_LOW>;
        };
        wink-key {
            label = "Bixby";
            /* Exact V12R5T stock keycode 0x2bf; don't silently remap. */
            linux,code = <0x2bf>;
            gpios = <&gpa0 6 GPIO_ACTIVE_LOW>;
            wakeup-source;
        };
    };
};

&{/chosen} {
    stdout-path = "serial0:115200n8";
    /* Do not replace /chosen initrd-start/end set by uniLoader. */
};

&oscclk {
    clock-frequency = <26000000>;
};

&pinctrl_alive {
    alice_key_power: alice-key-power-pins {
        samsung,pins = "gpa2-4";
        samsung,pin-function = <EXYNOS_PIN_FUNC_EINT>;
        samsung,pin-pud = <EXYNOS_PIN_PULL_NONE>;
        samsung,pin-drv = <EXYNOS7_PIN_DRV_LV1>;
    };
    alice_key_voldown: alice-key-voldown-pins {
        samsung,pins = "gpa0-4";
        samsung,pin-function = <EXYNOS_PIN_FUNC_EINT>;
        samsung,pin-pud = <EXYNOS_PIN_PULL_NONE>;
        samsung,pin-drv = <EXYNOS7_PIN_DRV_LV1>;
    };
    alice_key_volup: alice-key-volup-pins {
        samsung,pins = "gpa0-3";
        samsung,pin-function = <EXYNOS_PIN_FUNC_EINT>;
        samsung,pin-pud = <EXYNOS_PIN_PULL_NONE>;
        samsung,pin-drv = <EXYNOS7_PIN_DRV_LV1>;
    };
    alice_key_wink: alice-key-wink-pins {
        samsung,pins = "gpa0-6";
        samsung,pin-function = <EXYNOS_PIN_FUNC_EINT>;
        samsung,pin-pud = <EXYNOS_PIN_PULL_NONE>;
        samsung,pin-drv = <EXYNOS7_PIN_DRV_LV1>;
    };
};

&{/soc@0} {
    /* V12R5T /uart@10430000: irq SPI385, 256-byte FIFO, gpd0-7/6 pins.
       4.4 vendor clock-name gate_pclk0/gate_uart0 replaced with actual
       Linux v5.10 mainline bindings from Exynos8895 CMU_PERIC0. */
    alice_dbg_uart: serial@10430000 {
        compatible = "samsung,exynos5433-uart",
                     "samsung,exynos4210-uart";
        reg = <0x10430000 0x100>;
        interrupts = <GIC_SPI 385 IRQ_TYPE_LEVEL_HIGH>;
        clocks = <&cmu_peric0 CLK_GOUT_PERIC0_UART_DBG_PCLK>,
                 <&cmu_peric0 CLK_GOUT_PERIC0_UART_DBG_EXT_UCLK>;
        clock-names = "uart", "clk_uart_baud0";
        pinctrl-names = "default";
        pinctrl-0 = <&uart0_bus>;
        status = "okay";
    };

    /* V12R5T /ufs@0x11120000, IRQ SPI334. 4.4 vendor-compatible
       "samsung,exynos-ufs" has NOT been proved to match v5.10 8895
       PHY/calibration/regulator; no writes to UFS controller yet. */
    alice_ufs_embd: ufs@11120000 {
        compatible = "samsung,exynos7-ufs";
        reg = <0x11120000 0x200>,
              <0x11121100 0x200>,
              <0x11110000 0x8000>,
              <0x11130000 0x100>;
        reg-names = "hci", "vs_hci", "unipro", "protector";
        interrupts = <GIC_SPI 334 IRQ_TYPE_LEVEL_HIGH>;
        pinctrl-names = "default";
        pinctrl-0 = <&ufs_rst_n &ufs_refclk_out>;
        /* PHYSICAL UFS PHY, power rails, reset & calibration MISSING.
           Never change status until the Samsung controller driver is
           verified on this specific Exynos8895 board. */
        status = "disabled";
    };
};
"""
p.write_text(s)
print("P4: board IDs/pins/oscillator, UART and GPIO keys enabled; UFS gated")
PY

# Device capabilities supported in genuine 5.10, distinct from runtime support.
# This does not cause disabled UFS node to probe.
"$TREE/scripts/config" --file "$OUT/.config" \
  --enable SERIAL_SAMSUNG \
  --enable SERIAL_SAMSUNG_CONSOLE \
  --enable SERIAL_EARLYCON \
  --enable INPUT \
  --enable INPUT_KEYBOARD \
  --enable GPIOLIB \
  --enable KEYBOARD_GPIO \
  --enable SCSI \
  --enable SCSI_DMA \
  --enable SCSI_UFSHCD \
  --enable SCSI_UFSHCD_PLATFORM \
  --enable SCSI_UFS_EXYNOS
make -s -C "$TREE" O="$OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
for key in SERIAL_SAMSUNG SERIAL_SAMSUNG_CONSOLE SERIAL_EARLYCON INPUT INPUT_KEYBOARD GPIOLIB KEYBOARD_GPIO SCSI_UFSHCD SCSI_UFSHCD_PLATFORM SCSI_UFS_EXYNOS; do
  grep -q "^CONFIG_$key=y$" "$OUT/.config" || {
      echo "P4: dependency rejected CONFIG_$key=y (fail closed)" >&2
      exit 12
  }
done
echo "P4 V12R5T board subset + Linux 5.10 UART/UFS drivers: CONFIG VERIFIED"
