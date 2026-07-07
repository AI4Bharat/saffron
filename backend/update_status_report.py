import os
import sys
import json
import glob
import re
from collections import defaultdict

def clean_text_for_match(text):
    if not text:
        return ""
    # Keep only alphanumeric characters (works for all Unicode scripts)
    return "".join(c for c in text if c.isalnum()).lower()

def update_status():
    print("\n[Status Autoupdate] Starting status report compilation...")
    try:
        # Import docx locally to avoid crash if docx is not installed in the environment where the script is called
        from docx import Document
    except ImportError:
        print("[Status Autoupdate] Warning: python-docx not installed. Skipping DOCX analysis.")
        Document = None

    try:
        # Import Flask app and models locally
        from main import app
        from application.database import db
        from application.models import Test
        
        editable_tasks_dir = "/root/saffron/backend/conversation_editable_tasks"
        exports_dir = "/root/saffron/backend/exports"
        docx_dir = "/root/saffron/backend/exports/docx"
        report_path = "/root/saffron/conversation_editable_status.md"

        # 1. Indexing all conversations from docx files
        docx_pre_scenes = {}
        if Document:
            docx_files = glob.glob(os.path.join(docx_dir, "*.docx"))
            for path in docx_files:
                filename = os.path.basename(path)
                try:
                    doc = Document(path)
                    for p in doc.paragraphs:
                        text = p.text.strip()
                        if text.startswith("Pre-Scene:"):
                            pre_scene_text = text[len("Pre-Scene:"):].strip()
                            cleaned = clean_text_for_match(pre_scene_text)
                            if cleaned:
                                if cleaned not in docx_pre_scenes:
                                    docx_pre_scenes[cleaned] = set()
                                docx_pre_scenes[cleaned].add(filename)
                except Exception as e:
                    print(f"[Status Autoupdate] Error reading docx {filename}: {e}")

        # 2. Scanning database for conversation-editable tests
        db_tests = []
        with app.app_context():
            tests = Test.query.filter(Test.test_type == "conversation-editable").all()
            for test in tests:
                desc = test.description or ""
                parts = [p.strip() for p in desc.split(" - ")]
                lang = parts[1].lower() if len(parts) > 1 else ""
                persona = parts[2].lower().replace(" ", "_") if len(parts) > 2 else ""
                grade = parts[3].lower().replace(" ", "_") if len(parts) > 3 else ""
                
                version = ""
                batch_info = ""
                for p in parts[4:]:
                    if p.lower().startswith("part "):
                        batch_info = p
                    else:
                        version = p.lower().replace(" ", "_")
                
                if not version:
                    version = "version_1"
                    
                db_tests.append({
                    "id": test.id,
                    "description": desc,
                    "language": lang,
                    "persona": persona,
                    "grade": grade,
                    "version": version,
                    "batch_info": batch_info,
                    "total_tasks": len(test.json_entry) if test.json_entry else 0
                })

        # 3. Scanning exports directory
        exports_map = {}
        export_files = glob.glob(os.path.join(exports_dir, "*.jsonl"))
        for path in export_files:
            filename = os.path.basename(path)
            if "conversation-editable" not in filename:
                continue
            
            match = re.match(r"^(\d+)_conversation-editable_conversation_editable___([a-z0-9_]+)___([a-z0-9_]+)___([a-z0-9_]+)___([a-z0-9_]+)\.jsonl$", filename)
            if match:
                test_id, lang, persona, grade, version = match.groups()
                key = (lang, persona, grade, version)
                if key not in exports_map:
                    exports_map[key] = []
                exports_map[key].append({
                    "test_id": int(test_id),
                    "filename": filename,
                    "size_kb": round(os.path.getsize(path) / 1024, 1)
                })

        # 4. Scanning source task files
        source_tasks = []
        for root, dirs, files in os.walk(editable_tasks_dir):
            for file in sorted(files):
                if file.endswith(".jsonl"):
                    full_path = os.path.join(root, file)
                    rel_dir = os.path.relpath(root, editable_tasks_dir)
                    version = "version_1" if rel_dir == "." else rel_dir
                    
                    base = os.path.splitext(file)[0]
                    if base.startswith("conversations_"):
                        base = base[len("conversations_"):]
                    elif base.startswith("conversation_"):
                        base = base[len("conversation_"):]
                    
                    tokens = base.split("_")
                    lang = tokens[0]
                    
                    grade_tokens = []
                    persona_tokens = []
                    is_grade = False
                    for t in tokens[1:]:
                        if t in ["elementary", "middle", "secondary", "senior"]:
                            is_grade = True
                        if is_grade:
                            grade_tokens.append(t)
                        else:
                            persona_tokens.append(t)
                    
                    persona = "_".join(persona_tokens)
                    grade = "_".join(grade_tokens)
                    
                    tasks = []
                    matched_docx = set()
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                if not line.strip():
                                    continue
                                item = json.loads(line)
                                tasks.append(item)
                                data = item if 'data' not in item else item['data']
                                pre_scene = data.get('pre_scene') or ''
                                cleaned = clean_text_for_match(pre_scene)
                                if cleaned in docx_pre_scenes:
                                    matched_docx.update(docx_pre_scenes[cleaned])
                    except Exception as e:
                        print(f"[Status Autoupdate] Error reading source file {file}: {e}")
                    
                    matching_db = [t for t in db_tests if t["language"] == lang and t["persona"] == persona and t["grade"] == grade and t["version"] == version]
                    db_status = "Imported" if matching_db else "Not Imported"
                    db_ids = [t["id"] for t in matching_db]
                    
                    key = (lang, persona, grade, version)
                    matching_exports = exports_map.get(key, [])
                    export_status = "Exported" if matching_exports else "Not Exported"
                    export_details = [f"ID {e['test_id']} ({e['size_kb']} KB)" for e in matching_exports]
                    
                    docx_status = "Generated" if matched_docx else "Not Generated"
                    
                    source_tasks.append({
                        "file": file,
                        "version": version,
                        "language": lang,
                        "persona": persona,
                        "grade": grade,
                        "task_count": len(tasks),
                        "db_status": db_status,
                        "db_ids": db_ids,
                        "export_status": export_status,
                        "export_details": export_details,
                        "docx_status": docx_status,
                        "docx_files": sorted(list(matched_docx))
                    })

        # 5. Writing status report to markdown
        report_content = []
        report_content.append("# Saffron Conversation Editable Tasks Status Report")
        report_content.append(f"Auto-generated on: 2026-07-07\n")
        report_content.append("This document tracks the import, export, and document generation status of the editable dialogue tasks located under `backend/conversation_editable_tasks/`.\n")

        report_content.append("## High-Level Summary by Language")
        report_content.append("| Language | Total Files | Imported | Exported | DOCX Generated |")
        report_content.append("| --- | --- | --- | --- | --- |")

        lang_summary = defaultdict(lambda: {"total": 0, "imported": 0, "exported": 0, "docx": 0})
        for t in source_tasks:
            lang = t["language"].capitalize()
            lang_summary[lang]["total"] += 1
            if t["db_status"] == "Imported":
                lang_summary[lang]["imported"] += 1
            if t["export_status"] == "Exported":
                lang_summary[lang]["exported"] += 1
            if t["docx_status"] == "Generated":
                lang_summary[lang]["docx"] += 1

        for lang, counts in sorted(lang_summary.items()):
            report_content.append(f"| **{lang}** | {counts['total']} | {counts['imported']} / {counts['total']} | {counts['exported']} / {counts['total']} | {counts['docx']} / {counts['total']} |")

        languages_list = sorted(list(set(t["language"] for t in source_tasks)))
        for lang in languages_list:
            report_content.append(f"\n## Language: {lang.capitalize()}")
            
            lang_tasks = [t for t in source_tasks if t["language"] == lang]
            versions_in_lang = sorted(list(set(t["version"] for t in lang_tasks)))
            
            for ver in versions_in_lang:
                ver_display = ver.replace("_", " ").title()
                report_content.append(f"\n### {ver_display}")
                report_content.append("| File Name | Tasks | DB Status | Export Status | DOCX Status | Target DOCX / Details |")
                report_content.append("| --- | --- | --- | --- | --- | --- |")
                
                ver_tasks = [t for t in lang_tasks if t["version"] == ver]
                for t in sorted(ver_tasks, key=lambda x: (x["persona"], x["grade"])):
                    db_str = f"✓ Yes (IDs: {', '.join(map(str, t['db_ids']))})" if t["db_status"] == "Imported" else "✗ No"
                    exp_str = f"✓ Yes ({', '.join(t['export_details'])})" if t["export_status"] == "Exported" else "✗ No"
                    
                    if t["docx_status"] == "Generated":
                        docx_str = "✓ Yes"
                        docx_details = ", ".join(t["docx_files"])
                    else:
                        docx_str = "✗ No"
                        docx_details = "-"
                        
                    report_content.append(f"| `{t['file']}` | {t['task_count']} | {db_str} | {exp_str} | {docx_str} | {docx_details} |")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_content))

        print(f"[Status Autoupdate] Successfully updated report at: {report_path}")

    except Exception as e:
        print(f"[Status Autoupdate] Error during auto-update execution: {e}")

if __name__ == "__main__":
    update_status()
