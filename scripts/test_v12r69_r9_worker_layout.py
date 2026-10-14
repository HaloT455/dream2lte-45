#!/usr/bin/env python3
"""Compile the real worker structure and check original 64-bit member offsets.

R8 inserted last_func before current_pwq and shifted every later member. PSI
needs extra storage but does not need to alter the pre-existing worker layout.
"""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path(os.environ.get('WORKER_TEST_HEADER', 'kernel/workqueue_internal.h')).read_text()
begin = source.index('struct worker {')
opening = source.index('{', begin)
depth, end = 1, opening + 1
while depth:
    depth += (source[end] == '{') - (source[end] == '}')
    end += 1
worker = source[begin:end] + ';'
stub = '''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
struct list_head { struct list_head *next, *prev; };
struct hlist_node { struct hlist_node *next, **pprev; };
struct work_struct; struct pool_workqueue; struct task_struct;
struct worker_pool; struct workqueue_struct;
typedef void (*work_func_t)(struct work_struct *);
#define WORKER_DESC_LEN 24
'''
main = '''
int main(void) {
    assert(sizeof(void *) == 8);
    printf("current_pwq=%zu task=%zu pool=%zu last_func=%zu\\n",
           offsetof(struct worker,current_pwq), offsetof(struct worker,task),
           offsetof(struct worker,pool), offsetof(struct worker,last_func));
    fflush(stdout);
    assert(offsetof(struct worker,current_work) == 16);
    assert(offsetof(struct worker,current_func) == 24);
    assert(offsetof(struct worker,current_pwq) == 32);
    assert(offsetof(struct worker,desc_valid) == 40);
    assert(offsetof(struct worker,scheduled) == 48);
    assert(offsetof(struct worker,task) == 64);
    assert(offsetof(struct worker,pool) == 72);
    assert(offsetof(struct worker,node) == 80);
    assert(offsetof(struct worker,last_active) == 96);
    assert(offsetof(struct worker,flags) == 104);
    assert(offsetof(struct worker,id) == 108);
    assert(offsetof(struct worker,desc) == 112);
    assert(offsetof(struct worker,rescue_wq) == 136);
    assert(offsetof(struct worker,last_func) == 144);
    puts("PASS: all original Samsung 64-bit worker member offsets preserved; PSI storage appended");
}
'''
with tempfile.TemporaryDirectory(prefix='r9-worker-layout-') as tmp:
    c, exe = Path(tmp)/'layout.c', Path(tmp)/'layout'
    c.write_text(stub + worker + main)
    subprocess.run([os.environ.get('HOSTCC', 'cc'), '-std=gnu99', '-Wall', '-Wextra',
                    '-Werror', str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)
