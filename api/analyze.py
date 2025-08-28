import sys
import json
import subprocess
from urllib.parse import unquote
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        # Parse the query string: ?url=<encoded>
        query = self.path.split("?url=", 1)
        if len(query) < 2:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing url param")
            return

        url = unquote(query[1])

        try:
            # Call your existing newsanalyzer.py with subprocess
            result = subprocess.check_output(
                [sys.executable, "newsanalyzer.py", url],
                stderr=subprocess.STDOUT
            ).decode("utf-8")

            # Send JSON back
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"result": result}).encode("utf-8"))

        except subprocess.CalledProcessError as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(
                json.dumps({"error": e.output.decode("utf-8")}).encode("utf-8")
            )
