"""Host-wide RAM accounting and hard Docker limits for the FjordLens stack."""
import http.client
import json
import os
from pathlib import Path
import socket
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MIB = 1024 ** 2
RESERVE = 2 * 1024 ** 3
HUB_MEMORY_PROTOCOL = '3'
LEASE_SECONDS = 120
MAX_SAMPLE_AGE = 10
SERVICES = {'fjordlens', 'fjordlens-ai', 'fjordlens-convert', 'fjordlens-updater'}
_api_version = None


class DockerConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect('/var/run/docker.sock')


def docker(method, path, body=None):
    global _api_version
    if _api_version is None:
        version_conn = DockerConnection('localhost', timeout=3)
        try:
            version_conn.request('GET', '/version')
            response = version_conn.getresponse()
            if response.status != 200:
                raise RuntimeError('Docker API version discovery failed')
            _api_version = json.loads(response.read())['ApiVersion']
        finally:
            version_conn.close()
    conn = DockerConnection('localhost', timeout=3)
    try:
        conn.request(method, '/v' + _api_version + path, body=json.dumps(body) if body is not None else None,
                     headers={'Content-Type': 'application/json'})
        response = conn.getresponse()
        data = response.read()
        if response.status >= 300:
            raise RuntimeError(f'Docker {response.status}: {data.decode(errors="replace")[:250]}')
        return json.loads(data) if data else {}
    finally:
        conn.close()


