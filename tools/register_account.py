"""Test-account registration runner for local mock portals.

Drives a registration flow end to end: open the page, inspect the form, fill
synthetic data, submit, read the result, recover from a rejected password or a
duplicate email, follow the simulated verification email, and confirm the
account through the portal's own status signal.

Scope is deliberately limited to local development hosts (127.0.0.1,
localhost, ::1, *.localhost, *.test). Real third-party portals are refused:
creating accounts there is the candidate's own step (see apply.md Step 7.4).

    python3 tools/register_account.py --url http://127.0.0.1:8799/register
    python3 tools/register_account.py --url ... --email taken@example.test   # exercise duplicate path

Output: one JSON evidence object on stdout. The generated password is never
printed or written to disk.
"""

import argparse
import json
import re
import secrets
import string
import sys
import time
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def is_local(url):
    host = (urlparse(url).hostname or "").lower()
    return host in LOCAL_HOSTS or host.endswith(".localhost") or host.endswith(".test")


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.form = None
        self.fields = []
        self.messages = []
        self._msg = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form" and self.form is None:
            self.form = a
        elif tag == "input" and self.form is not None:
            self.fields.append(a)
        elif tag == "p" and a.get("class") in ("error", "success"):
            self._msg = {"kind": a["class"], "code": a.get("data-code") or a.get("data-status"), "text": ""}

    def handle_data(self, data):
        if self._msg is not None:
            self._msg["text"] += data

    def handle_endtag(self, tag):
        if tag == "p" and self._msg is not None:
            self._msg["text"] = self._msg["text"].strip()
            self.messages.append(self._msg)
            self._msg = None


def parse(html):
    p = FormParser()
    p.feed(html)
    return p


def http(method, url, data=None):
    body = urlencode(data).encode() if data is not None else None
    req = Request(url, data=body, method=method, headers={"User-Agent": "register_account-test/1"})
    try:
        with urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except HTTPError as e:
        with e:
            return e.code, e.read().decode()


def strong_password(n=16):
    pools = [string.ascii_uppercase, string.ascii_lowercase, string.digits, "!@#$%^&*-_"]
    chars = [secrets.choice(p) for p in pools]
    chars += [secrets.choice("".join(pools)) for _ in range(n - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def fill(fields, identity, password):
    values = {}
    for f in fields:
        name, ftype = f.get("name"), (f.get("type") or "text").lower()
        if not name:
            continue
        if ftype == "checkbox":
            values[name] = f.get("value", "on")
        elif ftype == "password":
            values[name] = password
        elif ftype == "email" or "email" in name:
            values[name] = identity["email"]
        elif "name" in name:
            values[name] = identity["full_name"]
    return values


def run(url, email=None, name="Test Candidate", weak_first=False, log=None):
    log = log if log is not None else []
    step = lambda s, **kw: log.append({"t": round(time.time(), 3), "step": s, **kw})
    if not is_local(url):
        step("refused", reason="not a local development host", host=urlparse(url).hostname)
        return {"ok": False, "result": "refused_non_local", "log": log}

    identity = {"full_name": name, "email": (email or f"candidate+{secrets.token_hex(4)}@example.test").lower()}
    code, html = http("GET", url)
    step("open", status=code)
    page = parse(html)
    if not page.form:
        step("inspect", error="no form found")
        return {"ok": False, "result": "no_form", "log": log}
    step("inspect", action=page.form.get("action"), fields=[f.get("name") for f in page.fields])
    action = urljoin(url, page.form.get("action") or url)

    password = "short1" if weak_first else strong_password()
    for attempt in range(1, 4):
        code, html = http("POST", action, fill(page.fields, identity, password))
        msgs = parse(html).messages
        step("submit", attempt=attempt, status=code, messages=msgs)
        if code == 201:
            break
        if code == 409 or any(m["code"] == "duplicate" for m in msgs):
            status = json.loads(http("GET", urljoin(url, "/status?" + urlencode({"email": identity["email"]})))[1])
            step("duplicate", existing=status)
            return {"ok": False, "result": "duplicate", "email": identity["email"], "status": status, "log": log}
        if code == 422 and any("Password" in m["text"] for m in msgs):
            password = strong_password()
            step("recover", action="regenerated password to satisfy policy")
            continue
        return {"ok": False, "result": "rejected", "log": log}
    else:
        return {"ok": False, "result": "gave_up", "log": log}

    mails = json.loads(http("GET", urljoin(url, "/_outbox?" + urlencode({"to": identity["email"]})))[1])
    step("verification_email", count=len(mails))
    if not mails:
        return {"ok": False, "result": "no_verification_email", "log": log}
    code, html = http("GET", urljoin(url, mails[-1]["link"]))
    step("verify", status=code, messages=parse(html).messages)

    status = json.loads(http("GET", urljoin(url, "/status?" + urlencode({"email": identity["email"]})))[1])
    step("confirm", status=status)
    ok = status.get("exists") and status.get("verified")
    return {"ok": bool(ok), "result": "created_and_verified" if ok else "unverified",
            "email": identity["email"], "status": status, "log": log}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--email")
    ap.add_argument("--name", default="Test Candidate")
    ap.add_argument("--weak-first", action="store_true", help="submit a weak password first to exercise recovery")
    a = ap.parse_args()
    out = run(a.url, a.email, a.name, a.weak_first)
    print(json.dumps(out, indent=2))
    sys.exit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
