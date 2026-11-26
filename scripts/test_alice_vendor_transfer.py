#!/usr/bin/env python3
"""Full OTA decoding regressions: zero/erase ranges are not Brotli payload."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from alice_vendor_merge import B, filesystem, transfer_commands, unpack


class TransferTest(unittest.TestCase):
    def test_zero_ranges_do_not_consume_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tl = root / "vendor.transfer.list"
            tl.write_text("4\n4\n0\n0\nerase 2,4,7\nnew 2,3,4\nnew 2,0,1\nzero 2,1,3\n")
            payload = b"B" * B + b"A" * B
            def decompress(*args, **kwargs):
                (root / "base.dat").write_bytes(payload)
            with patch("alice_vendor_merge.run", side_effect=decompress):
                unpack(root / "input.br", tl, root / "output.img", root)
            self.assertEqual((root / "output.img").read_bytes(), b"A" * B + bytes(2*B) + b"B" * B + bytes(3*B))

    def test_reject_malformed_and_incremental_lists(self):
        cases = ["", "4\n1\n0\n0\n", "4\n1\n1\n1\nnew 2,0,1\n",
                 "4\n1\n0\n0\nmove 2,0,1\n", "4\n3\n0\n0\nnew 4,0,2,1,2\n",
                 "4\n1\n0\n0\nnew 2,0,2\n", "4\n1\n0\n0\nnew 2,0,1\nnew 2,0,1\n"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transfer.list"
            for contents in cases:
                with self.subTest(contents=contents):
                    path.write_text(contents)
                    with self.assertRaises(ValueError):
                        transfer_commands(path)

    def test_detect_erofs_and_ext4(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image"
            for magic, offset, kind in ((bytes.fromhex("e2e1f5e0"), 1024, "erofs"),
                                        (bytes.fromhex("53ef"), 1080, "ext4")):
                contents = bytearray(4096)
                contents[offset:offset+len(magic)] = magic
                path.write_bytes(contents)
                self.assertEqual(filesystem(path), kind)
            path.write_bytes(bytes(4096))
            with self.assertRaises(ValueError):
                filesystem(path)


if __name__ == "__main__":
    unittest.main()
