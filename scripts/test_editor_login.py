#!/usr/bin/env python3
"""Render the login with the actual pinned gateway, without network or real credentials."""
import argparse
import base64
import html.parser
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "quay.io/oauth2-proxy/oauth2-proxy@sha256:aa0bd8dd5ab0c78e4c91c92755ad573a5f92241f88138b4141b8ec803463b4fd"


class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("editor.example.invalid", timeout=5)
        self.path = str(path)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class Page(html.parser.HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.forms = []
        self.inputs = []
        self.scripts = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "form":
            self.forms.append(attributes)
        if tag == "input":
            self.inputs.append(attributes)
        if tag == "script" or any(key.lower().startswith("on") for key in attributes):
            self.scripts.append(tag)


def request(path, route):
    connection = UnixHTTP(path)
    try:
        connection.request("GET", route)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read().decode()
    finally:
        connection.close()


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", type=Path)
    args = parser.parse_args()
    name = "n8n-login-test-" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix="n8n-login-test-") as temp:
        work = Path(temp)
        endpoint = work / "gateway.sock"
        command = [
            "docker", "run", "--detach", "--name", name, "--network", "none",
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "--mount", f"type=bind,src={work},dst=/work",
            "--mount", f"type=bind,src={ROOT / 'orbit/login'},dst=/templates,readonly",
            IMAGE, "--provider=keycloak-oidc", "--oidc-issuer-url=https://issuer.example.invalid",
            "--skip-oidc-discovery=true", "--login-url=https://issuer.example.invalid/auth",
            "--redeem-url=https://issuer.example.invalid/token",
            "--oidc-jwks-url=https://issuer.example.invalid/keys",
            "--client-id=ci-fixture-only", "--client-secret=ci-fixture-only",
            "--cookie-secret=" + base64.b64encode(b"0" * 32).decode(),
            "--email-domain=*", "--allowed-role=n8n_operator", "--allowed-role=n8n_admin", "--upstream=static://202",
            "--redirect-url=https://editor.example.invalid/oauth2/callback",
            "--code-challenge-method=S256", "--http-address=unix:///work/gateway.sock",
            "--custom-templates-dir=/templates", "--skip-provider-button=false",
            "--show-debug-on-error=false", "--cookie-secure=true",
            "--cookie-httponly=true", "--cookie-samesite=lax",
        ]
        try:
            started = subprocess.run(command, capture_output=True, text=True, timeout=120)
            check(started.returncode == 0, "gateway_container_start_failed")
            deadline = time.monotonic() + 20
            while not endpoint.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            check(endpoint.exists(), "gateway_socket_unavailable")
            status, _, login = request(endpoint, "/oauth2/sign_in?rd=%2Fworkflow%2Fexample%3Ftab%3Dcanvas%26view%3Ddetails")
            check(status == 200, "login_status")
            page = Page(login)
            check("Sign in to n8n" in login and "Continue with Codestra" in login, "login_branding")
            check("#f4c223" in login and "#07080a" in login and "#55d6be" not in login, "codestra_black_gold_palette")
            check(page.forms == [{"method": "GET", "action": "/oauth2/start"}], "login_form_action")
            check(page.inputs == [{"type": "hidden", "name": "rd", "value": "/workflow/example?tab=canvas&view=details"}], "return_path_preserved")
            check(not page.scripts and 'type="password"' not in login, "no_local_credentials_or_scripts")
            status, headers, _ = request(endpoint, "/oauth2/start?rd=%2Fworkflow%2Fexample")
            check(status in (302, 303), "oidc_start_status")
            location = urllib.parse.urlsplit(headers["Location"])
            query = urllib.parse.parse_qs(location.query)
            check(location.hostname == "issuer.example.invalid", "oidc_start_host")
            check(query.get("code_challenge_method") == ["S256"] and bool(query.get("state")), "pkce_and_state")
            check("Secure" in headers.get("Set-Cookie", "") and "HttpOnly" in headers.get("Set-Cookie", ""), "csrf_cookie_security")
            status, _, protected = request(endpoint, "/workflow/example")
            check(status == 403 and "Continue with Codestra" in protected, "anonymous_upstream_denied")
            status, _, error = request(endpoint, "/oauth2/callback?error=access_denied")
            check(status == 403 and "Access required" in error, "access_error_rendered")
            check("issuer.example.invalid" not in error and "fixture-only" not in error, "errors_do_not_disclose_configuration")
            metadata = json.loads(subprocess.run(["docker", "inspect", name], capture_output=True, text=True, check=True).stdout)[0]
            check(metadata["HostConfig"]["NetworkMode"] == "none" and not metadata["HostConfig"].get("PortBindings"), "test_isolation")
            if args.render_dir:
                args.render_dir.mkdir(parents=True, exist_ok=True)
                (args.render_dir / "sign-in.html").write_text(login)
                (args.render_dir / "access-required.html").write_text(error)
            print(json.dumps({"EDITOR_LOGIN_RENDER": "PASS", "checks": 15, "gateway_image": IMAGE,
                              "network": "none", "published_ports": 0, "production_login_verified": False}))
        finally:
            subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=20)


if __name__ == "__main__":
    main()
