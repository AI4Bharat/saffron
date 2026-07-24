"""
Safe LaTeX corruption recovery for the Saffron DB.

Background (all verified before writing this):
  * These tasks originally contained LaTeX (\\times, \\theta, \\frac, \\beta, ...).
  * An old bad load turned control-escapes into raw control chars:
        \\t -> TAB, \\f -> FF, \\b -> BS   (so \\times->TABimes, \\frac->FFrac, \\beta->BSeta)
    This state is captured verbatim in db_backup.xlsx (Jul-8 snapshot).
  * On Jul-10 fix_database_escapes.py ran; its buggy regexes (\\b = word-boundary,
    \\t/\\f = literal control chars) made it WORSE: it prepended stray backslashes,
    turning legit \\eta -> \\\\eta, BSeta -> BS\\eta, TABimes -> \\imes, etc.
  * PROVEN: wrong_script(backup) == current for ALL 721 tests -> current is a pure
    function of the Jul-8 backup, so restoring cleaned-backup values loses nothing.

Recovery:
  * det_fix(x): repair the ORIGINAL control-char corruption in a Jul-8 (pre-Jul-10) string.
  * TEST rows: task definitions are never annotator-edited -> set json_entry = det_fix(backup).
  * RATING rows: only touch rows that are UNCHANGED since backup
    (wrong_script(backup)==current); restore results_json = det_fix(backup).
    New/edited annotations (3282 new + edited) are left untouched, except a few
    new rows carrying the SAME \\\\eta artifact get the safe targeted inverse.
"""
import os, sys, json, re, argparse
sys.path.append('/root/saffron/backend')
os.chdir('/root/saffron/backend')
import openpyxl
from main import app
from application.database import db
from application.models import Test, Rating

# ---------- transforms ----------
def det_fix(s):
    """Repair original control-char corruption in a pre-Jul10 string."""
    if not isinstance(s, str): return s
    s = s.replace('\x08', '\\b')      # BS  -> \b  (\beta \bar \binom \begin \bullet \bot)
    s = s.replace('\x0c', '\\f')      # FF  -> \f  (\frac \forall)
    # TAB stood for \t : tab+imes -> \times (tab ate the 't'); tab+times -> \times (word intact)
    s = re.sub('\t' + r'(imes|heta|au|riangle|ilde|op|an|ext|frac|extrm|extbf|extit)\b', r'\\t\1', s)
    s = re.sub('\t' + r'(times|theta|tau|triangle|tilde|top|tan|text|tfrac|frac)\b', r'\\\1', s)
    s = s.replace('\t', '\\t')        # any remaining tab -> \t
    return s

def inverse_fix(s):
    """Undo the Jul-10 buggy script on a CURRENT string, then det_fix."""
    if not isinstance(s, str): return s
    s = s.replace('\x08\\', '\x08')                               # undo stray '\' after backspace
    s = re.sub(r'\\\\(eta|inom|ar|ullet|ot|egin)\b', r'\\\1', s)  # \\eta -> \eta
    return det_fix(s)

def wrong_script(s):
    if not isinstance(s, str): return s
    s = re.sub(r'\t(imes|heta|au|o\b|ext|frac|riangle|textrm|extbf|extit|ilde|an\b|op\b)', r'\\\1', s)
    s = re.sub(r'\f(rac|hi\b|arphi|orall)', r'\\\1', s)
    s = re.sub(r'\b(eta\b|inom|ar\b|ullet|ot\b|egin)', r'\\\1', s)
    return s

def deep(f, o):
    if isinstance(o, dict): return {k: deep(f, v) for k, v in o.items()}
    if isinstance(o, list): return [deep(f, x) for x in o]
    if isinstance(o, str): return f(o)
    return o
def J(o): return json.dumps(o, ensure_ascii=False, sort_keys=True)
def residual(o):
    s = json.dumps(o, ensure_ascii=False)
    r = s.count('\x08') + s.count('\t') + s.count('\x0c')
    r += len(re.findall(r'\\\\\\\\(eta|inom|ar|ullet|ot|egin)\b', s))  # \\<greek> -> 4 backslashes in dumps
    return r
def has_artifact(o):
    s = json.dumps(o, ensure_ascii=False)
    if s.count('\x08') or s.count('\t') or s.count('\x0c'): return True
    return bool(re.search(r'\\\\\\\\(eta|inom|ar|ullet|ot|egin)\b', s))

