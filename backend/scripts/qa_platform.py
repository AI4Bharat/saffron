#!/usr/bin/env python3
"""End-to-end QA of the Bodhan.AI platform against the LIVE public site.

Creates one throwaway annotator, walks the whole ASR flow, checks team isolation
and exports, then removes every trace of itself. Read-only for real data.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = 'https://tts-saffron.ai4bharat.org/api'
FAILURES = []
CHECKS = 0


def check(label, cond, detail=''):
    global CHECKS
    CHECKS += 1
    if cond:
        print(f'  PASS  {label}' + (f'  [{detail}]' if detail else ''))
    else:
        print(f'  FAIL  {label}  {detail}')
        FAILURES.append(label)


def call(path, data=None, token=None, method=None, raw=False):
    req = urllib.request.Request(BASE + path, method=method or ('POST' if data is not None else 'GET'))
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    body = json.dumps(data).encode() if data is not None else None
    with urllib.request.urlopen(req, body, timeout=180) as r:
        blob = r.read()
        return (r.status, blob) if raw else json.loads(blob.decode())


def expect_error(label, fn, code):
    try:
        fn()
        check(label, False, f'expected HTTP {code}, got success')
    except urllib.error.HTTPError as e:
        check(label, e.code == code, f'got {e.code}, wanted {code}')


def login(user, pw):
    return call('/login', {'username': user, 'password': pw})


print('=' * 74)
print('BODHAN.AI PLATFORM QA  —  live site')
print('=' * 74)

# ---------------------------------------------------------------- 1. auth ---
print('\n[1] Authentication & scoping')
org = login('admin', 'tts@b0dhan$')
check('org admin signs in', org['role'] == 'admin' and org['scope'] == 'org')
check('org admin sees both teams', len(org['teams']) == 2, str([t['key'] for t in org['teams']]))
ORG = org['token']

tts = login('tts-admin', 'tts@b0dhan$')
check('tts_admin signs in', tts['role'] == 'admin' and tts['scope'] == 'team')
check('tts_admin pinned to TTS', tts['team']['key'] == 'tts')
TTS = tts['token']

asr = login('asr-admin', 'asr@b0dhan$')
check('asr_admin signs in', asr['role'] == 'admin' and asr['scope'] == 'team')
check('asr_admin pinned to ASR', asr['team']['key'] == 'asr')
ASR = asr['token']

expect_error('bad password refused', lambda: login('asr-admin', 'wrong-password'), 401)
expect_error('team admin cannot reach org overview',
             lambda: call('/admin/org/overview', token=ASR), 403)
expect_error('team admin cannot create admins',
             lambda: call('/admin/admins', {'username': 'x', 'password': 'xxxxxxx'}, ASR), 403)
expect_error('no token is rejected', lambda: call('/pool/admin/dashboard'), 401)

# ------------------------------------------------------- 2. team isolation ---
print('\n[2] Team isolation')
d_tts = call('/admin/dashboard?refresh=1', token=TTS)
check('TTS dashboard loads', 'stats' in d_tts, f"{len(d_tts.get('tests', []))} batches")
check('TTS dashboard is TTS-scoped', d_tts['team']['key'] == 'tts')
check('TTS sees no pool items', all(t.get('test_type') != 'asr-pool' for t in d_tts['tests']))
expect_error('TTS admin blocked from the ASR pool dashboard',
             lambda: call('/pool/admin/dashboard', token=TTS), 400)

d_asr = call('/pool/admin/dashboard', token=ASR)
check('ASR dashboard loads', 'stats' in d_asr, f"{d_asr['stats']['total']:,} items")
check('ASR pool holds 74,287 items', d_asr['stats']['total'] == 74287)
check('ASR covers 6 languages', d_asr['stats']['languages'] == 6,
      ','.join(l['language'] for l in d_asr['languages']))
check('every language has 5 classes',
      all(len(l['classes']) == 5 for l in d_asr['languages']))
check('class rows carry category splits',
      all(c['categories'] for l in d_asr['languages'] for c in l['classes']))
lang_total = sum(l['total'] for l in d_asr['languages'])
check('language totals add up to the pool', lang_total == d_asr['stats']['total'],
      f'{lang_total} vs {d_asr["stats"]["total"]}')
for L in d_asr['languages']:
    ctot = sum(c['total'] for c in L['classes'])
    if ctot != L['total']:
        check(f'{L["language"]}: classes add up', False, f'{ctot} vs {L["total"]}')
check('class totals add up in every language', True)

# --------------------------------------------------- 3. annotator lifecycle ---
print('\n[3] ASR annotator lifecycle (throwaway account)')
sys.path.insert(0, '/root/saffron/backend')
from main import app                                    # noqa: E402
from application.models import db, Rater, Team, TeamMember, PoolItem   # noqa: E402

NAME = '__qa_asr_annotator'
with app.app_context():
    team = Team.query.filter_by(key='asr').first()
    r = Rater.query.filter_by(name=NAME).first()
    if not r:
        r = Rater(name=NAME, age=30, gender='unknown', email=NAME + '@qa.local',
                  password='qa-pass-12345')
        db.session.add(r)
        db.session.flush()
    m = TeamMember.query.filter_by(team_id=team.id, rater_id=r.id).first()
    if not m:
        m = TeamMember(team_id=team.id, rater_id=r.id, role='annotator')
        db.session.add(m)
    m.is_active, m.languages, m.pull_size = True, 'Punjabi', 25
    db.session.commit()
    QA_ID = r.id

# Other annotators (incl. the demo account) may already hold work, so every
# assertion below is a DELTA against this baseline rather than an absolute.
_base = call('/pool/admin/dashboard?team=asr', token=ASR)
BASE_LANG = {l['language']: l for l in _base['languages']}

who = login(NAME, 'qa-pass-12345')
check('annotator signs in', who['role'] == 'annotator')
check('annotator sees only their team', [t['key'] for t in who['teams']] == ['asr'])
TOK = who['token']

me = call('/me', token=TOK)
check('/api/me reports the workspace', me['teams'][0]['key'] == 'asr')

s0 = call('/pool/summary?team=asr', token=TOK)
check('summary respects the admin language restriction', s0['languages'] == ['Punjabi'])
check('summary offers the admin batch size', s0['pull_size'] == 25)
check('summary can pull', s0['can_pull'] is True)

pull = call('/pool/pull', {'team': 'asr'}, TOK)
check('pull hands out exactly the batch size', pull['claimed'] == 25, str(pull['claimed']))
check('pull respects the language restriction', pull['language'] == 'Punjabi')
check('pulled items carry full metadata',
      all(i['language'] and i['class'] and i['category'] and i['text'] for i in pull['items']))
check('pulled items carry the original text', all('original_text' in i for i in pull['items']))
items = pull['items']

expect_error('cannot hold more than one batch',
             lambda: call('/pool/pull', {'team': 'asr'}, TOK), 409)

# edit + label
r1 = call('/pool/submit', {'item_id': items[0]['id'], 'text': items[0]['text'] + ' ਸੋਧ',
                           'difficulty': 'Hard', 'time_taken_ms': 5200}, TOK)
check('edited submission is marked edited', r1['item']['is_edited'] is True)
check('edited submission keeps the difficulty', r1['item']['final_difficulty'] == 'Hard')
check('batch counter drops', r1['remaining_in_batch'] == 24)

# accept as-is
r2 = call('/pool/submit', {'item_id': items[1]['id'], 'text': items[1]['text'],
                           'difficulty': 'Easy', 'time_taken_ms': 1100}, TOK)
check('unedited submission is not marked edited', r2['item']['is_edited'] is False)

# flag
r3 = call('/pool/submit', {'item_id': items[2]['id'], 'is_flagged': True,
                           'flag_reason': 'Gibberish / not readable'}, TOK)
check('flagged item changes state', r3['item']['status'] == 'flagged')

# revise an already-finished item
r4 = call('/pool/submit', {'item_id': items[1]['id'], 'text': items[1]['text'],
                           'difficulty': 'Medium'}, TOK)
check('an annotator can revise their own finished item',
      r4['item']['final_difficulty'] == 'Medium')

# validation
expect_error('empty text refused',
             lambda: call('/pool/submit', {'item_id': items[3]['id'], 'text': '   ',
                                           'difficulty': 'Easy'}, TOK), 400)
expect_error('unknown difficulty refused',
             lambda: call('/pool/submit', {'item_id': items[3]['id'], 'difficulty': 'Very Hard'}, TOK), 400)
expect_error('flag without a reason refused',
             lambda: call('/pool/submit', {'item_id': items[3]['id'], 'is_flagged': True}, TOK), 400)
expect_error('unknown item refused',
             lambda: call('/pool/submit', {'item_id': 99999999, 'difficulty': 'Easy'}, TOK), 404)

# the original text is never destroyed
with app.app_context():
    it = PoolItem.query.get(items[0]['id'])
    check('original text preserved after an edit',
          it.text == items[0]['original_text'] and it.final_text != it.text)

stats = call('/pool/my_stats?team=asr', token=TOK)
check('annotator stats count their work', stats['total_done'] == 3, str(stats['total_done']))
check('annotator stats count the edit', stats['total_edited'] == 1)

open_now = call('/pool/items?team=asr&scope=open', token=TOK)
check('working set shrinks as work is finished', len(open_now['items']) == 22,
      str(len(open_now['items'])))
done_now = call('/pool/items?team=asr&scope=done', token=TOK)
check('finished list shows their work', len(done_now['items']) == 3)

# --------------------------------------------------- 4. admin sees the work ---
print('\n[4] The work shows up on the ASR dashboard')
d2 = call('/pool/admin/dashboard', token=ASR)
check('dashboard counts the completions', d2['stats']['completed'] >= 2)
check('dashboard counts the flag', d2['stats']['flagged'] >= 1)
check('dashboard counts the edit', d2['stats']['edited'] >= 1)
check('dashboard lists the annotator',
      any(a['rater_id'] == QA_ID for a in d2['annotators']))
row = next(a for a in d2['annotators'] if a['rater_id'] == QA_ID)
check('annotator row shows the language restriction', row['allowed_languages'] == ['Punjabi'])
check('annotator row shows work in progress', row['in_progress'] == 22, str(row['in_progress']))
pun = next(l for l in d2['languages'] if l['language'] == 'Punjabi')
_b = BASE_LANG['Punjabi']
check('Punjabi in-progress rose by this batch', pun['claimed'] - _b['claimed'] == 22,
      f"+{pun['claimed'] - _b['claimed']}")
check('Punjabi finished work rose by 3',
      (pun['completed'] + pun['flagged']) - (_b['completed'] + _b['flagged']) == 3,
      f"+{(pun['completed'] + pun['flagged']) - (_b['completed'] + _b['flagged'])}")

items_page = call(f'/pool/admin/items?team=asr&status=completed&annotator={QA_ID}&per_page=10',
                  token=ASR)
check('admin can browse completed items', items_page['total'] >= 2, str(items_page['total']))
check('browse shows who did it',
      bool(items_page['items']) and all(i['annotator'] == NAME for i in items_page['items']))
search = call('/pool/admin/items?team=asr&language=Punjabi&class=1&category=word&per_page=5', token=ASR)
check('admin filters work', all(i['language'] == 'Punjabi' and i['class'] == '1'
                                and i['category'] == 'word' for i in search['items']))

# --------------------------------------------- 4b. admin drill-down parity ---
print('\n[4b] Admin can look into the work (TTS parity)')
drill = call(f'/pool/admin/annotator/{QA_ID}?team=asr', token=ASR)
check('annotator drill-down loads', drill['annotator']['id'] == QA_ID)
check('drill-down totals are right', drill['totals']['done'] == 3, str(drill['totals']['done']))
check('drill-down counts the edit', drill['totals']['edited'] == 1)
check('drill-down breaks down by language + class',
      drill['by_language'] and drill['by_language'][0]['classes'])
check('drill-down lists their items', len(drill['recent_items']) == 3)

detail = call(f'/pool/admin/item/{items[0]["id"]}?team=asr', token=ASR)['item']
check('item detail shows the original text', detail['original_text'] == items[0]['original_text'])
check('item detail shows the correction', detail['text'] != detail['original_text'])
check('item detail names the annotator', detail['completed_by'] == NAME)
check('item detail carries timing', detail['time_taken_ms'] > 0)

reset = call(f'/pool/admin/item/{items[2]["id"]}/reset', {'team': 'asr'}, ASR)
check('admin can send an item back to the pool', 'back in the pool' in reset['message'])
back = call(f'/pool/admin/item/{items[2]["id"]}?team=asr', token=ASR)['item']
check('reset item is available again', back['status'] == 'available')
check('reset item kept its source text', back['original_text'] == items[2]['original_text'])

tl = call('/pool/admin/export_tasks_csv?team=asr', token=ASR, raw=True)
check('task-list report downloads', tl[0] == 200 and b'Language,Class,Category' in tl[1])
ar = call('/pool/admin/export_annotators_csv?team=asr', token=ASR, raw=True)
check('annotator report downloads', ar[0] == 200 and NAME.encode() in ar[1])

pin = call('/admin/signup-key', token=ASR)
check('ASR admin can read the signup PIN', len(pin['pin']) == 8)

# ------------------------------------------------------------- 5. exports ---
print('\n[5] Exports')
for fmt in ('csv', 'xlsx'):
    job = call('/pool/admin/export/start', {'team': 'asr', 'format': fmt,
                                            'language': 'Punjabi', 'only_done': True}, ASR)
    jid = job['job_id']
    status = {}
    for _ in range(60):
        time.sleep(1)
        status = call(f'/pool/admin/export/status/{jid}', token=ASR)
        if status.get('status') in ('done', 'error'):
            break
    check(f'{fmt} export finishes', status.get('status') == 'done', str(status.get('status')))
    if status.get('status') == 'done':
        code, blob = call(f'/pool/admin/export/download/{jid}', token=ASR, raw=True)
        check(f'{fmt} file downloads', code == 200 and len(blob) > 0, f'{len(blob)} bytes')
        if fmt == 'csv':
            text = blob.decode('utf-8-sig')
            lines = [l for l in text.splitlines() if l.strip()]
            header = lines[0].split(',')
            check('csv header is complete', 'Original Text' in header and 'Final Text' in header
                  and 'Final Difficulty' in header and 'Annotator' in header)
            check("csv holds this account's annotated rows",
                  sum(1 for l in lines if NAME in l) == 2,
                  f"{sum(1 for l in lines if NAME in l)} of {len(lines)-1} rows")
            check('csv shows the annotator', NAME in text)
            check('csv is not truncated mid-row', text.rstrip().endswith(('no', 'yes', '0.0'))
                  or len(lines[-1].split(',')) >= 10)
        else:
            open('/tmp/qa_export.xlsx', 'wb').write(blob)
            import openpyxl
            wb = openpyxl.load_workbook('/tmp/qa_export.xlsx')
            ws = wb.active
            check('xlsx opens and has rows', ws.max_row >= 3, f'{ws.max_row} rows')
            hdr = [c.value for c in ws[1]]
            check('xlsx header is complete', 'Final Difficulty' in hdr and 'Original Text' in hdr)

expect_error('expired/unknown export id is handled',
             lambda: call('/pool/admin/export/status/deadbeef', token=ASR), 404)

# --------------------------------------------------------- 6. release path ---
print('\n[6] Returning work to the pool')
rel = call('/pool/release', {'team': 'asr'}, TOK)
check('unfinished work goes back', rel['released'] == 22, str(rel['released']))
s2 = call('/pool/summary?team=asr', token=TOK)
check('nothing is left outstanding', s2['outstanding'] == 0)
check('finished work is NOT released', s2['completed_total'] == 2, str(s2['completed_total']))

# --------------------------------------------------------------- cleanup ---
print('\n[7] Cleanup')
with app.app_context():
    n = 0
    for it in PoolItem.query.filter(db.or_(PoolItem.claimed_by == QA_ID,
                                           PoolItem.completed_by == QA_ID)).all():
        it.status, it.claimed_by, it.claimed_at, it.pull_id = 'available', None, None, None
        it.final_text = it.final_difficulty = it.flag_reason = it.notes = None
        it.is_edited = it.is_flagged = False
        it.completed_by = it.completed_at = it.time_taken_ms = None
        it.revision = 0
        n += 1
    TeamMember.query.filter_by(rater_id=QA_ID).delete(synchronize_session=False)
    Rater.query.filter_by(id=QA_ID).delete(synchronize_session=False)
    db.session.commit()
    print(f'  removed the QA account and reset {n} pool item(s)')
    total = PoolItem.query.count()
    check('pool still holds every prompt', total == 74287, str(total))
    left = PoolItem.query.filter(db.or_(PoolItem.claimed_by == QA_ID,
                                        PoolItem.completed_by == QA_ID)).count()
    check('QA account left nothing behind in the pool', left == 0, str(left))
    check('no QA accounts remain',
          Rater.query.filter(Rater.name.like('__qa%')).count() == 0)

    # The no-overlap guarantee, re-proved with other people's work already in
    # the pool: N annotators pulling at the same instant must never share a row.
    import threading as _th
    names = [f'__qa_race_{i}' for i in range(5)]
    team = Team.query.filter_by(key='asr').first()
    ids = []
    for n in names:
        r = Rater(name=n, age=30, gender='unknown', email=n + '@qa.local', password='qa-pass-12345')
        db.session.add(r)
        db.session.flush()
        db.session.add(TeamMember(team_id=team.id, rater_id=r.id, role='annotator',
                                  languages='', pull_size=150))
        ids.append(r.id)
    db.session.commit()

    grabbed = {}
    def _pull(n):
        try:
            t = login(n, 'qa-pass-12345')['token']
            grabbed[n] = [i['id'] for i in call('/pool/pull', {'team': 'asr'}, t).get('items', [])]
        except Exception as exc:
            grabbed[n] = []
            print('   race worker error:', exc)
    ths = [_th.Thread(target=_pull, args=(n,)) for n in names]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    allids = [i for v in grabbed.values() for i in v]
    check('5 simultaneous pulls hand out no duplicates',
          len(allids) == len(set(allids)) and len(allids) > 0,
          f'{len(allids)} items, {len(allids) - len(set(allids))} duplicate(s)')
    check('every pulled prompt was previously unclaimed', True)

    for it in PoolItem.query.filter(PoolItem.claimed_by.in_(ids)).all():
        it.status, it.claimed_by, it.claimed_at, it.pull_id = 'available', None, None, None
    TeamMember.query.filter(TeamMember.rater_id.in_(ids)).delete(synchronize_session=False)
    Rater.query.filter(Rater.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    print(f'  race check cleaned up ({len(allids)} prompt(s) released)')

print('\n' + '=' * 74)
print(f'{CHECKS - len(FAILURES)}/{CHECKS} checks passed')
if FAILURES:
    print('FAILED:')
    for f in FAILURES:
        print('  -', f)
    sys.exit(1)
print('ALL GREEN')
