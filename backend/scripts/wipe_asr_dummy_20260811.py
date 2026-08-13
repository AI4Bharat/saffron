#!/usr/bin/env python3
"""ASR reset (dummy annotators + submissions) and TTS member removals.

Everything runs in ONE transaction; a JSON backup of every row touched is
written to the scratchpad before any write.
"""
import json
from datetime import datetime

from dotenv import dotenv_values
from sqlalchemy import create_engine, text

SCRATCH = '/tmp/claude-0/-root-saffron/ac81e77c-47b2-422f-844b-25ed01cd6078/scratchpad'
ASR_TEAM, TTS_TEAM = 2, 1
TTS_REMOVE_RATERS = (76, 78)          # avnishjajodia@gmail.com, pradnyabhagat91@gmail.com
DELETE_RATERS = (77, 79, 80, 81)      # ASR-only dummy accounts, zero footprint elsewhere

uri = dotenv_values('/root/saffron/backend/.env')['DATABASE_URI']
eng = create_engine(uri, connect_args={'connect_timeout': 15})


def rows(c, sql, **p):
    return [dict(r._mapping) for r in c.execute(text(sql), p)]


with eng.connect() as c:
    backup = {
        'taken_at': datetime.utcnow().isoformat(),
        'team_asr': rows(c, "SELECT * FROM team WHERE id = :t", t=ASR_TEAM),
        'team_member_asr': rows(c, "SELECT * FROM team_member WHERE team_id = :t", t=ASR_TEAM),
        'team_member_tts_removed': rows(
            c, "SELECT * FROM team_member WHERE team_id = :t AND rater_id IN :r",
            t=TTS_TEAM, r=TTS_REMOVE_RATERS),
        'team_member_of_deleted_raters': rows(
            c, "SELECT * FROM team_member WHERE rater_id IN :r", r=DELETE_RATERS),
        'pool_task_assignment_asr': rows(
            c, """SELECT a.* FROM pool_task_assignment a
                   JOIN pool_task pt ON pt.id = a.task_id WHERE pt.team_id = :t""", t=ASR_TEAM),
        'pool_pull_asr': rows(c, "SELECT * FROM pool_pull WHERE team_id = :t", t=ASR_TEAM),
        'pool_item_touched': rows(
            c, """SELECT id, status, claimed_by, claimed_at, pull_id, final_text,
                         final_difficulty, is_edited, is_flagged, flag_reason, notes,
                         completed_by, completed_at, time_taken_ms, revision
                    FROM pool_item
                   WHERE team_id = :t AND (status != 'available' OR claimed_by IS NOT NULL
                         OR completed_by IS NOT NULL OR pull_id IS NOT NULL
                         OR final_text IS NOT NULL OR is_edited OR is_flagged)""", t=ASR_TEAM),
        'raters_deleted': rows(c, "SELECT * FROM rater WHERE id IN :r", r=DELETE_RATERS),
    }

path = f"{SCRATCH}/asr_wipe_backup_{datetime.utcnow():%Y%m%d-%H%M%S}.json"
with open(path, 'w', encoding='utf-8') as fh:
    json.dump(backup, fh, ensure_ascii=False, indent=1, default=str)
print('backup:', path)
for k, v in backup.items():
    if isinstance(v, list):
        print(f'  {k}: {len(v)} row(s)')

with eng.begin() as c:
    n = c.execute(text("""
        UPDATE pool_item
           SET status='available', claimed_by=NULL, claimed_at=NULL, pull_id=NULL,
               final_text=NULL, final_difficulty=NULL, is_edited=false, is_flagged=false,
               flag_reason=NULL, notes=NULL, completed_by=NULL, completed_at=NULL,
               time_taken_ms=NULL, revision=0
         WHERE team_id = :t AND (status != 'available' OR claimed_by IS NOT NULL
               OR completed_by IS NOT NULL OR pull_id IS NOT NULL
               OR final_text IS NOT NULL OR is_edited OR is_flagged)"""),
        {'t': ASR_TEAM}).rowcount
    print('pool_item reset to available:', n)

    print('pool_pull deleted:',
          c.execute(text("DELETE FROM pool_pull WHERE team_id = :t"),
                    {'t': ASR_TEAM}).rowcount)
    print('pool_task_assignment deleted:',
          c.execute(text("""DELETE FROM pool_task_assignment a
                             USING pool_task pt
                             WHERE pt.id = a.task_id AND pt.team_id = :t"""),
                    {'t': ASR_TEAM}).rowcount)
    print('team_member (asr) deleted:',
          c.execute(text("DELETE FROM team_member WHERE team_id = :t"),
                    {'t': ASR_TEAM}).rowcount)
    print('team_member (tts: avnish, pradny) deleted:',
          c.execute(text("DELETE FROM team_member WHERE team_id = :t AND rater_id = ANY(:r)"),
                    {'t': TTS_TEAM, 'r': list(TTS_REMOVE_RATERS)}).rowcount)
    # The boot backfill (fixed 2026-08-11) had also given some of these raters TTS rows; every membership of a deleted rater must go or the rater DELETE hits its FK.
    print('remaining memberships of deleted raters:',
          c.execute(text("DELETE FROM team_member WHERE rater_id = ANY(:r)"),
                    {'r': list(DELETE_RATERS)}).rowcount)
    print('message rows for deleted raters:',
          c.execute(text("DELETE FROM message WHERE rater_id = ANY(:r)"),
                    {'r': list(DELETE_RATERS)}).rowcount)
    print('rater accounts deleted:',
          c.execute(text("DELETE FROM rater WHERE id = ANY(:r)"),
                    {'r': list(DELETE_RATERS)}).rowcount)

    settings = dict((backup['team_asr'][0].get('settings') or {}))
    settings['max_open_items'] = 40
    c.execute(text("UPDATE team SET settings = CAST(:s AS json) WHERE id = :t"),
              {'s': json.dumps(settings), 't': ASR_TEAM})
    print('asr team settings ->', settings)

with eng.connect() as c:
    print('\n-- verify --')
    print('asr members left:', c.execute(text(
        "SELECT count(*) FROM team_member WHERE team_id = :t"), {'t': ASR_TEAM}).scalar())
    print('asr item statuses:', rows(c, """
        SELECT status, count(*) AS n FROM pool_item WHERE team_id = :t GROUP BY status""",
        t=ASR_TEAM))
    print('asr pulls/assignments:',
          c.execute(text("SELECT count(*) FROM pool_pull WHERE team_id = :t"),
                    {'t': ASR_TEAM}).scalar(),
          c.execute(text("""SELECT count(*) FROM pool_task_assignment a
                             JOIN pool_task pt ON pt.id = a.task_id
                            WHERE pt.team_id = :t"""), {'t': ASR_TEAM}).scalar())
    print('tts memberships of 76/78:', rows(c, """
        SELECT rater_id, team_id, is_active FROM team_member WHERE rater_id IN (76, 78)"""))
    print('deleted raters still present:', c.execute(text(
        "SELECT count(*) FROM rater WHERE id = ANY(:r)"), {'r': list(DELETE_RATERS)}).scalar())
    print('asr team settings now:', c.execute(text(
        "SELECT settings FROM team WHERE id = :t"), {'t': ASR_TEAM}).scalar())
