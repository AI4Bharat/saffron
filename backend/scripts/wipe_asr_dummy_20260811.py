#!/usr/bin/env python3
"""Remove the LAST of the pre-launch dummy ASR annotators and their traces.

Rewritten 2026-08-13: the original wipe (written 2026-08-11) reset the whole
team, but ASR now has real annotators (approval flow) and 5,600 live MDFS
items — so this version touches ONLY the known dummy raters:

  76 avnishjajodia@gmail.com   (account kept; already deactivated everywhere)
  77 kunalgandhi@ai4bharat.org (account kept; already deactivated everywhere)
  79 pradnyabhagat@ai4bharat.org  -> account deleted
  80 sandeepkaursk568@gmail.com   -> account deleted
  81 anmoljangra21@gmail.com      -> account deleted

Their claimed/completed pool items go back to 'available', their pulls,
assignments and memberships are removed, and the three ASR-only dummy
accounts are deleted. Everything runs in ONE transaction; a JSON backup of
every affected row is written first.
"""
import json
from datetime import datetime

from dotenv import dotenv_values
from sqlalchemy import create_engine, text

SCRATCH = '/tmp/claude-0/-root-saffron/ac81e77c-47b2-422f-844b-25ed01cd6078/scratchpad'
DUMMY_RATERS = [76, 77, 79, 80, 81]     # traces reset for all of these
DELETE_RATERS = [79, 80, 81]            # accounts removed (zero footprint elsewhere)
ASR_TEAM = 2

uri = dotenv_values('/root/saffron/backend/.env')['DATABASE_URI']
eng = create_engine(uri, connect_args={'connect_timeout': 15})


def rows(c, sql, **p):
    return [dict(r._mapping) for r in c.execute(text(sql), p)]


with eng.connect() as c:
    backup = {
        'taken_at': datetime.utcnow().isoformat(),
        'team_member': rows(c, "SELECT * FROM team_member WHERE rater_id = ANY(:r)",
                            r=DUMMY_RATERS),
        'pool_task_assignment': rows(
            c, "SELECT * FROM pool_task_assignment WHERE rater_id = ANY(:r)", r=DUMMY_RATERS),
        'pool_pull': rows(c, "SELECT * FROM pool_pull WHERE rater_id = ANY(:r)", r=DUMMY_RATERS),
        'pool_item_touched': rows(
            c, """SELECT id, status, claimed_by, claimed_at, pull_id, final_text,
                         final_difficulty, is_edited, is_flagged, flag_reason, notes,
                         completed_by, completed_at, time_taken_ms, revision, extra_json
                    FROM pool_item
                   WHERE claimed_by = ANY(:r) OR completed_by = ANY(:r)""", r=DUMMY_RATERS),
        'raters_deleted': rows(c, "SELECT * FROM rater WHERE id = ANY(:r)", r=DELETE_RATERS),
        'messages_deleted': rows(c, "SELECT * FROM message WHERE rater_id = ANY(:r)",
                                 r=DELETE_RATERS),
    }

path = f"{SCRATCH}/asr_dummy_wipe_backup_{datetime.utcnow():%Y%m%d-%H%M%S}.json"
with open(path, 'w', encoding='utf-8') as fh:
    json.dump(backup, fh, ensure_ascii=False, indent=1, default=str)
print('backup:', path)
for k, v in backup.items():
    if isinstance(v, list):
        print(f'  {k}: {len(v)} row(s)')

with eng.begin() as c:
    print('items reset to available:', c.execute(text("""
        UPDATE pool_item
           SET status='available', claimed_by=NULL, claimed_at=NULL, pull_id=NULL,
               final_text=NULL, final_difficulty=NULL, is_edited=false, is_flagged=false,
               flag_reason=NULL, notes=NULL, completed_by=NULL, completed_at=NULL,
               time_taken_ms=NULL, revision=0,
               extra_json = CASE WHEN extra_json IS NULL THEN NULL
                                 ELSE CAST((CAST(extra_json AS jsonb) - 'results') AS json) END
         WHERE claimed_by = ANY(:r) OR completed_by = ANY(:r)"""),
        {'r': DUMMY_RATERS}).rowcount)
    print('pulls deleted:', c.execute(text(
        "DELETE FROM pool_pull WHERE rater_id = ANY(:r)"), {'r': DUMMY_RATERS}).rowcount)
    print('assignments deleted:', c.execute(text(
        "DELETE FROM pool_task_assignment WHERE rater_id = ANY(:r)"),
        {'r': DUMMY_RATERS}).rowcount)
    print('memberships deleted:', c.execute(text(
        "DELETE FROM team_member WHERE rater_id = ANY(:r)"), {'r': DUMMY_RATERS}).rowcount)
    print('messages deleted:', c.execute(text(
        "DELETE FROM message WHERE rater_id = ANY(:r)"), {'r': DELETE_RATERS}).rowcount)
    print('dummy accounts deleted:', c.execute(text(
        "DELETE FROM rater WHERE id = ANY(:r)"), {'r': DELETE_RATERS}).rowcount)

    merged = rows(c, "SELECT settings FROM team WHERE id = :t", t=ASR_TEAM)[0]['settings'] or {}
    merged['max_open_items'] = merged.get('max_open_items', 40)
    c.execute(text("UPDATE team SET settings = CAST(:s AS json) WHERE id = :t"),
              {'s': json.dumps(merged), 't': ASR_TEAM})
    print('asr team settings ->', merged)

with eng.connect() as c:
    print('\n-- verify --')
    print('remaining traces:', c.execute(text(
        "SELECT count(*) FROM pool_item WHERE claimed_by = ANY(:r) OR completed_by = ANY(:r)"),
        {'r': DUMMY_RATERS}).scalar())
    print('remaining memberships:', c.execute(text(
        "SELECT count(*) FROM team_member WHERE rater_id = ANY(:r)"),
        {'r': DUMMY_RATERS}).scalar())
    print('deleted accounts still present:', c.execute(text(
        "SELECT count(*) FROM rater WHERE id = ANY(:r)"), {'r': DELETE_RATERS}).scalar())
