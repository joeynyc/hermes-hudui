import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.api.profile_scope import resolve_profile_scope


class ProfileScopeTests(unittest.TestCase):
    def test_default_profile_resolves_to_base_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('backend.api.profile_scope.default_hermes_dir', return_value=tmp):
                profile, path = resolve_profile_scope('default')

            self.assertEqual(profile, 'default')
            self.assertEqual(path, tmp)

    def test_named_profile_resolves_to_profiles_subdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_dir = Path(tmp) / 'profiles' / 'next'
            profile_dir.mkdir(parents=True)

            with patch('backend.api.profile_scope.default_hermes_dir', return_value=tmp):
                profile, path = resolve_profile_scope('next')

            self.assertEqual(profile, 'next')
            self.assertEqual(path, str(profile_dir))

    def test_missing_profile_raises_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('backend.api.profile_scope.default_hermes_dir', return_value=tmp):
                with self.assertRaises(HTTPException) as ctx:
                    resolve_profile_scope('ghost')

            self.assertEqual(ctx.exception.status_code, 404)


if __name__ == '__main__':
    unittest.main()