# ---------- load backup ----------
print("Loading backup xlsx (this takes ~1 min)...")
wb = openpyxl.load_workbook("/root/saffron/db_backup.xlsx", read_only=True, data_only=True)
ws = wb['Test_Item']; bt = {}
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0: continue
    bt.setdefault(row[0], {})[row[1]] = row[2]
backup_test = {}
for tid, items in bt.items():
    o = [items[k] for k in sorted(items)]
    try: backup_test[tid] = json.loads(o[0]) if len(o) == 1 else [json.loads(x) for x in o]
    except Exception: backup_test[tid] = None
ws = wb['Rating']; backup_rating = {}
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0: continue
    try: backup_rating[row[0]] = json.loads(row[3]) if row[3] else None
    except Exception: backup_rating[row[0]] = None
print(f"backup: {len(backup_test)} tests, {len(backup_rating)} ratings")

def main(commit):
    with app.app_context():
        # ---------------- TESTS ----------------
        test_updates = []   # (obj_id, new_value)
        skipped_no_backup = []
        for t in Test.query.all():
            if t.id not in backup_test or backup_test[t.id] is None:
                if has_artifact(t.json_entry):
                    skipped_no_backup.append(t.id)
                continue
            clean = deep(det_fix, backup_test[t.id])
            assert residual(clean) == 0, f"residual in test {t.id}"
            # safety: current must be wrong_script(backup) -> proves no legit divergence
            assert J(deep(wrong_script, backup_test[t.id])) == J(t.json_entry), \
                f"test {t.id}: current != wrong_script(backup); NOT restoring"
            if J(clean) != J(t.json_entry):
                test_updates.append((t, clean))
        print(f"\nTEST rows to restore from cleaned backup: {len(test_updates)}")
        print(f"TEST rows with artifacts but NOT in backup (left as-is): {skipped_no_backup}")

        # ---------------- RATINGS ----------------
        rating_updates = []
        rest_count = new_artifact = 0
        for r in Rating.query.all():
            if not r.results_json: continue
            in_bk = (r.id in backup_rating and backup_rating[r.id] is not None)
            restorable = in_bk and (J(deep(wrong_script, backup_rating[r.id])) == J(r.results_json))
            if restorable:
                clean = deep(det_fix, backup_rating[r.id])
                assert residual(clean) == 0, f"residual in rating {r.id}"
                if J(clean) != J(r.results_json):
                    rating_updates.append((r, clean)); rest_count += 1
            else:
                # new or edited since backup: only touch if it carries the SAME artifact
                if has_artifact(r.results_json):
                    clean = deep(inverse_fix, r.results_json)
                    assert residual(clean) == 0, f"residual in new rating {r.id}"
                    if J(clean) != J(r.results_json):
                        rating_updates.append((r, clean)); new_artifact += 1
        print(f"RATING rows to fix: {len(rating_updates)}  (restorable-from-backup={rest_count}, new/edited-artifact={new_artifact})")

        # ---------------- sample diffs ----------------
        def vis(s): return s.replace('\x08','<BS>').replace('\t','<TAB>').replace('\x0c','<FF>')
        def show(pairs, n):
            for obj, clean in pairs[:n]:
                a = vis(J(obj.json_entry if isinstance(obj, Test) else obj.results_json))
                b = vis(J(clean))
                k = next((i for i in range(min(len(a),len(b))) if a[i]!=b[i]), 0)
                tag = f"Test {obj.id}" if isinstance(obj, Test) else f"Rating {obj.id}"
                print(f"  --- {tag} ---")
                print(f"    before: ...{a[max(0,k-45):k+45]}...")
                print(f"    after : ...{b[max(0,k-45):k+45]}...")
        print("\nSample TEST diffs:");   show(test_updates, 3)
        print("Sample RATING diffs:");   show(rating_updates, 4)

        if not commit:
            print("\n[DRY RUN] no changes written. Re-run with --commit to apply.")
            return
        # ---------------- write ----------------
        for t, clean in test_updates:
            t.json_entry = clean
        for r, clean in rating_updates:
            r.results_json = clean
        db.session.commit()
        print(f"\n[COMMITTED] {len(test_updates)} tests + {len(rating_updates)} ratings updated.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args()
    main(a.commit)
