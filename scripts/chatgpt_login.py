"""Local official OAuth login for the self-hosted FjordLens application."""
import base64
import argparse
import hashlib
import json
import os
import secrets
import subprocess
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt
import requests

ISSUER = 'https://auth.openai.com'
RESOURCE = 'https://api.openai.com/v1'
SCOPES = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'


def atomic_write(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(record, stream)
    os.replace(temp, path)
    path.chmod(0o600)


def authorization_url(host_id, redirect_uri, state, nonce, verifier, client_id='dynamic_agent_client'):
    params = dict(client_id=client_id, ext_agent_host_id=host_id, response_type='code',
                  redirect_uri=redirect_uri, scope=SCOPES, resource=RESOURCE, state=state,
                  nonce=nonce, code_challenge_method='S256',
                  code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='))
    if client_id == 'dynamic_agent_client':
        params['agent_name_hint'] = 'FjordLens'
    return ISSUER + '/api/accounts/authorize?' + urlencode(params)


def exchange(params, state, nonce, verifier, redirect_uri, expected_client=None):
    if not secrets.compare_digest(params.get('state', [''])[0], state):
        raise ValueError('Loginforsøget kunne ikke bekræftes.')
    if params.get('error'):
        raise ValueError('Login blev afvist. Prøv igen og godkend adgang til ChatGPT-abonnementet.')
    client = params.get('client_id', [expected_client or ''])[0]
    if not client.startswith('oaiapp_') or (expected_client and client != expected_client):
        raise ValueError('OpenAI returnerede ikke den forventede registrering.')
    code = params.get('code', [''])[0]
    if not code:
        raise ValueError('OpenAI returnerede ikke en loginkode.')
    response = requests.post(ISSUER + '/api/accounts/oauth/token', data=dict(
        grant_type='authorization_code', client_id=client, code=code, code_verifier=verifier,
        redirect_uri=redirect_uri, resource=RESOURCE), timeout=20, allow_redirects=False)
    if response.status_code != 200:
        raise ValueError('OpenAI kunne ikke afslutte login. Start et nyt loginforsøg.')
    tokens = response.json()
    token = tokens.get('id_token', '')
    key = jwt.PyJWKClient(ISSUER + '/.well-known/jwks.json', timeout=10).get_signing_key_from_jwt(token).key
    identity = jwt.decode(token, key, algorithms=['RS256'], issuer=ISSUER, audience=client,
                          options={'require': ['sub', 'exp', 'iat']}, leeway=5)
    if identity.get('nonce') != nonce:
        raise ValueError('Loginforsøgets identitet kunne ikke bekræftes.')
    if 'chatgpt.tokens.use.direct' not in tokens.get('scope', '').split():
        raise ValueError('Adgang til ChatGPT-abonnementet blev ikke godkendt.')
    if not tokens.get('access_token') or not tokens.get('refresh_token'):
        raise ValueError('OpenAI returnerede ikke de nødvendige loginoplysninger.')
    return dict(client_id=client, issuer=ISSUER, subject=identity['sub'], email=identity.get('email', ''),
                id_token=token, access_token=tokens['access_token'], refresh_token=tokens['refresh_token'],
                scopes=tokens['scope'].split(), saved_at=int(time.time()),
                expires_at=int(time.time()) + int(tokens.get('expires_in', 3600)))


def main():
    parser = argparse.ArgumentParser(description='Tilslut ChatGPT til FjordLens')
    parser.add_argument('--new-account', action='store_true', help='Tilslut en anden konto eller et andet workspace')
    args = parser.parse_args()
    folder = Path.home() / '.fjordlens-chatgpt'
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == 'nt':
        account = os.environ['USERDOMAIN'] + '\\' + os.environ['USERNAME']
        subprocess.run(['icacls', str(folder), '/inheritance:r', '/grant:r', account + ':(OI)(CI)F'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        folder.chmod(0o700)
    host_file = folder / 'host.json'
    if not host_file.exists():
        atomic_write(host_file, {'ext_agent_host_id': 'urn:uuid:' + str(uuid.uuid4())})
    host = json.loads(host_file.read_text())['ext_agent_host_id']
    registration_file = folder / 'registration.json'
    registration = json.loads(registration_file.read_text()) if registration_file.exists() and not args.new_account else {}
    client = registration.get('client_id', 'dynamic_agent_client')
    state, nonce, verifier = (secrets.token_urlsafe(48) for _ in range(3))
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Never log callback codes or state.

        def do_GET(self):
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            if parsed.path != '/auth/callback' or params.get('state', [''])[0] != state:
                self.send_error(400, 'Invalid callback')
                return
            result.update(params)
            body = b'Login modtaget. Gaa tilbage til FjordLens-loginprogrammet.'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

    with HTTPServer(('127.0.0.1', 0), Callback) as server:
        server.timeout = 1
        redirect = f'http://127.0.0.1:{server.server_port}/auth/callback'
        url = authorization_url(host, redirect, state, nonce, verifier, client)
        print('Åbner ChatGPT-login i din browser. Login udløber efter 10 minutter.')
        if not webbrowser.open(url):
            raise ValueError('Browseren kunne ikke åbnes. Kør programmet på en computer med en browser.')
        deadline = time.monotonic() + 600
        while not result and time.monotonic() < deadline:
            server.handle_request()
        if not result:
            raise ValueError('Login udløb. Prøv igen.')
    record = exchange(result, state, nonce, verifier, redirect,
                      None if client == 'dynamic_agent_client' else client)
    if registration.get('subject') and record['subject'] != registration['subject']:
        raise ValueError('Login stemmer ikke overens med den valgte konto.')
    atomic_write(registration_file, {k: record[k] for k in ['client_id', 'subject']})
    record['ext_agent_host_id'] = host
    output = folder / 'fjordlens-chatgpt-connection.json'
    atomic_write(output, record)
    print('Login gennemført. Vælg denne fil i FjordLens via HTTPS:\n' + str(output))
    print('Slet forbindelsesfilen efter overførslen. Del den ikke med andre.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Third-party exceptions can contain credential values; do not print them.
        print('Login kunne ikke gennemføres. Prøv igen og godkend ChatGPT-adgangen hos OpenAI.')
        raise SystemExit(1)
