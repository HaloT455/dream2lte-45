#!/usr/bin/env python3
"""Reject effective configuration changes outside the UI1 tracing dependency set."""
import re
import sys
from pathlib import Path

TRACE_KEYS = {
    'CONFIG_BINARY_PRINTF', 'CONFIG_CONTEXT_SWITCH_TRACER', 'CONFIG_DEBUG_FS',
    'CONFIG_ENABLE_DEFAULT_TRACERS', 'CONFIG_EVENT_TRACING', 'CONFIG_NOP_TRACER',
    'CONFIG_RING_BUFFER', 'CONFIG_TRACE_CLOCK', 'CONFIG_TRACEPOINTS', 'CONFIG_TRACING',
}


def parse(text):
    config = {}
    for line in text.splitlines():
        if line.startswith('CONFIG_') and '=' in line:
            key, value = line.split('=', 1)
            config[key] = value
        else:
            match = re.fullmatch(r'# (CONFIG_\w+) is not set', line)
            if match:
                config[match[1]] = 'n'
    return config


def verify(base, candidate):
    changes = {k: (base.get(k, 'n'), candidate.get(k, 'n'))
               for k in base.keys() | candidate.keys()
               if base.get(k, 'n') != candidate.get(k, 'n')}
    unexpected = set(changes) - TRACE_KEYS - {'CONFIG_LOCALVERSION'}
    if unexpected:
        raise ValueError(f'Non-tracing config changed: {sorted(unexpected)}')
    for key in TRACE_KEYS | {'CONFIG_FTRACE'}:
        if candidate.get(key) != 'y':
            raise ValueError(f'Missing tracing dependency: {key}')
    for key in ('CONFIG_FUNCTION_TRACER', 'CONFIG_FUNCTION_GRAPH_TRACER',
                'CONFIG_DYNAMIC_FTRACE', 'CONFIG_IRQSOFF_TRACER',
                'CONFIG_PREEMPT_TRACER', 'CONFIG_SCHED_TRACER',
                'CONFIG_FTRACE_SYSCALLS', 'CONFIG_SCHEDSTATS',
                'CONFIG_BT_DEBUGFS', 'CONFIG_F2FS_STAT_FS'):
        if candidate.get(key, 'n') != 'n':
            raise ValueError(f'Unnecessary tracing/debug feature: {key}')
    for key, (old, new) in sorted(changes.items()):
        print(f'{key}: {old} -> {new}')
    return changes


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: verify_ui_trace_config.py BASE_CONFIG TRACE_CONFIG')
    verify(*(parse(Path(p).read_text()) for p in sys.argv[1:]))
