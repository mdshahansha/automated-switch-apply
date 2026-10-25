"""Local mock career portal for testing tools/register_account.py.

Simulates a registration flow: an HTML form, password rules, duplicate-account
handling, a simulated verification email (exposed at /_outbox) and a status
endpoint. State is in memory only. Binds to 127.0.0.1.

    python3 tests/mock_portal/server.py --port 8799
"""

import argparse
import html
import json
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

FORM = """<!doctype html><html><head><title>Mock Careers - Create account</title></head>
<body><h1>Create your candidate account</h1>{msg}
<form id="register" method="post" action="/register">
<label for="full_name">Full name</label><input id="full_name" name="full_name" required>
<label for="email">Email</label><input id="email" name="email" type="email" required>
<label for="password">Password</label><input id="password" name="password" type="password" required>
<label for="confirm_password">Confirm password</label><input id="confirm_password" name="confirm_password" type="password" required>
<label><input name="terms" type="checkbox" value="yes" required> I accept the terms</label>
<button type="submit">Create account</button></form></body></html>"""

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def password_problems(pw):
    problems = []
    if len(pw) < 10:
        problems.append("at least 10 characters")
    if not re.search(r"[A-Z]", pw):
        problems.append("an uppercase letter")
    if not re.search(r"[a-z]", pw):
        problems.append("a lowercase letter")
    if not re.search(r"\d", pw):
        problems.append("a digit")
    if not re.search(r"[^A-Za-z0-9]", pw):
        problems.append("a symbol")
    return problems


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.accounts = {}  # email -> {"name", "verified"}
        self.outbox = []  # simulated emails
        self.tokens = {}  # token -> email


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj), "application/json")

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            if url.path in ("/", "/register"):
                return self._send(200, FORM.format(msg=""))
            if url.path == "/verify":
                token = (q.get("token") or [""])[0]
                with state.lock:
                    email = state.tokens.pop(token, None)
                    if email:
                        state.accounts[email]["verified"] = True
                if not email:
                    return self._send(400, '<p class="error">Invalid or used verification link.</p>')
                return self._send(200, '<p class="success" data-status="verified">Email verified. Account active.</p>')
            if url.path == "/_outbox":
                to = (q.get("to") or [""])[0].lower()
                with state.lock:
                    mails = [m for m in state.outbox if m["to"] == to]
                return self._json(200, mails)
            if url.path == "/status":
                email = (q.get("email") or [""])[0].lower()
                with state.lock:
                    acct = state.accounts.get(email)
                return self._json(200, {"exists": bool(acct), "verified": bool(acct and acct["verified"])})
            return self._send(404, "not found")

        def do_POST(self):
            if urlparse(self.path).path != "/register":
                return self._send(404, "not found")
            length = int(self.headers.get("Content-Length") or 0)
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode()).items()}
            name = form.get("full_name", "").strip()
            email = form.get("email", "").strip().lower()
            pw = form.get("password", "")
            errors = []
            if not name:
                errors.append("Full name is required.")
            if not EMAIL_RE.match(email):
                errors.append("Enter a valid email.")
            probs = password_problems(pw)
            if probs:
                errors.append("Password needs " + ", ".join(probs) + ".")
            if pw != form.get("confirm_password", ""):
                errors.append("Passwords do not match.")
            if form.get("terms") != "yes":
                errors.append("You must accept the terms.")
            if errors:
                msg = "".join(f'<p class="error">{html.escape(e)}</p>' for e in errors)
                return self._send(422, FORM.format(msg=msg))
            with state.lock:
                if email in state.accounts:
                    return self._send(409, FORM.format(msg='<p class="error" data-code="duplicate">An account with this email already exists.</p>'))
                state.accounts[email] = {"name": name, "verified": False}
                token = secrets.token_urlsafe(16)
                state.tokens[token] = email
                state.outbox.append({"to": email, "subject": "Verify your email", "link": f"/verify?token={token}"})
            return self._send(201, '<p class="success" data-status="pending_verification">Account created. Check your email to verify.</p>')

    return Handler


def serve(port=0):
    """Start the mock portal in a background thread; returns (server, base_url)."""
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(State()))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8799)
    args = ap.parse_args()
    srv, base = serve(args.port)
    print(f"mock portal on {base}", flush=True)
    threading.Event().wait()
