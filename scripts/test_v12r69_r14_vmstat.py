#!/usr/bin/env python3
"""Compile the production aggregation/render functions for multiple zone layouts."""
from pathlib import Path
import itertools,os,re,subprocess,tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'mm/vmstat.c').read_text()
start=s.index('static unsigned long vmstat_reclaim_sum(')
end=s.index('\n#endif',start)
functions=s[start:end]
assert 'if (off == ARRAY_SIZE(vmstat_text) - 1)\n\t\tvmstat_lmkd_aliases(m);' in s
for name in ['exynos8895-dream2lte_defconfig','exynos8895-dreamlte_defconfig']:
 assert 'CONFIG_VM_EVENT_COUNTERS=y' in (root/'arch/arm64/configs'/name).read_text()
for dma,dma32,high,device in itertools.product([False,True],repeat=4):
 flags=[]
 for enabled,name in [(dma,'CONFIG_ZONE_DMA'),(dma32,'CONFIG_ZONE_DMA32'),(high,'CONFIG_HIGHMEM')]:
  if enabled:flags.append('-D'+name)
 zones=['ZONE_DMA']*dma+['ZONE_DMA32']*dma32+['ZONE_NORMAL']+['ZONE_HIGHMEM']*high+['ZONE_MOVABLE']+['ZONE_DEVICE']*device
 code='''#include <assert.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include "include/linux/vm_event_item.h"
enum zone_type { ZONES };
#define NR_VM_ZONE_STAT_ITEMS 32
#define NR_VM_WRITEBACK_STAT_ITEMS 2
struct seq_file { void *private; char text[1024]; unsigned int length; };
static void seq_printf(struct seq_file *m, const char *fmt, ...) {
 va_list args; va_start(args,fmt);
 m->length += vsnprintf(m->text+m->length,sizeof(m->text)-m->length,fmt,args);
 va_end(args);
}
FUNCTIONS
int main(void) {
 unsigned long data[34+NR_VM_EVENT_ITEMS], copy[34+NR_VM_EVENT_ITEMS];
 struct seq_file m={.private=data}; unsigned long expected[4];
 enum vm_event_item groups[]={PGSCAN_KSWAPD_NORMAL,PGSCAN_DIRECT_NORMAL,PGSTEAL_KSWAPD_NORMAL,PGSTEAL_DIRECT_NORMAL};
 int i,z; memset(data,0,sizeof(data));
 for(i=0;i<34;i++)data[i]=987654;
 for(i=0;i<4;i++) { expected[i]=0;
  for(z=0;z<=ZONE_MOVABLE;z++) {
   unsigned long val=(i+1)*100+z;
   data[34+groups[i]-ZONE_NORMAL+z]=val;expected[i]+=val;
  }
 }
 memcpy(copy,data,sizeof(data)); vmstat_lmkd_aliases(&m);
 unsigned long a,b,c,d;
 assert(sscanf(m.text,"pgscan_kswapd %lu\\npgscan_direct %lu\\npgsteal_kswapd %lu\\npgsteal_direct %lu\\n",&a,&b,&c,&d)==4);
 assert(a==expected[0] && b==expected[1] && c==expected[2] && d==expected[3]);
 assert(memcmp(data,copy,sizeof(data))==0);
 return 0;
}
'''.replace('ZONES',','.join(zones)).replace('FUNCTIONS',functions)
 with tempfile.TemporaryDirectory() as td:
  c=Path(td)/'test.c';exe=Path(td)/'test';c.write_text(code)
  subprocess.run([os.environ.get('HOSTCC','cc'),'-I',str(root),'-Wall','-Wextra','-Werror',*flags,str(c),'-o',str(exe)],check=True)
  subprocess.run([str(exe)],check=True)
print('PASS: real vmstat aggregation/rendering across 16 zone layouts; aliases are sums from the same immutable snapshot; native fields retained')
