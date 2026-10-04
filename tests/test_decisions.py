import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'prewarm.py'
spec = importlib.util.spec_from_file_location('prewarm', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Decisions(unittest.TestCase):
    def test_old_window_is_active(self):
        self.assertEqual(module.window_state({'reset': 9000, 'observed_at': 1000}), 'active')

    def test_idle_projection_is_not_confirmation(self):
        first = {'observed_at': 1000, 'reset': 19000}
        second = {'observed_at': 1015, 'reset': 19015}
        self.assertEqual(module.window_state(first, second), 'idle')
        self.assertFalse(module.stable_new_window(first, first, second, 1000, 1002))

    def test_zero_percent_can_still_be_active(self):
        first = {'observed_at': 1000, 'reset': 19000, 'used': 0}
        second = {'observed_at': 1015, 'reset': 19000, 'used': 0}
        self.assertEqual(module.window_state(first, second), 'active')

    def test_only_a_new_fixed_reset_is_success(self):
        old = {'observed_at': 1000, 'reset': 999}
        first = {'observed_at': 1010, 'reset': 19000}
        second = {'observed_at': 1025, 'reset': 19000}
        self.assertTrue(module.stable_new_window(old, first, second, 1000, 1002))
        self.assertFalse(module.stable_new_window(first, first, second, 1000, 1002))

    def test_idle_projection_can_equal_real_anchor(self):
        old = {'observed_at': 1000, 'reset': 19000, 'window_state': 'idle'}
        first = {'observed_at': 1010, 'reset': 19000}
        second = {'observed_at': 1025, 'reset': 19000}
        self.assertTrue(module.stable_new_window(old, first, second, 1000, 1002))

    def test_missing_or_far_future_reset_does_not_pass(self):
        old = {'observed_at': 1000, 'reset': 999}
        first = {'observed_at': 1010, 'reset': 25000}
        self.assertFalse(module.stable_new_window(old, first, first, 1000, 1002))

    def test_all_three_slots_and_late_wake(self):
        import datetime as dt
        for hour, minute in ((8,30),(14,0),(19,30)):
            current = dt.datetime(2026,10,5,hour,minute,tzinfo=module.ZONE)
            self.assertIsNotNone(module.slot_at(current))
            self.assertIsNone(module.slot_at(current + dt.timedelta(minutes=31)))


if __name__ == '__main__':
    unittest.main()
