import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from application.database import db
from application.models import Team, TeamMember, AdminUser, PoolUpload, PoolItem, Rater, Test, Rating, Message

def serialize_json(val):
    if val is None:
        return ""
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)

def format_dt(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else None

def backup_to_excel(output_path):
    print(f"Starting database backup using app context...")
    with app.app_context():
        # Define exact columns for each sheet to handle empty states gracefully
        TEAM_COLS = ['id', 'key', 'name', 'description', 'workflow', 'accent', 'is_active', 'created_at']
        TEAM_MEMBER_COLS = ['id', 'team_id', 'rater_id', 'role', 'languages', 'pull_size', 'is_active', 'created_at']
        ADMIN_USER_COLS = ['id', 'username', 'password', 'display_name', 'email', 'team_id', 'is_active', 'created_at', 'last_login']
        POOL_UPLOAD_COLS = ['id', 'team_id', 'name', 'source', 'item_count', 'created_at']
        POOL_ITEM_COLS = [
            'id', 'team_id', 'upload_id', 'item_key', 'task_type', 'language', 'class_label',
            'category', 'source_difficulty', 'source', 'n_words', 'text', 'extra_json',
            'status', 'claimed_by', 'claimed_at', 'pull_id', 'final_text', 'final_difficulty',
            'is_edited', 'is_flagged', 'flag_reason', 'notes', 'completed_by', 'completed_at',
            'time_taken_ms', 'revision'
        ]
        RATER_COLS = ['id', 'name', 'email', 'age', 'gender', 'assigned_tasks', 'password', 'is_active', 'prev_assigned_tasks']
        TEST_COLS = ['id', 'test_type', 'description', 'handoff_mode', 'team_id', 'item_count', 'language_hint']
        TEST_ITEM_COLS = ['test_id', 'item_index', 'item_json']
        RATING_COLS = ['id', 'rater_id', 'test_id', 'results_json', 'time_of_submission', 'time_taken_to_submit', 'page_no_progress', 'completion_status', 'verdict']
        MESSAGE_COLS = ['id', 'rater_id', 'body', 'sender', 'category', 'is_read', 'created_at', 'broadcast_id', 'edited_at']

        # 1. Team table
        teams = Team.query.all()
        team_data = [{
            'id': t.id,
            'key': t.key,
            'name': t.name,
            'description': t.description,
            'workflow': t.workflow,
            'accent': t.accent,
            'is_active': t.is_active,
            'created_at': format_dt(t.created_at)
        } for t in teams]
        df_team = pd.DataFrame(team_data, columns=TEAM_COLS)
        print(f"Fetched {len(df_team)} records from Team table.")

        # 2. TeamMember table
        members = TeamMember.query.all()
        member_data = [{
            'id': m.id,
            'team_id': m.team_id,
            'rater_id': m.rater_id,
            'role': m.role,
            'languages': m.languages,
            'pull_size': m.pull_size,
            'is_active': m.is_active,
            'created_at': format_dt(m.created_at)
        } for m in members]
        df_team_member = pd.DataFrame(member_data, columns=TEAM_MEMBER_COLS)
        print(f"Fetched {len(df_team_member)} records from TeamMember table.")

        # 3. AdminUser table
        admins = AdminUser.query.all()
        admin_data = [{
            'id': a.id,
            'username': a.username,
            'password': a.password,
            'display_name': a.display_name,
            'email': a.email,
            'team_id': a.team_id,
            'is_active': a.is_active,
            'created_at': format_dt(a.created_at),
            'last_login': format_dt(a.last_login)
        } for a in admins]
        df_admin_user = pd.DataFrame(admin_data, columns=ADMIN_USER_COLS)
        print(f"Fetched {len(df_admin_user)} records from AdminUser table.")

        # 4. PoolUpload table
        uploads = PoolUpload.query.all()
        upload_data = [{
            'id': u.id,
            'team_id': u.team_id,
            'name': u.name,
            'source': u.source,
            'item_count': u.item_count,
            'created_at': format_dt(u.created_at)
        } for u in uploads]
        df_pool_upload = pd.DataFrame(upload_data, columns=POOL_UPLOAD_COLS)
        print(f"Fetched {len(df_pool_upload)} records from PoolUpload table.")

        # 5. PoolItem table
        pool_items = PoolItem.query.all()
        pool_item_data = [{
            'id': pi.id,
            'team_id': pi.team_id,
            'upload_id': pi.upload_id,
            'item_key': pi.item_key,
            'task_type': pi.task_type,
            'language': pi.language,
            'class_label': pi.class_label,
            'category': pi.category,
            'source_difficulty': pi.source_difficulty,
            'source': pi.source,
            'n_words': pi.n_words,
            'text': pi.text,
            'extra_json': serialize_json(pi.extra_json),
            'status': pi.status,
            'claimed_by': pi.claimed_by,
            'claimed_at': format_dt(pi.claimed_at),
            'pull_id': pi.pull_id,
            'final_text': pi.final_text,
            'final_difficulty': pi.final_difficulty,
            'is_edited': pi.is_edited,
            'is_flagged': pi.is_flagged,
            'flag_reason': pi.flag_reason,
            'notes': pi.notes,
            'completed_by': pi.completed_by,
            'completed_at': format_dt(pi.completed_at),
            'time_taken_ms': pi.time_taken_ms,
            'revision': pi.revision
        } for pi in pool_items]
        df_pool_item = pd.DataFrame(pool_item_data, columns=POOL_ITEM_COLS)
        print(f"Fetched {len(df_pool_item)} records from PoolItem table.")

        # 6. Rater table
        raters = Rater.query.all()
        rater_data = [{
            'id': r.id,
            'name': r.name,
            'email': r.email,
            'age': r.age,
            'gender': r.gender,
            'assigned_tasks': r.assigned_tasks,
            'password': r.password,
            'is_active': r.is_active,
            'prev_assigned_tasks': r.prev_assigned_tasks
        } for r in raters]
        df_rater = pd.DataFrame(rater_data, columns=RATER_COLS)
        print(f"Fetched {len(df_rater)} records from Rater table.")

        # 7. Test table (metadata only) and Test_Item sheet
        tests = Test.query.all()
        test_data = []
        test_item_data = []
        for t in tests:
            test_data.append({
                'id': t.id,
                'test_type': t.test_type,
                'description': t.description,
                'handoff_mode': t.handoff_mode,
                'team_id': t.team_id,
                'item_count': t.item_count,
                'language_hint': t.language_hint
            })
            
            # Split items in json_entry list
            items = t.json_entry
            if isinstance(items, list):
                for idx, item in enumerate(items):
                    test_item_data.append({
                        'test_id': t.id,
                        'item_index': idx,
                        'item_json': json.dumps(item, ensure_ascii=False)
                    })
            elif items is not None:
                test_item_data.append({
                    'test_id': t.id,
                    'item_index': 0,
                    'item_json': json.dumps(items, ensure_ascii=False)
                })

        df_test = pd.DataFrame(test_data, columns=TEST_COLS)
        df_test_item = pd.DataFrame(test_item_data, columns=TEST_ITEM_COLS)
        print(f"Fetched {len(df_test)} records from Test table (metadata).")
        print(f"Extracted {len(df_test_item)} individual items into Test_Item sheet.")

        # 8. Rating table
        ratings = Rating.query.all()
        rating_data = [{
            'id': r.id,
            'rater_id': r.rater_id,
            'test_id': r.test_id,
            'results_json': serialize_json(r.results_json),
            'time_of_submission': format_dt(r.time_of_submission),
            'time_taken_to_submit': r.time_taken_to_submit,
            'page_no_progress': r.page_no_progress,
            'completion_status': r.completion_status,
            'verdict': r.verdict
        } for r in ratings]
        df_rating = pd.DataFrame(rating_data, columns=RATING_COLS)
        print(f"Fetched {len(df_rating)} records from Rating table.")

        # 9. Message table
        messages = Message.query.all()
        message_data = [{
            'id': m.id,
            'rater_id': m.rater_id,
            'body': m.body,
            'sender': m.sender,
            'category': m.category,
            'is_read': m.is_read,
            'created_at': format_dt(m.created_at),
            'broadcast_id': m.broadcast_id,
            'edited_at': format_dt(m.edited_at)
        } for m in messages]
        df_message = pd.DataFrame(message_data, columns=MESSAGE_COLS)
        print(f"Fetched {len(df_message)} records from Message table.")

        # Ensure output directory exists
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        # Write to multi-sheet Excel file
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df_team.to_excel(writer, sheet_name='Team', index=False)
            df_team_member.to_excel(writer, sheet_name='TeamMember', index=False)
            df_admin_user.to_excel(writer, sheet_name='AdminUser', index=False)
            df_pool_upload.to_excel(writer, sheet_name='PoolUpload', index=False)
            df_pool_item.to_excel(writer, sheet_name='PoolItem', index=False)
            df_rater.to_excel(writer, sheet_name='Rater', index=False)
            df_test.to_excel(writer, sheet_name='Test', index=False)
            df_test_item.to_excel(writer, sheet_name='Test_Item', index=False)
            df_rating.to_excel(writer, sheet_name='Rating', index=False)
            df_message.to_excel(writer, sheet_name='Message', index=False)

        print(f"Database successfully backed up to Excel: {output_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backup database to a multi-sheet Excel file")
    parser.add_argument("--output", default="db_backup.xlsx", help="Output XLSX file path")
    args = parser.parse_args()
    
    # Resolve relative paths relative to the saffron root directory
    out_path = args.output
    if not os.path.isabs(out_path):
        out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", out_path))
        
    backup_to_excel(out_path)

