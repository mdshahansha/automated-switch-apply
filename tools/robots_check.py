#!/usr/bin/env python3
"""Decide whether the identifying GET retry in 09-web-research.md may run.

The retry reads public pages only when robots.txt permits access. It uses the
repository's honest tool User-Agent, never a browser identity or a policy bypass.

Claude-User exclusions are retained for the WebFetch workflow as well as wildcard
and actual-tool exclusions. A policy that cannot be read with the identifying
User-Agent leaves permission unconfirmed; no alternate identity is tried.

Rules implemented (RFC 9309), deliberately on the cautious side:
  * longest-match wins; on equal specificity Disallow wins
  * a Disallow for "*", "Claude-User" or "automated-switch-apply" blocks the retry
  * blank lines inside a record do not end it (Python's robotparser drops
    rules in that case, which fails open - see tests)
  * one leading UTF-8 byte-order mark is skipped (left in, it hides a first
    "User-agent" line and drops that whole group, which fails open)
  * 404 means no published robots policy; other access rules still apply
  * any other failure to read robots.txt leaves permission unconfirmed,
    and the retry does not happen - including a User-agent, Allow or
    Disallow line holding U+FFFD, i.e. a byte that is not valid UTF-8

Usage:  python3 tools/robots_check.py <url>
Exit 0 = the retry may proceed. Exit 1 = do not retry; go to escalation step 3.
"""

import re, subprocess, sys
from urllib.parse import urlsplit, unquote

USER_AGENT = 'mdshahansha/automated-switch-apply/1.0 (web-research)'

