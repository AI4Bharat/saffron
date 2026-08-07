#!/usr/bin/env python3
"""Measure where Saffron's time actually goes, so the 'should we add cores?'
question can be answered with numbers instead of intuition.

Read-only: it logs in as the ASR admin and hits GET endpoints only.
"""
import json
import statistics
import subprocess
import sys
import threading
import time
import urllib.request

BASE = 'http://127.0.0.1:4020/api'


def login(u, p):
    req = urllib.request.Request(BASE + '/login', method='POST')
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, json.dumps({'username': u, 'password': p}).encode()) as r:
        return json.load(r)['token']


def cpu_snapshot():
    """(busy_jiffies, total_jiffies) across all cores."""
    with open('/proc/stat') as fh:
        parts = [int(x) for x in fh.readline().split()[1:]]
    idle = parts[3] + parts[4]
    return sum(parts) - idle, sum(parts)


def bench(label, path, token, concurrency, per_thread):
    lat = []
    lock = threading.Lock()
    errors = [0]

    def worker():
        mine = []
        for _ in range(per_thread):
            req = urllib.request.Request(BASE + path)
            req.add_header('Authorization', 'Bearer ' + token)
            t = time.time()
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    r.read()
                mine.append(time.time() - t)
            except Exception:
                with lock:
                    errors[0] += 1
        with lock:
            lat.extend(mine)

    b0, t0 = cpu_snapshot()
    start = time.time()
    threads = [threading.Thread(target=worker) for _ in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.time() - start
    b1, t1 = cpu_snapshot()

    cpu_pct = 100.0 * (b1 - b0) / (t1 - t0) if t1 > t0 else 0
    n = len(lat)
    if not n:
        print(f'{label:38s} all {errors[0]} request(s) failed')
        return
    lat.sort()
    print(f'{label:38s} n={n:4d} conc={concurrency:2d}  '
          f'p50={statistics.median(lat)*1000:6.0f}ms  p95={lat[int(n*0.95)-1]*1000:6.0f}ms  '
          f'max={lat[-1]*1000:6.0f}ms  {n/wall:5.1f} req/s  '
          f'CPU={cpu_pct:4.1f}% of {CORES} cores  err={errors[0]}')


CORES = int(subprocess.check_output(['nproc']).decode().strip())
print(f'host: {CORES} cores')
print(subprocess.check_output(['uptime']).decode().strip())
print()

TOKEN = login('asr-admin', 'asr@b0dhan$')
TTS = login('tts-admin', 'tts@b0dhan$')

print('--- single request, warm ---')
bench('ASR dashboard (SQL aggregates)', '/pool/admin/dashboard?team=asr', TOKEN, 1, 3)
bench('ASR pool browse (paged)', '/pool/admin/items?team=asr&per_page=50', TOKEN, 1, 3)
bench('TTS dashboard (cached)', '/admin/dashboard', TTS, 1, 3)
bench('TTS dashboard (uncached)', '/admin/dashboard?refresh=1', TTS, 1, 2)

print('\n--- concurrent load ---')
bench('ASR dashboard x8 parallel', '/pool/admin/dashboard?team=asr', TOKEN, 8, 3)
bench('ASR dashboard x16 parallel', '/pool/admin/dashboard?team=asr', TOKEN, 16, 3)
bench('pool browse x16 parallel', '/pool/admin/items?team=asr&per_page=50', TOKEN, 16, 5)
bench('TTS dashboard x8 uncached', '/admin/dashboard?refresh=1', TTS, 8, 1)
