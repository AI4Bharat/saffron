#!/usr/bin/env bash
# Give backend/ a predictable shape without breaking a single existing command.
#
# Modules the app IMPORTS (main.py, admin_reports.py, audio_set_labels.py,
# application/) stay exactly where they are. Standalone CLI scripts move into
# loaders/ exporters/ tools/ scripts/, and a symlink is left at the old path so
# `./venv/bin/python load_x.py ...` keeps working verbatim.
set -u
cd /root/saffron/backend || exit 1
mkdir -p loaders exporters tools scripts

# Imported by the running app -- must remain importable from the backend root.
KEEP="main.py admin_reports.py audio_set_labels.py"

move() {          # move <dest-dir> <file>
  local dest=$1 f=$2
  [ -f "$f" ] || return 0
  [ -L "$f" ] && return 0
  case " $KEEP " in *" $f "*) return 0 ;; esac
  mv "$f" "$dest/" && ln -sfn "$dest/$f" "$f" && echo "   $f -> $dest/"
}

echo "== loaders/"
for f in load_*.py split_and_load.py prepare_scripted_mos.py manage_dummy_test.py; do move loaders "$f"; done

echo "== exporters/"
for f in export_*.py backup_db_to_excel.py restore_db_from_excel.py generate_docs.py \
         generate_missing_excels.py docx_to_excel.py update_status_report.py summarize_db.py; do
  move exporters "$f"
done

echo "== tools/"
for f in audit_docx_vs_excel.py backfill_audio_set_labels.py delete_raters.py delete_tasks.py \
         db_clear.py fix_latex_recovery.py organize_pending_excels.py qc_inspect_worker.py \
         qc_load_worker.py qc_upload_jobs.py sync_all_state.py transliterate_conversations.py \
         transliterate_excels.py drive_sync.py update_email.py load_config.py; do
  move tools "$f"
done

echo "== scripts/ (ops)"
for f in start_saffron.sh restart_saffron.sh; do
  [ -f "$f" ] && [ ! -L "$f" ] && mv "$f" scripts/ && ln -sfn "scripts/$f" "$f" && echo "   $f -> scripts/"
done

echo
echo "== backend root now holds:"
ls -p | grep -v / | sed 's/^/   /'
echo "== directories:"
ls -d */ | sed 's/^/   /'
