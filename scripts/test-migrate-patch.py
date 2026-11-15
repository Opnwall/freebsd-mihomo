#!/usr/bin/env python3
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('migration', Path(__file__).with_name('migrate-patch.py'))
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class MigrationTests(unittest.TestCase):
    def fixture(self, tmp):
        root = Path(tmp)
        source, baseline = root / 'source', root / 'baseline'
        source.mkdir()
        (baseline / 'files').mkdir(parents=True)
        original = ''.join(f'line {i}\n' for i in range(40)).encode()
        desired = original.replace(b'line 20\n', b'TUN implementation\n')
        patch = root / 'test.patch'
        patch.write_text(''.join(difflib.unified_diff(original.decode().splitlines(True), desired.decode().splitlines(True), fromfile='a/test.go', tofile='b/test.go')))
        (source / 'test.go').write_bytes(original)
        (baseline / 'files/test.go').write_bytes(original)
        (baseline / 'manifest.json').write_text(json.dumps({'patch_sha256': hashlib.sha256(patch.read_bytes()).hexdigest(), 'files': {'test.go': hashlib.sha256(original).hexdigest()}}))
        return source, patch, baseline, original, desired

    def test_strict_application(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, patch, baseline, original, desired = self.fixture(tmp)
            output = Path(tmp) / 'output'
            migration.apply(source, patch, baseline, 'core', '1.0.0', output)
            self.assertEqual((source / 'test.go').read_bytes(), desired)
            self.assertFalse((output / 'migrated').exists())

    def test_context_change_three_way_and_regenerated_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, patch, baseline, original, desired = self.fixture(tmp)
            current = original.replace(b'line 17\n', b'upstream context\n')
            (source / 'test.go').write_bytes(current)
            self.assertNotEqual(migration.run_patch(source, patch, dry=True).returncode, 0)
            output = Path(tmp) / 'output'
            migration.apply(source, patch, baseline, 'core', '1.1.0', output)
            merged = (source / 'test.go').read_bytes()
            self.assertIn(b'upstream context', merged)
            self.assertIn(b'TUN implementation', merged)
            self.assertTrue((output / 'migrated').exists())
            (source / 'test.go').write_bytes(current)
            self.assertEqual(migration.run_patch(source, output / 'patches/test.patch').returncode, 0)
            self.assertEqual((source / 'test.go').read_bytes(), merged)

    def test_real_conflict_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, patch, baseline, original, desired = self.fixture(tmp)
            current = original.replace(b'line 20\n', b'upstream incompatible API\n')
            (source / 'test.go').write_bytes(current)
            output = Path(tmp) / 'output'
            with self.assertRaisesRegex(ValueError, 'merge conflict'):
                migration.apply(source, patch, baseline, 'core', '2.0.0', output)
            self.assertEqual((source / 'test.go').read_bytes(), current)
            self.assertFalse((output / 'migrated').exists())

    def test_mismatched_patch_baseline_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, patch, baseline, original, desired = self.fixture(tmp)
            (source / 'test.go').write_bytes(original.replace(b'line 20\n', b'incompatible\n'))
            patch.write_text(patch.read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'do not match'):
                migration.apply(source, patch, baseline, 'core', '2.0.0', Path(tmp) / 'output')


if __name__ == '__main__':
    unittest.main()
