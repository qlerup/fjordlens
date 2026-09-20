"""Host-wide RAM accounting and hard Docker limits for the FjordLens stack."""
import http.client
import json
import os
from pathlib import Path
import socket
import threading
import time
from urllib.parse import urlencode

MIB = 1024 ** 2
RESERVE = 2 * 1024 ** 3
FLOORS = {'fjordlens': 512*MIB, 'fjordlens-ai': 768*MIB,
          'fjordlens-convert': 256*MIB, 'fjordlens-updater': 128*MIB}
WEIGHTS = {'fjordlens': 1, 'fjordlens-ai': 8, 'fjordlens-convert': 3, 'fjordlens-updater': 0}


class DockerConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect('/var/run/docker.sock')


def docker(method, path, body=None):
    conn = DockerConnection('localhost', timeout=3)
    try:
        conn.request(method, '/v1.41' + path, body=json.dumps(body) if body is not None else None,
                     headers={'Content-Type': 'application/json'})
        response = conn.getresponse()
        data = response.read()
        if response.status >= 300:
            raise RuntimeError(f'Docker {response.status}: {data.decode(errors="replace")[:250]}')
        return json.loads(data) if data else {}
    finally:
        conn.close()


def host_memory(cgroup, proc):
    """Use the LXC/VM limit, never a container's own limit or free swap."""
    values = {}
    for line in (proc / 'meminfo').read_text().splitlines():
        key, _, value = line.partition(':')
        values[key] = int(value.strip().split()[0]) * 1024
    limits = [values['MemTotal']]
    raw_usage = None
    for limit_name, usage_name in [('memory.max', 'memory.current'),
                                    ('memory/memory.limit_in_bytes', 'memory/memory.usage_in_bytes')]:
        limit_path = cgroup / limit_name
        if limit_path.exists():
            raw = limit_path.read_text().strip()
            if raw != 'max' and 0 < int(raw) < 2**60:
                limits.append(int(raw))
                raw_usage = int((cgroup / usage_name).read_text().strip())
                break
    total = min(limits)
    # For bare metal / VM root cgroups, meminfo includes all processes and caches.
    used = raw_usage if raw_usage is not None else total - values['MemFree']
    if not 0 <= used <= total or total <= 0:
        raise RuntimeError('Invalid host memory accounting')
    return total, used


def allocate(total, host_used, containers):
    own = sum(c['usage'] for c in containers)
    if own > host_used + 64*MIB:
        raise RuntimeError('Host cgroup does not include all FjordLens containers')
    other = max(0, host_used - own)
    budget = max(0, total - other - RESERVE)
    # Docker cannot enforce a zero-byte limit (zero means unlimited).
    if budget < len(containers) * 8*MIB:
        raise RuntimeError('No RAM left for FjordLens after the 2 GiB reserve')
    bases = {c['id']: max(FLOORS[c['service']], ((c['usage'] + 127*MIB)//(64*MIB))*64*MIB)
             for c in containers}
    baseline = sum(bases.values())
    if baseline > budget:
        remaining = budget - len(containers)*8*MIB
        caps = {c['id']: 8*MIB + int(remaining*bases[c['id']]/baseline) for c in containers}
    else:
        weights = sum(WEIGHTS[c['service']] for c in containers) or 1
        caps = {c['id']: bases[c['id']] + int((budget-baseline)*WEIGHTS[c['service']]/weights)
                for c in containers}
    # Round down, keeping the sum of hard limits within the aggregate budget.
    caps = {key: max(8*MIB, value//MIB*MIB) for key, value in caps.items()}
    return budget, other, caps


class MemoryGovernor:
    def __init__(self, api=docker):
        self.enabled = os.environ.get('FJORDLENS_MEMORY_GUARD') == '1'
        self.project = os.environ.get('COMPOSE_PROJECT_NAME', 'fjordlens')
        self.api = api
        self.lock = threading.Lock()
        self.state = {'ok': False, 'enabled': self.enabled, 'error': 'Afventer RAM-måling'}

    def snapshot(self):
        with self.lock:
            state = dict(self.state)
        age = time.monotonic() - state.pop('_sample_at', 0)
        if self.enabled and age > 5:
            state.update(ok=False, error='RAM-målingen er for gammel')
        return state

    def sample(self):
        filters = json.dumps({'label': [f'com.docker.compose.project={self.project}',
                                         'io.fjordlens.memory-managed=1']})
        listed = self.api('GET', '/containers/json?' + urlencode({'all': 1, 'filters': filters}))
        containers = []
        for entry in listed:
            service = entry.get('Labels', {}).get('com.docker.compose.service')
            if service not in FLOORS:
                continue
            ident = entry['Id']
            info = self.api('GET', f'/containers/{ident}/json')
            running = info['State']['Running']
            raw = self.api('GET', f'/containers/{ident}/stats?stream=false&one-shot=true') if running else {}
            usage = raw.get('memory_stats', {}).get('usage', 0)
            if running and not usage:
                raise RuntimeError(f'Missing memory stats for {service}')
            containers.append({'id': ident, 'service': service, 'usage': int(usage),
                               'limit': int(info['HostConfig'].get('Memory') or 0),
                               'swap': int(info['HostConfig'].get('MemorySwap') or 0)})
        if not containers:
            raise RuntimeError('Ingen FjordHub-styrede FjordLens-containere fundet')
        total, used = host_memory(Path('/host/sys/fs/cgroup'), Path('/host/proc'))
        budget, other, caps = allocate(total, used, containers)
        # Shrink before growing: reallocating memory must not temporarily double it.
        containers.sort(key=lambda c: caps[c['id']] - (c['limit'] or total))
        for c in containers:
            cap = caps[c['id']]
            if c['limit'] != cap or c['swap'] != cap:
                result = self.api('POST', f'/containers/{c["id"]}/update', {'Memory': cap, 'MemorySwap': cap})
                if result.get('Warnings'):
                    raise RuntimeError('; '.join(result['Warnings']))
            # Read back the actual limits; never advertise an unenforced budget.
            actual = self.api('GET', f'/containers/{c["id"]}/json')['HostConfig']
            if actual.get('Memory') != cap or actual.get('MemorySwap') != cap:
                raise RuntimeError('Docker did not apply the RAM/swap limit')
        return {'ok': True, 'enabled': True, '_sample_at': time.monotonic(),
                'total_bytes': total, 'used_bytes': used, 'other_bytes': other,
                'reserve_bytes': RESERVE, 'budget_bytes': budget,
                'pressure': total-used < RESERVE + 128*MIB,
                'containers': {c['service']: {'usage_bytes': c['usage'], 'limit_bytes': caps[c['id']]}
                               for c in containers}}

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
