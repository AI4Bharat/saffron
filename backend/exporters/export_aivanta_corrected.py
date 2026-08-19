#!/usr/bin/env python3
"""Bundle the aivanta transcript-correction task: corrected manifest + audio.

The two Tests (Batch 1/2, ids 21144/21145) hold one rating per clip, keyed by the
clip's audio_filename. This joins those corrections back onto manifest.jsonl and
drops the whole deliverable - manifest, audio, raw annotations - into one folder.

  ./venv/bin/python exporters/export_aivanta_corrected.py --out /data2/downloads/aivanta_transcript_corrected
"""

import argparse
import csv
import json
import os
import shutil

import sqlalchemy as sa

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK_DIR = os.path.join(BACKEND_DIR, 'aivanta_task')
MANIFEST = os.path.join(TASK_DIR, 'manifest.jsonl')
TEST_TYPE = 'transcript-correction'


def _engine():
    uri = None
    with open(os.path.join(BACKEND_DIR, '.env'), encoding='utf-8') as f:
        for line in f:
            if line.startswith('DATABASE_URI'):
                uri = line.split('=', 1)[1].strip().strip('"').strip("'")
    if not uri:
        raise SystemExit('DATABASE_URI not found in backend/.env')
    return sa.create_engine(uri)


def fetch_corrections(engine):
    """audio_filename -> correction, for every transcript-correction rating."""
    md = sa.MetaData()
    test_t = sa.Table('test', md, autoload_with=engine)
    rating_t = sa.Table('rating', md, autoload_with=engine)
    rater_t = sa.Table('rater', md, autoload_with=engine)

    out = {}
    with engine.connect() as conn:
        test_ids = [r[0] for r in conn.execute(
            sa.select(test_t.c.id).where(test_t.c.test_type == TEST_TYPE)).fetchall()]
        rows = conn.execute(
            sa.select(rating_t.c.test_id, rating_t.c.rater_id, rating_t.c.results_json,
                      rating_t.c.completion_status, rating_t.c.time_of_submission,
                      rating_t.c.time_taken_to_submit, rater_t.c.name, rater_t.c.email)
            .select_from(rating_t.outerjoin(rater_t, rating_t.c.rater_id == rater_t.c.id))
            .where(rating_t.c.test_id.in_(test_ids))).fetchall()

    for test_id, rater_id, rj, status, submitted, took_ms, name, email in rows:
        if isinstance(rj, str):
            rj = json.loads(rj)
        if not isinstance(rj, dict):
            continue
        af = rj.get('audio_filename')
        if not af:
            continue
        out[af] = {
            'corrected_text': rj.get('text') or '',
            'original_text_at_annotation': rj.get('original_text') or '',
            'corrected_lines': rj.get('corrected_lines'),
            'lines_changed': rj.get('lines_changed'),
            'n_lines_annotated': rj.get('n_lines'),
            'test_id': test_id,
            'item_id': rj.get('id') or rj.get('data_id'),
            'rater_id': rater_id,
            'rater_name': name or '',
            'rater_email': email or rj.get('rater_email') or '',
            'completion_status': status or 'completed',
            'submitted_at': submitted.isoformat() if submitted else '',
            'time_taken_sec': round((took_ms or 0.0) / 1000.0, 1),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, help='delivery folder')
    ap.add_argument('--no-audio', action='store_true')
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(MANIFEST, encoding='utf-8') if l.strip()]
    corrections = fetch_corrections(_engine())
    print('manifest rows: %d   corrections in DB: %d' % (len(rows), len(corrections)))

    missing = [r['audio_filename'] for r in rows if r['audio_filename'] not in corrections]
    if missing:
        print('WARNING: %d manifest rows have no correction:' % len(missing))
        for m in missing[:10]:
            print('   ', m)

    os.makedirs(args.out, exist_ok=True)
    audio_root = os.path.join(args.out, 'audio')

    out_rows, copied, changed_clips, total_lines_changed = [], 0, 0, 0
    for r in rows:
        af = r['audio_filename']                  # aivanta_task/<domain>/<file>.wav
        rel = af.split('/', 1)[1]                 # <domain>/<file>.wav - keeps the 9 colliding basenames apart
        c = corrections.get(af)
        new = dict(r)
        new['audio_filename'] = os.path.join('audio', rel)
        new['audio_filepath'] = os.path.join(args.out, 'audio', rel)
        new['original_text'] = r.get('text') or ''
        if c:
            new['corrected_text'] = c['corrected_text']
            new['lines_changed'] = c['lines_changed']
            new['annotation'] = {k: c[k] for k in (
                'test_id', 'item_id', 'rater_id', 'rater_name', 'rater_email',
                'completion_status', 'submitted_at', 'time_taken_sec', 'n_lines_annotated')}
            if c['corrected_text'] and c['corrected_text'] != (r.get('text') or ''):
                changed_clips += 1
            total_lines_changed += int(c['lines_changed'] or 0)
        else:
            new['corrected_text'] = None
            new['lines_changed'] = None
            new['annotation'] = None
        out_rows.append(new)

        if not args.no_audio:
            src = r['audio_filepath']
            dst = os.path.join(audio_root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                copied += 1
            else:
                print('MISSING AUDIO: %s' % src)

    with open(os.path.join(args.out, 'manifest.jsonl'), 'w', encoding='utf-8') as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    # Raw annotations alongside, for anyone who wants the per-rating detail.
    with open(os.path.join(args.out, 'annotations.jsonl'), 'w', encoding='utf-8') as f:
        for af, c in sorted(corrections.items()):
            f.write(json.dumps(dict(audio_filename=af, **c), ensure_ascii=False) + '\n')

    cols = ['audio_filename', 'domain', 'title', 'test_id', 'item_id', 'rater_name',
            'rater_email', 'completion_status', 'submitted_at', 'time_taken_sec',
            'lines_changed', 'n_lines_annotated', 'original_text', 'corrected_text']
    with open(os.path.join(args.out, 'annotations.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in out_rows:
            a = r.get('annotation') or {}
            w.writerow([r['audio_filename'], r.get('domain', ''), r.get('title', ''),
                        a.get('test_id', ''), a.get('item_id', ''), a.get('rater_name', ''),
                        a.get('rater_email', ''), a.get('completion_status', ''),
                        a.get('submitted_at', ''), a.get('time_taken_sec', ''),
                        r.get('lines_changed', ''), a.get('n_lines_annotated', ''),
                        r.get('original_text', ''), r.get('corrected_text') or ''])

    print('wrote %d manifest rows -> %s/manifest.jsonl' % (len(out_rows), args.out))
    print('audio copied: %d' % copied)
    print('clips whose transcript actually changed: %d/%d' % (changed_clips, len(out_rows)))
    print('total lines changed across all clips: %d' % total_lines_changed)


if __name__ == '__main__':
    main()
