import tomllib,unittest
from pathlib import Path
class NetlifyGuestConfigTests(unittest.TestCase):
 def test_static_publish_routes_and_security_headers(self):
  config=tomllib.loads((Path(__file__).resolve().parents[1]/"netlify.toml").read_text())
  self.assertEqual(config["build"]["publish"],"src/nurion_pg/api/guest_ui")
  routes={(x["from"],x["to"],x["status"]) for x in config["redirects"]}
  self.assertIn(("/guest","/index.html",200),routes);self.assertIn(("/guest/payments/*","/detail.html",200),routes);self.assertIn(("/guest/assets/*","/:splat",200),routes)
  headers=config["headers"][0]["values"]
  self.assertEqual(headers["X-Frame-Options"],"DENY");self.assertEqual(headers["Cache-Control"],"no-store");self.assertIn("payment=()",headers["Permissions-Policy"]);self.assertIn("frame-ancestors 'none'",headers["Content-Security-Policy"])
if __name__=="__main__":unittest.main()
