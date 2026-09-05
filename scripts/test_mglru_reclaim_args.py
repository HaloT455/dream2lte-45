#!/usr/bin/env python3
"""Exercise the real MGLRU call against shrink_page_list's 4.4 output contract."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--revision', help='read mm/vmscan.c from a Git revision')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
source = (subprocess.check_output(
    ['git', 'show', args.revision + ':mm/vmscan.c'], cwd=root, text=True)
    if args.revision else (root / 'mm/vmscan.c').read_text())

def function(name):
    start = re.search(r'^static\s+[^;{}]+\b' + name + r'\([^;{}]+\)\n\{',
                      source, re.M)
    if not start:
        raise SystemExit('missing function: ' + name)
    pos = start.end()
    depth = 1
    while depth:
        depth += (source[pos] == '{') - (source[pos] == '}')
        pos += 1
    return source[start.start():pos]

evict = function('evict_pages')
shrink = function('shrink_page_list')
declarations = evict.split('{', 1)[1].split('spin_lock_irq(', 1)[0]
call = re.search(r'reclaimed = shrink_page_list\([\s\S]*?\);', evict).group()
signature = shrink.split('{', 1)[0]
contract = shrink[shrink.index('\t*ret_nr_dirty +='):shrink.rfind('}')]
contract = contract.replace('return nr_reclaimed;', '''
    assert(*ret_nr_dirty == 1 && *ret_nr_unqueued_dirty == 2);
    assert(*ret_nr_congested == 3 && *ret_nr_writeback == 4);
    assert(*ret_nr_immediate == 5);
    return nr_reclaimed;''')

# Reuse the actual caller declarations/call and callee output writes. Page
# traversal is deliberately outside this host test; the bug was in this ABI.
harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
struct list_head { int unused; };
struct zone { int unused; };
struct scan_control { int unused; };
struct lruvec { struct zone zone; };
struct page { int unused; };
enum ttu_flags { TTU_UNMAP = 1 };
#define LIST_HEAD(name) struct list_head name = {0}
static struct zone *lruvec_zone(struct lruvec *v) { return &v->zone; }
''' + signature + r''' {
    unsigned long nr_dirty = 1, nr_unqueued_dirty = 2, nr_congested = 3;
    unsigned long nr_writeback = 4, nr_immediate = 5, nr_reclaimed = 7;
''' + contract + r'''
}
int main(void) {
    struct lruvec value = {0}, *lruvec = &value;
    struct scan_control scan = {0}, *sc = &scan;
''' + declarations + call + r'''
    assert(reclaimed == 7);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='mglru-output-contract-') as tmp:
    c = Path(tmp) / 'reclaim.c'
    exe = Path(tmp) / 'reclaim'
    c.write_text(harness)
    subprocess.run([os.environ.get('HOSTCC', 'cc'), '-std=gnu11', '-O1',
                    '-fsanitize=undefined', '-fno-sanitize-recover=all',
                    str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print('PASS: real MGLRU call supplies five initialized writable 4.4 reclaim outputs')
