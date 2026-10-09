#!/usr/bin/env bash
# P1B: surgical Exynos8895 pinctrl data backport (Linux 6.13 -> 5.10).
# Preserve 5.10 pinctrl framework; import only Exynos8895 bank tables and match.
set -euo pipefail
TREE="${1:?Usage: $0 /path/to/linux-5.10.262}"
[[ "$(make -s -C "$TREE" kernelversion)" == 5.10.* ]] || exit 3
export K510_PINCTRL_TREE="$TREE"
python3 - <<'PY'
import os, pathlib, urllib.request

tree = pathlib.Path(os.environ['K510_PINCTRL_TREE'])
root = tree / 'drivers/pinctrl/samsung'
base = "https://raw.githubusercontent.com/torvalds/linux/v6.13/"
def donor(path):
    with urllib.request.urlopen(base+path, timeout=60) as r:
        return r.read().decode()
def put(p, text):
    p.write_text(text)
def section(t,start,end):
    a=t.index(start)
    b=t.index(end,a)
    return t[a:b]

source=donor('drivers/pinctrl/samsung/pinctrl-exynos-arm64.c')
donor_h=donor('drivers/pinctrl/samsung/pinctrl-exynos.h')
type_info=section(source,
  'static const struct samsung_pin_bank_type exynos8895_bank_type_off',
  '\n};')
type_info+='\n};\n\n'
data=section(source,
  '/* pin banks of exynos8895 pin-controller 0',
  '/*\n * Pinctrl driver data for Tesla FSD')
macro=section(donor_h,
  '#define EXYNOS8895_PIN_BANK_EINTG',
  '\n\n#define EXYNOSV920_PIN_BANK_EINTG').rstrip()+'\n\n'
assert 'exynos8895_of_data' in data
assert 'exynos8895_bank_type_off' in type_info

c=root/'pinctrl-exynos-arm64.c'
text=c.read_text()
anchor='/* pin banks of exynos7 pin-controller - ALIVE */'
assert text.count(anchor)==1
if 'exynos8895_pin_banks0' not in text:
    text=text.replace(anchor,
        '/* Alice K510 P1B: exynos8895 bank data from Linux v6.13 */\n'+
        type_info+data+'\n'+anchor)
    put(c,text)

h=root/'pinctrl-exynos.h'
text=h.read_text()
assert '#endif /* __PINCTRL_SAMSUNG_EXYNOS_H */' in text
if 'EXYNOS8895_PIN_BANK_EINTG' not in text:
    text=text.replace('#endif /* __PINCTRL_SAMSUNG_EXYNOS_H */',
                      macro+'#endif /* __PINCTRL_SAMSUNG_EXYNOS_H */')
    put(h,text)

h=root/'pinctrl-samsung.h'
text=h.read_text()
anchor='extern const struct samsung_pinctrl_of_match_data exynos7_of_data;'
assert text.count(anchor)==1
if 'exynos8895_of_data' not in text:
    put(h,text.replace(anchor,'extern const struct samsung_pinctrl_of_match_data exynos8895_of_data;\n'+anchor))

c=root/'pinctrl-samsung.c'
text=c.read_text()
anchor='{ .compatible = "samsung,exynos7-pinctrl",'
assert text.count(anchor)==1
if '"samsung,exynos8895-pinctrl"' not in text:
    put(c,text.replace(anchor,
      '{ .compatible = "samsung,exynos8895-pinctrl",\n\t\t.data = &exynos8895_of_data },\n\t'+anchor))
print('P1B imported Exynos8895 pin banks into existing Linux 5.10 driver')
PY
