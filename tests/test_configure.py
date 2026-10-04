import hashlib
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'configure.py'
spec = importlib.util.spec_from_file_location('configure', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AccountBinding(unittest.TestCase):
    def test_only_fingerprint_is_copied_from_login(self):
        template = {'times': ['08:30', '14:00', '19:30'], 'model': 'example-model'}
        auth = {'tokens': {'account_id': 'test-account', 'access_token': 'private-test-token'}}
        result = module.configuration(template, auth, '/example/codex', '/example/home', '/usr/bin')
        self.assertEqual(result['account_fingerprint'], hashlib.sha256(b'test-account').hexdigest())
        self.assertNotIn('tokens', result)
        self.assertNotIn('private-test-token', str(result))
        self.assertNotIn('account_fingerprint', template)

    def test_api_key_login_is_rejected(self):
        with self.assertRaises(ValueError):
            module.configuration({}, {'tokens': {'account_id': 'test'}, 'OPENAI_API_KEY': 'fake-test-key'},
                                 '/example/codex', '/example/home', '/usr/bin')

    def test_missing_account_is_rejected(self):
        with self.assertRaises(ValueError):
            module.configuration({}, {'tokens': {}}, '/example/codex', '/example/home', '/usr/bin')


if __name__ == '__main__':
    unittest.main()
