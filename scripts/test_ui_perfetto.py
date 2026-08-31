#!/usr/bin/env python3
"""Private fake tracefs/processes only. No host tracing or root settings changed."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('collect_ui_perfetto.sh')
CONFIG = SCRIPT.parent.parent / 'apps/ui-trace/assets/ui-perfetto.pbtxt'
EVENTS = ('sched/sched_switch', 'sched/sched_wakeup',
          'vmscan/mm_vmscan_direct_reclaim_begin', 'vmscan/mm_vmscan_direct_reclaim_end')
MOCK = r'''#!/usr/bin/env python3
import os, re, signal, sys, time
from pathlib import Path
root = Path(os.environ['ALICE_FAKE_ROOT'])
mode = os.environ.get('ALICE_FAKE_MODE', '')
name = Path(sys.argv[0]).name
trace = root / 'sys/kernel/tracing'
if name == 'id': print(1000 if mode == 'nonroot' else 0)
elif name == 'getprop': print(1 if mode == 'active_prop' else 0)
elif name == 'getenforce': print('Enforcing')
elif name == 'pidof': sys.exit(1)
elif name == 'mount': sys.exit(1)
elif name == 'umount': sys.exit(0)
elif name == 'cp': sys.exit(1)
elif name == 'perfetto':
    if '--version' in sys.argv: print('Perfetto mocked'); sys.exit(0)
    (root / 'called').write_text(' '.join(sys.argv[1:]))
    if mode == 'start_failure': print('Cannot connect to traced'); sys.exit(1)
    proc = root / 'proc' / str(os.getpid())
    proc.mkdir()
    (proc / 'cmdline').write_bytes(b'\0'.join(s.encode() for s in sys.argv) + b'\0')
    config = Path(sys.argv[sys.argv.index('-c') + 1]).read_text()
    output = Path(re.search(r'^output_path: "([^"]+)"$', config, re.M)[1])
    output.write_bytes(b'\x0a\x03abc' * 1000)
    nodes = list((trace / 'events').rglob('enable'))
    if mode != 'missing_events':
        for node in nodes: node.write_text('1\n')
    def finish(sig=None, frame=None):
        if mode != 'cleanup_failure':
            for node in nodes: node.write_text('0\n')
        (proc / 'cmdline').unlink()
        sys.exit(0)
    signal.signal(signal.SIGTERM, finish)
    if mode == 'signal':
        time.sleep(1.2)
        os.kill(os.getppid(), signal.SIGTERM)
        time.sleep(10)
    elif mode == 'missing_events': time.sleep(15)
    else: time.sleep(1.3)
    finish()
'''


class PerfettoCollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='alice-perfetto-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.trace = self.root / 'sys/kernel/tracing'
        nodes = {'trace_marker': '', 'current_tracer': 'nop\n', 'events/enable': '0\n'}
        nodes.update({'events/' + e + '/enable': '0\n' for e in EVENTS})
        for name, value in nodes.items():
            node = self.trace / name
            node.parent.mkdir(parents=True, exist_ok=True)
            node.write_text(value)
        (self.root / 'proc').mkdir()
        (self.root / 'proc/filesystems').write_text('nodev\ttracefs\n')
        (self.root / 'proc/mounts').write_text('')
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        mock = bin_dir / 'mock'
        mock.write_text(MOCK)
        mock.chmod(0o755)
        for name in ('id', 'getprop', 'getenforce', 'pidof', 'mount', 'umount', 'perfetto'):
            (bin_dir / name).symlink_to(mock)
        # Fake proc also models argv ownership: host proc/PID namespaces can differ.
        script = SCRIPT.read_text()
        for prefix in ('/proc/', '/sys/', '/dev/cpuctl/', '/data/misc/perfetto-traces'):
            script = script.replace(prefix, str(self.root) + prefix)
        self.script = self.root / 'collector.sh'
        self.script.write_text(script)
        self.config = self.root / 'config.pbtxt'
        self.native = self.root / 'data/misc/perfetto-traces/alice-ui-12345678-1234-1234-1234-123456789abc.perfetto-trace'
        self.native.parent.mkdir(parents=True)
        self.config.write_text(CONFIG.read_text() + '\noutput_path: "' + str(self.native) + '"\n')
        self.output = self.root / 'output.trace'
        self.output.touch()
        self.env = dict(os.environ, ALICE_FAKE_ROOT=str(self.root), PATH=str(bin_dir) + ':' + os.environ['PATH'])

    def run_capture(self, mode=''):
        return subprocess.run(['sh', str(self.script), str(self.config), str(self.output), str(self.native)],
                              env=dict(self.env, ALICE_FAKE_MODE=mode), capture_output=True, text=True, timeout=25)

    def test_success_binary_not_dumped_to_text(self):
        result = self.run_capture()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ALICE_RECORDING', result.stdout)
        self.assertIn('ALICE_CAPTURE_COMPLETE', result.stdout)
        self.assertIn('=== after ===', result.stdout)
        self.assertEqual(self.output.stat().st_size, 5000)
        self.assertFalse(self.native.exists())
        self.assertNotIn('\x03abc', result.stdout)

    def test_signal_flushes_owned_child(self):
        result = self.run_capture('signal')
        self.assertEqual(result.returncode, 130, result.stdout + result.stderr)
        self.assertIn('ALICE_CLEANUP_OK', result.stdout)
        self.assertIn('=== after ===', result.stdout)
        self.assertNotIn('ALICE_CAPTURE_COMPLETE', result.stdout)

    def test_reject_nonroot(self):
        self.assertEqual(self.run_capture('nonroot').returncode, 2)
        self.assertFalse((self.root / 'called').exists())

    def test_active_trace_untouched(self):
        (self.trace / 'events/enable').write_text('X\n')
        self.assertNotEqual(self.run_capture().returncode, 0)
        self.assertEqual((self.trace / 'events/enable').read_text(), 'X\n')
        self.assertFalse((self.root / 'called').exists())

    def test_active_atrace_untouched(self):
        self.assertNotEqual(self.run_capture('active_prop').returncode, 0)
        self.assertFalse((self.root / 'called').exists())

    def test_start_failure(self):
        result = self.run_capture('start_failure')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('ALICE_CAPTURE_COMPLETE', result.stdout)

    def test_existing_native_output_never_overwritten(self):
        self.native.write_bytes(b'KEEP')
        result = self.run_capture()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.native.read_bytes(), b'KEEP')
        self.assertFalse((self.root / 'called').exists())

    def test_copy_failure_preserves_native_output(self):
        (self.root / 'bin/cp').symlink_to(self.root / 'bin/mock')
        result = self.run_capture()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.native.exists())
        self.assertIn('Native trace retained', result.stdout)

    def test_cleanup_failure_not_success(self):
        result = self.run_capture('cleanup_failure')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ALICE_CLEANUP_UNCONFIRMED', result.stdout)
        self.assertNotIn('ALICE_CAPTURE_COMPLETE', result.stdout)

    def test_missing_required_events(self):
        result = self.run_capture('missing_events')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('ALICE_CAPTURE_COMPLETE', result.stdout)

    def test_config_bounded_local_only(self):
        config = CONFIG.read_text()
        for value in ('duration_ms: 60000', 'write_into_file: true',
                      'file_write_period_ms: 1000', 'max_file_size_bytes: 268435456',
                      'buffer_size_kb: 2048', 'drain_period_ms: 100'):
            self.assertIn(value, config)
        for bad in ('android_report_config', 'incident_report_config', 'deferred_start', 'output_path:'):
            self.assertNotIn(bad, config)
        script = SCRIPT.read_text()
        for bad in ('setenforce', 'setprop ', 'pkill ', 'killall ', 'echo 0 >', 'atrace --async'):
            self.assertNotIn(bad, script)


if __name__ == '__main__':
    unittest.main()
