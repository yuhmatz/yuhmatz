#!/usr/bin/env python3
"""
recon_scanner.py — White Hat Lab reconnaissance & scanning demonstrator.

WHAT THIS IS
------------
An educational utility that simulates the Scanning phase of a penetration test
against your OWN local lab. It:

  1. Verifies the target resolves to a loopback address (hard safety guard).
  2. TCP-connect scans a list of common web service ports.
  3. Sends an HTTP request to each open port and collects response headers.
  4. Fingerprints the service and flags missing security headers.
  5. Performs light content discovery using a small, safe wordlist.
  6. Prints a readable terminal report (or JSON with --json).

SAFETY / LEGAL
--------------
This script REFUSES to scan anything that is not a loopback address. Port
scanning a host you do not own or lack written authorization to test is illegal
in many jurisdictions (e.g. the US CFAA, the UK Computer Misuse Act). The guard
is intentional and should not be removed.

USAGE
-----
    python3 tools/recon_scanner.py http://127.0.0.1:3000
    python3 tools/recon_scanner.py 127.0.0.1 --ports 80,443,3000,8080
    python3 tools/recon_scanner.py http://localhost:3000 --json

Standard library only — no dependencies to install.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse

# Ports commonly used by web services in development and production.
DEFAULT_PORTS = [80, 443, 3000, 5000, 8000, 8080, 8443]

# A deliberately small, harmless wordlist. Real content discovery uses lists with
# tens of thousands of entries; we keep this tiny so the lab stays gentle and fast.
COMMON_PATHS = [
    "/",
    "/api/health",
    "/admin",
    "/admin-backup",
    "/backup",
    "/.env",
    "/robots.txt",
    "/login",
]

# Security headers whose ABSENCE is worth reporting as a finding.
SECURITY_HEADERS = {
    "Content-Security-Policy": "Mitigates XSS and data-injection attacks",
    "X-Content-Type-Options": "Stops MIME-type sniffing (nosniff)",
    "X-Frame-Options": "Prevents clickjacking via framing",
    "Strict-Transport-Security": "Forces HTTPS (HTTPS deployments only)",
    "Referrer-Policy": "Controls how much referrer data leaks",
}


# --------------------------------------------------------------------------- #
# Terminal colours (disabled automatically when output is piped to a file)
# --------------------------------------------------------------------------- #
class C:
    enabled = sys.stdout.isatty()

    @classmethod
    def _w(cls, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if cls.enabled else text

    @classmethod
    def bold(cls, t): return cls._w("1", t)
    @classmethod
    def dim(cls, t): return cls._w("2", t)
    @classmethod
    def red(cls, t): return cls._w("31", t)
    @classmethod
    def green(cls, t): return cls._w("32", t)
    @classmethod
    def yellow(cls, t): return cls._w("33", t)
    @classmethod
    def blue(cls, t): return cls._w("34", t)
    @classmethod
    def cyan(cls, t): return cls._w("36", t)


@dataclass
class PortResult:
    port: int
    open: bool
    scheme: str = "http"
    status: int | None = None
    server: str | None = None
    powered_by: str | None = None
    headers: dict = field(default_factory=dict)
    missing_security_headers: list = field(default_factory=list)
    discovered_paths: list = field(default_factory=list)
    error: str | None = None


# --------------------------------------------------------------------------- #
# Safety guard
# --------------------------------------------------------------------------- #
def parse_target(raw: str) -> tuple[str, int | None]:
    """Accept either a bare host ('127.0.0.1') or a URL ('http://127.0.0.1:3000')."""
    if "://" in raw:
        parsed = urlparse(raw)
        return (parsed.hostname or "", parsed.port)
    if raw.count(":") == 1 and not raw.startswith("["):
        host, _, port = raw.partition(":")
        return (host, int(port) if port.isdigit() else None)
    return (raw, None)


def assert_loopback(host: str) -> str:
    """
    Resolve `host` and refuse to continue unless every resolved address is a
    loopback address. This is the script's core safety control.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        fail(f"Could not resolve host '{host}': {exc}")

    addresses = {info[4][0] for info in infos}
    for addr in addresses:
        try:
            ip = ipaddress.ip_address(addr.split("%")[0])  # strip zone id if present
        except ValueError:
            fail(f"Unrecognised address '{addr}' for host '{host}'.")
        if not ip.is_loopback:
            fail(
                f"Refusing to scan '{host}' — it resolves to {addr}, which is NOT a "
                "loopback address.\n"
                "        This tool only scans your own machine (127.0.0.1 / ::1).\n"
                "        Scanning systems you do not own or are not authorized to "
                "test is illegal."
            )
    return sorted(addresses)[0]


