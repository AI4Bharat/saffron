#!/usr/bin/env bash
# Tidy /root/saffron into a predictable layout.
#
# RULES
#   * nothing the running app reads is moved out of place -- task data folders
#     stay reachable at their old paths via symlinks, so every loader script and
#     the audio endpoint keep working;
#   * nothing is deleted: superseded .bak copies are ARCHIVED, not removed;
#   * every step is idempotent, so this can be re-run safely.
set -u
ROOT=/root/saffron
cd "$ROOT" || exit 1

ARCHIVE="$ROOT/_archive"
mkdir -p "$ARCHIVE/backups" "$ARCHIVE/scratch" "$ROOT/docs" "$ROOT/backend/state" "$ROOT/backend/logs"

echo "== 1. archive superseded .bak / .BROKEN copies (moved, never deleted)"
moved=0
while IFS= read -r f; do
  rel="${f#./}"
  dest="$ARCHIVE/backups/$(dirname "$rel")"
  mkdir -p "$dest"
  mv -n "$f" "$dest/" 2>/dev/null && moved=$((moved+1))
done < <(find . -path ./.git -prune -o -path ./_archive -prune -o \
              \( -name '*.bak' -o -name '*.bak_*' -o -name '*.bak.*' \
                 -o -name '*.BROKEN*' -o -name '*.done' \) -print)
echo "   archived $moved file(s)"

echo "== 2. project docs -> docs/"
for f in BATCH_INSTRUCTIONS.md BENCHMARK_EVALUATION_V2_TASKS.md BENCHMARK_PARALLEL_TASKS.md \
         BENCHMARK_TASKS.md conversation_editable_status.md GETTING_STARTED.md \
         SAFFRON_ARCHITECTURE.md SAFFRON_CODEBASE_GUIDE.md; do
  [ -f "$f" ] && mv -n "$f" docs/
done
[ -d pipeline_docs ] && [ ! -d docs/pipeline_docs ] && mv -n pipeline_docs docs/
echo "   docs/: $(ls docs | wc -l) file(s)"

echo "== 3. one-off scratch files -> _archive/scratch/"
for f in test_direct_download.wav test_download test_export_1.jsonl dummy_english.jsonl \
         dummy_hindi.jsonl db_summary.csv audio_segmentation_rejection_reasons.csv \
         audio_segmentation_rejection_summary.csv error.log; do
  [ -f "$f" ] && mv -n "$f" "$ARCHIVE/scratch/"
done
cd backend || exit 1
for f in dummy_hindi_corrected.jsonl emails_to_delete.txt docx_excel_audit.csv \
         docx_excel_audit.json benchmark_v2_rows_backup_20260731_123516.json temp.py; do
  [ -f "$f" ] && mv -n "$f" "$ARCHIVE/scratch/"
done

echo "== 4. pipeline state files -> backend/state/ (symlinked back)"
for f in audio_segmentation_state.csv excel_sets_state.csv upload_sets_state.csv \
         version_state.csv signup_key.txt; do
  if [ -f "$f" ] && [ ! -L "$f" ]; then
    mv -n "$f" state/ && ln -sfn "state/$f" "$f"
  fi
done
ls state/ | sed 's/^/   state\//'

echo "== 5. logs -> backend/logs/ (symlinked back)"
for f in error.log error.log.1 gunicorn.log transliterate.log; do
  if [ -f "$f" ] && [ ! -L "$f" ]; then
    mv -n "$f" logs/ && ln -sfn "logs/$f" "$f"
  fi
done

echo "== 6. task data -> backend/tasks/<name> (old paths kept as symlinks)"
mkdir -p tasks
for d in conversation_tasks conversation_editable_tasks benchmark_tasks benchmark_tasks_new \
         benchmark_tasks_v2 benchmark_updated_v2 benchmark_exports; do
  if [ -d "$d" ] && [ ! -L "$d" ]; then
    mv "$d" tasks/ && ln -sfn "tasks/$d" "$d"
    echo "   moved $d -> tasks/$d (symlink left behind)"
  fi
done

echo "== 7. python caches"
find . -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null
echo "   done"

echo
echo "== resulting layout =="
cd "$ROOT"
ls -d */ | sed 's/^/  /'
echo "  backend/:"
ls -d backend/*/ | sed 's/^/    /'
