import unittest
from host.network import HostEndpoint


class NetworkEndpointTests(unittest.TestCase):
    def test_endpoint_serialization(self):
        endpoint = HostEndpoint("192.168.1.50", 8765)
        self.assertEqual(endpoint.as_dict(), {
            "host": "192.168.1.50",
            "port": 8765,
            
        })


if __name__ == "__main__":
    unittest.main()
