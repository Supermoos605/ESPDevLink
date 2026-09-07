import unittest

from host.network.remote import load_remote_config


class RemoteConfigTests(unittest.TestCase):
    def test_disabled_by_default(self):
        config = load_remote_config({})
        self.assertFalse(config.enabled)
        self.assertIsNone(config.signaling_url)
        self.assertIsNone(config.access_token)

    def test_enabled_requires_url(self):
        with self.assertRaises(ValueError):
            load_remote_config({"ESPLINK_REMOTE_ENABLED": "true"})

    def test_valid_configuration(self):
        config = load_remote_config({
            "ESPLINK_REMOTE_ENABLED": "1",
            "ESPLINK_REMOTE_SIGNALING_URL": "wss://signal.example.test/ws",
            "ESPLINK_REMOTE_ACCESS_TOKEN": "secret",
        })
        self.assertTrue(config.enabled)
        self.assertEqual(config.signaling_url, "wss://signal.example.test/ws")
        self.assertEqual(config.access_token, "secret")

    def test_invalid_url(self):
        with self.assertRaises(ValueError):
            load_remote_config({
                "ESPLINK_REMOTE_SIGNALING_URL": "http://signal.example.test/ws",
            })


if __name__ == "__main__":
    unittest.main()
