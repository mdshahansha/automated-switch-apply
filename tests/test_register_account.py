import unittest

from tests.mock_portal.server import serve
from tools.register_account import is_local, run


class RegisterAccountTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = serve()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_creates_and_verifies(self):
        out = run(self.base + "/register")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["status"], {"exists": True, "verified": True})
        steps = [e["step"] for e in out["log"]]
        self.assertEqual(steps, ["open", "inspect", "submit", "verification_email", "verify", "confirm"])

    def test_recovers_from_weak_password(self):
        out = run(self.base + "/register", weak_first=True)
        self.assertTrue(out["ok"], out)
        self.assertIn("recover", [e["step"] for e in out["log"]])

    def test_duplicate_detected(self):
        email = "dup@example.test"
        self.assertTrue(run(self.base + "/register", email=email)["ok"])
        out = run(self.base + "/register", email=email)
        self.assertEqual(out["result"], "duplicate")
        self.assertTrue(out["status"]["exists"])

    def test_password_never_in_output(self):
        out = run(self.base + "/register")
        self.assertNotIn("password", str([e for e in out["log"] if e["step"] == "submit"]).lower().replace("password needs", ""))

    def test_refuses_real_portals(self):
        for url in ("https://app.flexiple.com/signup", "https://barclays.wd3.myworkdayjobs.com/x", "http://127.0.0.1.evil.com/"):
            self.assertFalse(is_local(url), url)
            self.assertEqual(run(url)["result"], "refused_non_local")


if __name__ == "__main__":
    unittest.main()