def fail(message: str) -> None:
    print(f"\n{C.red('[ABORT]')} {message}\n", file=sys.stderr)
    sys.exit(2)


# --------------------------------------------------------------------------- #
# Scanning
# --------------------------------------------------------------------------- #
def scan_port(host: str, port: int, timeout: float) -> bool:
    """A plain TCP connect scan: if the handshake completes, the port is open."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((host, port)) == 0
    except OSError:
        return False


def fetch_headers(host: str, port: int, timeout: float) -> tuple[str, int | None, dict, str | None]:
    """
    Issue a GET to the service and return (scheme, status, headers, error).
    Tries HTTPS on the conventional TLS ports, HTTP otherwise.
    """
    scheme = "https" if port in (443, 8443) else "http"
    display_host = f"[{host}]" if ":" in host else host
    url = f"{scheme}://{display_host}:{port}/"

    req = urllib.request.Request(url, headers={"User-Agent": "WhiteHatLab-ReconScanner/1.0"})
    try:
        # Note: for HTTPS against a local lab we do not need certificate pinning;
        # urllib's default context is used, so self-signed certs will error out
        # and simply be reported — which is itself useful reconnaissance data.
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return scheme, resp.status, dict(resp.headers), None
    except urllib.error.HTTPError as exc:
        # A 4xx/5xx still carries headers worth fingerprinting.
        return scheme, exc.code, dict(exc.headers or {}), None
    except Exception as exc:  # URLError, ssl errors, timeouts
        return scheme, None, {}, f"{type(exc).__name__}: {exc}"


def discover_paths(host: str, port: int, scheme: str, timeout: float) -> list:
    """Light content discovery — reports paths that do not return 404."""
    found = []
    display_host = f"[{host}]" if ":" in host else host
    for path in COMMON_PATHS:
        url = f"{scheme}://{display_host}:{port}{path}"
        req = urllib.request.Request(
            url, method="GET", headers={"User-Agent": "WhiteHatLab-ReconScanner/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                found.append({"path": path, "status": resp.status,
                              "length": len(resp.read(2048))})
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                found.append({"path": path, "status": exc.code, "length": 0})
        except Exception:
            pass  # connection-level failures are not interesting here
    return found


def analyse(host: str, ports: list, timeout: float, do_discovery: bool) -> list:
    results = []
    for port in ports:
        is_open = scan_port(host, port, timeout)
        result = PortResult(port=port, open=is_open)
        if is_open:
            scheme, status, headers, error = fetch_headers(host, port, timeout)
            result.scheme = scheme
            result.status = status
            result.headers = headers
            result.error = error
            result.server = headers.get("Server")
            result.powered_by = headers.get("X-Powered-By")
            if status is not None:
                result.missing_security_headers = [
                    h for h in SECURITY_HEADERS if h not in headers
                ]
                if do_discovery:
                    result.discovered_paths = discover_paths(host, port, scheme, timeout)
        results.append(result)
    return results


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def print_report(target: str, host: str, results: list) -> None:
    line = "=" * 66
    print()
    print(C.cyan(line))
    print(C.cyan(C.bold("  WHITE HAT LAB — RECON SCANNER")))
    print(C.cyan("  Reconnaissance & Scanning phase demonstration"))
    print(C.cyan(line))
    print(f"  {C.bold('Target'):<22} {target}")
    print(f"  {C.bold('Resolved address'):<22} {host}  {C.green('(loopback — authorized)')}")
    print(f"  {C.bold('Ports probed'):<22} {len(results)}")
    print(C.cyan(line))

    open_ports = [r for r in results if r.open]

    print(f"\n{C.bold('PORT SCAN')}")
    print(C.dim("  PORT      STATE     SERVICE"))
    for r in results:
        if r.open:
            svc = r.server or ("HTTPS" if r.scheme == "https" else "HTTP")
            print(f"  {r.port:<9} {C.green('open'):<18} {svc}")
        else:
            print(C.dim(f"  {r.port:<9} closed"))

    if not open_ports:
        print(f"\n{C.yellow('No open ports found.')} Is the lab server running? (npm start)\n")
        return

    for r in open_ports:
        print(f"\n{C.bold(f'SERVICE DETAIL — port {r.port} ({r.scheme})')}")
        if r.error:
            print(f"  {C.yellow('!')} Could not complete HTTP request: {r.error}")
            continue

        print(f"  HTTP status        {r.status}")
        print(f"  Server             {r.server or C.dim('(not disclosed)')}")
        print(f"  X-Powered-By       {r.powered_by or C.dim('(not disclosed)')}")

        if r.headers:
            print(f"\n  {C.bold('Response headers')}")
            for k, v in sorted(r.headers.items()):
                print(f"    {C.blue(k)}: {v}")

        if r.missing_security_headers:
            print(f"\n  {C.bold('Missing security headers')} {C.dim('(hardening opportunities)')}")
            for h in r.missing_security_headers:
                print(f"    {C.yellow('!')} {h:<28} {C.dim(SECURITY_HEADERS[h])}")
        else:
            print(f"\n  {C.green('All checked security headers present.')}")

        if r.discovered_paths:
            print(f"\n  {C.bold('Content discovery')} {C.dim('(non-404 responses)')}")
            for p in r.discovered_paths:
                flag = C.red("  <-- sensitive?") if p["path"] in ("/admin-backup", "/.env", "/backup") else ""
                print(f"    {p['status']}  {p['path']}{flag}")

    print(f"\n{C.cyan(line)}")
    print(f"  {C.bold('NEXT STEPS')} — feed this into the methodology:")
    print("    Stage 3 Enumeration          dig into each discovered path")
    print("    Stage 4 Vulnerability Assess. test the endpoints in the Training Environment")
    print("    Stage 8 Reporting            write findings up in the Report Generator")
    print(C.cyan(line))
    print(C.dim("  Educational use only. Local scope only. Do no harm.\n"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="White Hat Lab recon scanner — loopback targets only.",
        epilog="Example: python3 tools/recon_scanner.py http://127.0.0.1:3000",
    )
    parser.add_argument("target", nargs="?", default="http://127.0.0.1:3000",
                        help="Localhost URL or host (default: http://127.0.0.1:3000)")
    parser.add_argument("--ports", help="Comma-separated port list (default: common web ports)")
    parser.add_argument("--timeout", type=float, default=1.5, help="Per-connection timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--no-discovery", action="store_true", help="Skip content discovery")
    args = parser.parse_args()

    host, url_port = parse_target(args.target)
    if not host:
        fail(f"Could not parse a host from '{args.target}'.")

    # SAFETY GUARD — refuse non-loopback targets.
    resolved = assert_loopback(host)

    if args.ports:
        try:
            ports = sorted({int(p) for p in args.ports.split(",") if p.strip()})
        except ValueError:
            fail("--ports must be a comma-separated list of integers.")
    else:
        ports = sorted(set(DEFAULT_PORTS + ([url_port] if url_port else [])))

    results = analyse(resolved, ports, args.timeout, not args.no_discovery)

    if args.json:
        print(json.dumps(
            {"target": args.target, "resolved": resolved,
             "results": [asdict(r) for r in results]},
            indent=2,
        ))
    else:
        print_report(args.target, resolved, results)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