def _fetch(url, ua):
    """curl, not urllib: some hosts (jobup.ch) hang urllib indefinitely while
    answering curl in under a second, and --max-time is a hard ceiling."""
    # "--" terminates option parsing, so a URL beginning with a dash can never
    # be read by curl as a flag. gate() rebuilds the target as
    # scheme://host/robots.txt before calling here, so this is hardening for
    # direct callers rather than a hole in the gate path itself.
    r = subprocess.run(
        ['curl', '-sS', '-L', '--max-redirs', '5', '--max-time', '12', '-A', ua,
         '-H', 'Accept: text/plain,*/*', '-w', '\n%{http_code}', '--', url],
        # robots.txt is UTF-8 (RFC 9309). Unpinned, Turkish Windows decoded it as
        # cp1254, where bytes like 0x81 are undefined: the pipe reader thread died,
        # stdout came back None, and tr.indeed.com read as UNCONFIRMED.
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
    if r.returncode != 0:
        raise RuntimeError('curl exit %d' % r.returncode)
    body, _, code = r.stdout.rpartition('\n')
    return body, int(code or 0)


def is_robots_body(text):
    """Does this actually look like a robots.txt?

    A misconfigured host can answer /robots.txt with 200 and an HTML error page.
    That body parses to zero rules, and zero rules read as "allowed" - so a
    soft-200 granted permission that was never given. An empty or whitespace-only
    body IS a valid allow-all under RFC 9309 and stays allowed; a non-empty body
    with no recognised directive is treated as unreadable.
    """
    text = text.removeprefix('\ufeff')          # byte-order mark, see _groups
    if not text.strip():
        return True
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip().lower()
        if ':' in line and line.split(':', 1)[0].strip() in (
            'user-agent', 'allow', 'disallow', 'sitemap', 'crawl-delay', 'host',
        ):
            return True
    return False

def has_undecodable_rule(text):
    """Does a User-agent, Allow or Disallow line hold U+FFFD?

    U+FFFD stands in for a byte that did not decode as UTF-8. A non-conformant
    robots.txt saved in a legacy code page (cp1254, ISO-8859-9) with raw
    non-ASCII bytes in a rule yields a pattern that can never match: the rule
    was silently skipped and the path read as allowed. Such a body is
    unreadable, not permissive. The field is named with U+FFFD removed, so a
    stray byte before "Disallow" cannot hide the line. U+FFFD in a comment or
    in any other field (Sitemap, Crawl-delay, ...) decides nothing and is
    ignored.
    """
    for raw in text.removeprefix('\ufeff').splitlines():
        line = raw.split('#', 1)[0]
        if '\ufffd' in line and ':' in line:
            field = line.split(':', 1)[0].replace('\ufffd', '').strip().lower()
            if field in ('user-agent', 'allow', 'disallow'):
                return True
    return False

def _groups(text):
    """user-agent -> [(is_allow, pattern)], tolerating blank lines inside a record.

    One leading U+FEFF is skipped, as Google's reference parser does. A file
    saved with a UTF-8 byte-order mark otherwise hid its first field: a leading
    "User-agent: *" went unseen, every rule in its group was dropped for want
    of an agent, and "Disallow: /" read as allow-all.
    """
    out, agents, expect = {}, [], True
    for raw in text.removeprefix('\ufeff').splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line or ':' not in line:
            continue
        field, _, value = line.partition(':')
        field, value = field.strip().lower(), value.strip()
        if field == 'user-agent':
            if not expect:
                agents, expect = [], True
            agents.append(value.lower())
            out.setdefault(value.lower(), [])
        elif field in ('allow', 'disallow') and agents:
            expect = False
            for a in agents:
                out[a].append((field == 'allow', value))
    return out

def _match(pattern, path):
    """RFC 9309 wildcard match; returns match length or -1.

    The pattern is percent-decoded to match the already-decoded path. Without
    this, "Disallow: /foo%20bar" never matched "/foo bar" and the rule was
    silently skipped - a fail-open on any site that encodes its own rules.
    Under RFC 9309 section 2.2.2, '$' anchors the end of the URL only when
    at the end of the pattern; mid-pattern '$' is matched literally.
    """
    if pattern == '':
        return -1
    pattern = unquote(pattern)
    end_anchor = pattern.endswith('$')
    pat = pattern[:-1] if end_anchor else pattern
    rx = '^' + ''.join('.*' if c == '*' else re.escape(c) for c in pat) + ('$' if end_anchor else '')
    return len(pattern) if re.match(rx, path) else -1

def allowed(text, agent, path):
    g = _groups(text)
    rules = g.get(agent.lower()) or g.get('*') or []
    best_len, best_allow = -1, True
    for is_allow, pat in rules:
        n = _match(pat, path)
        if n > best_len or (n == best_len and n >= 0 and not is_allow):
            best_len, best_allow = n, is_allow      # ties -> Disallow wins (cautious)
    return True if best_len < 0 else best_allow

def gate(url):
    parts = urlsplit(url)
    path = unquote(parts.path) or '/'
    if parts.query:
        path += '?' + unquote(parts.query)
    robots = f'{parts.scheme}://{parts.netloc}/robots.txt'
    try:
        text, code = _fetch(robots, USER_AGENT)
    except Exception as e:
        return 1, 'UNCONFIRMED (%s) - do not retry, go to step 3' % type(e).__name__
    if code == 404:
        return 0, 'ALLOWED - no robots.txt published'
    if code != 200:
        return 1, 'UNCONFIRMED (HTTP %d) - do not retry, go to step 3' % code
    if not is_robots_body(text):
        return 1, 'UNCONFIRMED (HTTP 200 but the body is not a robots.txt) - do not retry, go to step 3'
    if has_undecodable_rule(text):
        return 1, 'UNCONFIRMED (HTTP 200 but a User-agent/Allow/Disallow line is not valid UTF-8) - do not retry, go to step 3'
    for a in ('Claude-User', '*', 'automated-switch-apply'):
        if not allowed(text, a, path):
            return 1, f'DISALLOWED for {a} - do not retry, go to step 3'
    return 0, 'ALLOWED - robots.txt permits this path'

def _force_utf8_output() -> None:
    """Write UTF-8 whatever the host's default encoding is.

    A piped stdout on Windows defaults to the ANSI code page (cp1252 on most
    Western installs), so printing messages or paths outside it raised
    UnicodeEncodeError before the workflow saw any output.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)  # absent on a StringIO under test
        if reconfigure:
            reconfigure(encoding="utf-8")


if __name__ == '__main__':
    _force_utf8_output()
    if len(sys.argv) != 2:
        print('usage: python3 tools/robots_check.py <url>', file=sys.stderr)
        sys.exit(2)
    rc, msg = gate(sys.argv[1])
    print(msg)
    sys.exit(rc)