class MemoryGovernor:
    def __init__(self, api=docker, lease_path=None):
        self.enabled = os.environ.get('FJORDLENS_MEMORY_GUARD') == '1'
        self.project = os.environ.get('COMPOSE_PROJECT_NAME', 'fjordlens')
        self.api = api
        self.lock = threading.RLock()
        self.state = {'ok': False, 'enabled': self.enabled, 'error': 'Afventer samlet RAM-måling'}
        self.lease_path = Path(lease_path) if lease_path else None
        self.leases = {}
        if self.enabled and self.lease_path and self.lease_path.exists():
            self.leases = json.loads(self.lease_path.read_text())
            if not isinstance(self.leases, dict):
                raise RuntimeError('Invalid memory reservations')

    def _persist(self):
        if self.lease_path:
            self.lease_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.lease_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.leases))
            temporary.replace(self.lease_path)

    def snapshot(self):
        with self.lock:
            now = time.time()
            state = dict(self.state)
            self.leases = {k: v for k, v in self.leases.items() if v['expires'] > now
                           and not (v.get('released_at') and
                                    state.get('measured_at', 0) >= v['released_at'])}
            if self.enabled and not 0 <= now - state.get('measured_at', 0) <= MAX_SAMPLE_AGE:
                state.update(ok=False, error='Den samlede RAM-måling er for gammel')
            reserved = sum(v['bytes'] for v in self.leases.values())
            free = max(0, state.get('total_bytes', 0) - state.get('used_bytes', 0) - RESERVE)
            state.update(mode='host_global', reserved_bytes=reserved,
                         available_bytes=max(0, free-reserved) if state.get('ok') else 0)
            return state

    def reservation(self, action, body):
        token = body.get('token')
        service = body.get('service')
        if (not isinstance(token, str) or len(token) != 32
                or any(c not in '0123456789abcdef' for c in token) or service not in SERVICES):
            raise ValueError('Invalid reservation identity')
        with self.lock:
            state = self.snapshot()
            existing = self.leases.get(token)
            if existing and existing['service'] != service:
                raise ValueError('Reservation owner mismatch')
            if action == 'release':
                # Do not reuse admission from an old host sample: the completed
                # job may have left a resident model or buffers in memory.
                if existing:
                    existing['released_at'] = time.time()
                self._persist()
                return {'ok': True}
            if action == 'renew':
                if not existing:
                    return {'ok': False, 'error': 'Reservation expired'}
                existing['expires'] = time.time() + LEASE_SECONDS
                self._persist()
                return {'ok': True}
            if action != 'reserve':
                raise ValueError('Unknown reservation operation')
            amount = body.get('bytes')
            if type(amount) is not int or not 0 < amount <= 128*1024**3:
                raise ValueError('Invalid reservation size')
            if existing:
                if existing['bytes'] != amount:
                    raise ValueError('Reservation size mismatch')
                return {'ok': True, 'granted': True, 'token': token}
            if not self.enabled or not state.get('ok') or state['available_bytes'] < amount:
                return {'ok': state.get('ok', False), 'granted': False,
                        'available_bytes': state['available_bytes'], 'error': state.get('error', '')}
            if len(self.leases) >= 4096:
                return {'ok': False, 'granted': False, 'error': 'Too many reservations'}
            self.leases[token] = {'service': service, 'bytes': amount, 'expires': time.time()+LEASE_SECONDS}
            try:
                self._persist()
            except Exception:
                self.leases.pop(token, None)
                raise
            return {'ok': True, 'granted': True, 'token': token}

    def sample(self):
        hub_url = os.environ.get('FJORDHUB_URL', '').rstrip('/')
        hub_key = os.environ.get('FJORDHUB_API_KEY', '')
        if not hub_url or not hub_key:
            raise RuntimeError('FjordHub RAM connection is not configured')
        request = Request(hub_url + '/api/hub/fjordlens/memory-budget', headers={'X-Hub-Key': hub_key})
        with urlopen(request, timeout=8) as response:
            measurement = json.load(response)
        if (not measurement.get('ok') or measurement.get('source') != 'fjordhub'
                or not 0 <= time.time()-float(measurement.get('measured_at', 0)) <= MAX_SAMPLE_AGE):
            raise RuntimeError('No fresh verified FjordHub host measurement')
        total, used = int(measurement['total_bytes']), int(measurement['used_bytes'])
        if not 0 <= used <= total or total <= RESERVE:
            raise RuntimeError('Invalid total host memory measurement')
        # Remove the old per-service partitions. The LXC remains the aggregate
        # hard boundary; all heavy jobs now reserve from its shared free RAM.
        filters = json.dumps({'label': [f'com.docker.compose.project={self.project}',
                                         'io.fjordlens.memory-managed=1']})
        listed = self.api('GET', '/containers/json?' + urlencode({'all': 1, 'filters': filters}))
        seen = set()
        for entry in listed:
            service = entry.get('Labels', {}).get('com.docker.compose.service')
            if service not in SERVICES:
                continue
            seen.add(service)
            ident = entry['Id']
            config = self.api('GET', f'/containers/{ident}/json')['HostConfig']
            if config.get('Memory') != total or config.get('MemorySwap') != total:
                # Never lower an existing hard limit during live work.
                if int(config.get('Memory') or 0) > total:
                    raise RuntimeError('Host RAM limit changed; restart services to apply it')
                result = self.api('POST', f'/containers/{ident}/update', {'Memory': total, 'MemorySwap': total})
                if result.get('Warnings'):
                    raise RuntimeError('; '.join(result['Warnings']))
            actual = self.api('GET', f'/containers/{ident}/json')['HostConfig']
            if actual.get('Memory') != total or actual.get('MemorySwap') != total:
                raise RuntimeError('Docker did not apply the shared host ceiling')
        if seen != SERVICES:
            raise RuntimeError('Missing managed FjordLens services')
        return dict(ok=True, enabled=True, mode='host_global', source='fjordhub',
                    measured_at=measurement['measured_at'], total_bytes=total, used_bytes=used,
                    reserve_bytes=RESERVE, budget_bytes=max(0, total-used-RESERVE),
                    pressure=total-used <= RESERVE)

    def run(self):
        while True:
            try:
                state = self.sample()
            except Exception as exc:
                state = {'ok': False, 'enabled': True, 'error': str(exc)}
                print(f'memory_guard error={exc}', flush=True)
            with self.lock:
                self.state = state
            time.sleep(1)

    def start(self):
        if self.enabled:
            threading.Thread(target=self.run, name='memory-governor', daemon=True).start()
