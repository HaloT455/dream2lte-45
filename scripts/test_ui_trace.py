#!/usr/bin/env python3
"""Host tests use a private fake proc/sys tree; never touch host tracing."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from verify_ui_trace_config import TRACE_KEYS, verify

SCRIPT = Path(__file__).with_name('collect_ui_trace.sh')
EVENTS = ('sched/sched_switch', 'sched/sched_wakeup', 'power/cpu_frequency',
          'power/cpu_idle', 'binder/binder_transaction', 'binder/binder_transaction_received')
FAKE_COMMAND = r'''#!/usr/bin/env python3
import os, signal, sys
from pathlib import Path
root = Path(os.environ['UI_TRACE_FAKE_ROOT'])
trace = root / 'sys/kernel/tracing'
name = Path(sys.argv[0]).name
mode = os.environ.get('UI_TRACE_FAKE_MODE', '')
if name == 'id':
    print(1000 if mode == 'nonroot' else 0)
elif name == 'getprop':
    print(0)
elif name == 'getenforce':
    print('Enforcing')
elif name == 'pidof':
    sys.exit(1)
elif name == 'dumpsys':
    print('Mock gfxinfo snapshot')
elif name == 'sleep':
    if mode == 'signal':
        os.kill(os.getppid(), signal.SIGTERM)
elif name == 'mount':
    print('mount denied', file=sys.stderr)
    sys.exit(1)
elif name == 'umount':
    sys.exit(0)
elif name == 'atrace':
    with (root / 'calls').open('a') as out:
        out.write(' '.join(sys.argv[1:]) + '\n')
    action = sys.argv[1]
    if action == '--list_categories':
        for c in 'sched freq idle gfx view wm am binder_driver memreclaim disk'.split():
            if mode != 'missing_category' or c != 'sched':
                print(c, '- mocked category')
    elif action == '--async_start':
        if mode == 'start_error':
            sys.exit(1)
        if mode != 'silent_start_error':
            (trace / 'tracing_on').write_text('1\n')
            for node in (trace / 'events').rglob('enable'):
                node.write_text('1\n')
    elif action == '--async_stop':
        (trace / 'tracing_on').write_text('0\n')
        for node in (trace / 'events').rglob('enable'):
            node.write_text('0\n')
        print('TRACE:\n# mock trace\nmock-1 [000] 1.000: sched_switch: mock')
'''


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ui-trace-test-')
        self.root = Path(self.tmp.name)
        self.trace = self.root / 'sys/kernel/tracing'
        nodes = {'sys/kernel/tracing/trace_marker': '', 'sys/kernel/tracing/trace': '',
                 'sys/kernel/tracing/tracing_on': '0\n',
                 'sys/kernel/tracing/current_tracer': 'nop\n',
                 'sys/kernel/tracing/events/enable': '0\n',
                 'sys/kernel/tracing/per_cpu/cpu0/stats': 'entries: 1\noverrun: 0\n',
                 'proc/filesystems': 'nodev\ttracefs\n', 'proc/mounts': ''}
        for event in EVENTS:
            nodes['sys/kernel/tracing/events/' + event + '/enable'] = '0\n'
        for path, value in nodes.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value)
        fakebin = self.root / 'bin'
        fakebin.mkdir()
        runner = fakebin / 'mock-command'
        runner.write_text(FAKE_COMMAND)
        runner.chmod(0o755)
        for command in ('id', 'getprop', 'getenforce', 'pidof', 'dumpsys',
                        'sleep', 'atrace', 'mount', 'umount'):
            (fakebin / command).symlink_to(runner)
        script = SCRIPT.read_text()
        for prefix in ('/sys/', '/proc/', '/dev/cpuctl/'):
            script = script.replace(prefix, str(self.root) + prefix)
        self.script = self.root / 'collect.sh'
        self.script.write_text(script)
        self.env = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ['PATH'],
                        UI_TRACE_FAKE_ROOT=str(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def run_capture(self, mode='', seconds='5'):
        return subprocess.run(['sh', str(self.script), seconds],
                              env=dict(self.env, UI_TRACE_FAKE_MODE=mode),
                              text=True, capture_output=True, timeout=10)

    def calls(self):
        p = self.root / 'calls'
        return p.read_text() if p.exists() else ''

    def assert_stopped(self):
        self.assertEqual((self.trace / 'tracing_on').read_text().strip(), '0')
        self.assertEqual((self.trace / 'events/enable').read_text().strip(), '0')

    def test_success(self):
        result = self.run_capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        for marker in ('=== before ===', '=== buffer stats ===', '=== trace begin ===',
                       'sched_switch:', '=== trace end ===', '=== after ==='):
            self.assertIn(marker, result.stdout)
        self.assertEqual(self.calls().count('--async_start'), 1)
        self.assertEqual(self.calls().count('--async_stop'), 1)
        self.assert_stopped()

    def test_invalid_durations(self):
        for seconds in ('', '0', '4', '61', '999999999999999999999', '-1', '5;id', 'abc'):
            with self.subTest(seconds=seconds):
                self.assertNotEqual(self.run_capture(seconds=seconds).returncode, 0)
        self.assertNotIn('--async_start', self.calls())

    def test_sixty_seconds_accepted(self):
        result = self.run_capture(seconds='60')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('duration=60s', result.stdout)
        self.assertIn('-b 8192', self.calls())

    def test_nonroot_and_missing_category(self):
        for mode in ('nonroot', 'missing_category'):
            self.assertNotEqual(self.run_capture(mode).returncode, 0)
        self.assertNotIn('--async_start', self.calls())

    def test_active_session_untouched(self):
        (self.trace / 'events/enable').write_text('1\n')
        self.assertNotEqual(self.run_capture().returncode, 0)
        self.assertEqual(self.calls(), '')
        self.assertEqual((self.trace / 'events/enable').read_text(), '1\n')

    def test_failed_start_cleans_up(self):
        for mode in ('start_error', 'silent_start_error'):
            with self.subTest(mode=mode):
                self.assertNotEqual(self.run_capture(mode).returncode, 0)
                self.assert_stopped()
        self.assertEqual(self.calls().count('--async_stop'), 2)

    def test_signal_cleans_up(self):
        result = self.run_capture('signal')
        self.assertEqual(result.returncode, 130, result.stderr)
        self.assert_stopped()
        self.assertIn('--async_stop', self.calls())
        self.assertIn('=== trace begin ===', result.stdout)
        self.assertIn('sched_switch:', result.stdout)
        self.assertIn('Stopped early:', result.stderr)
        self.assertEqual(self.calls().count('--async_stop'), 1)

    def test_missing_kernel_support(self):
        (self.trace / 'trace_marker').unlink()
        (self.root / 'proc/filesystems').write_text('nodev\tsysfs\n')
        result = self.run_capture()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no tracefs', result.stderr)
        self.assertEqual(self.calls(), '')

    def test_mount_failure_stops(self):
        (self.trace / 'trace_marker').unlink()
        result = self.run_capture()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('do not change SELinux', result.stderr)
        self.assertEqual(self.calls(), '')


class ConfigTests(unittest.TestCase):
    def test_only_trace_changes_allowed(self):
        base = {'CONFIG_FTRACE': 'y', 'CONFIG_SWAP': 'y'}
        candidate = base | {key: 'y' for key in TRACE_KEYS}
        with contextlib.redirect_stdout(io.StringIO()):
            verify(base, candidate)
        for key, value in (('CONFIG_SWAP', 'n'), ('CONFIG_SCHEDSTATS', 'y'),
                           ('CONFIG_FUNCTION_TRACER', 'y'), ('CONFIG_BT_DEBUGFS', 'y'),
                           ('CONFIG_F2FS_STAT_FS', 'y'), ('CONFIG_TRACING', 'n')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify(base, candidate | {key: value})


if __name__ == '__main__':
    unittest.main()
