import json
import argparse
import sys
import os

# Add the parent directory or backend root to path to ensure imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend root

from load_config import TestType, populate_database_from_config

def load_jsonl(path: str):
    import re
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                pattern = r'(?<!\\)\\(times|theta|tau|to|text|tfrac|triangle|frac|phi|varphi|forall|beta|binom|bar|bullet|bot|begin|tilde|tan|top|textrm|textbf|textit)\b'
                fixed_line = re.sub(pattern, r'\\\\\1', line)
                item = json.loads(fixed_line)
                data.append(item)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON on line {idx} in {path}: {e}")
                sys.exit(1)
    return data

def normalize_id(item_id):
    if not item_id:
        return ""
    item_id = str(item_id).lower().strip()
    # Strip any language prefix
    languages = ["tamil", "telugu", "marathi", "kannada", "odia", "bengali", "hindi", "malayalam", "urdu", "gujarati"]
    for lang in languages:
        if item_id.startswith(f"{lang}-"):
            item_id = item_id[len(lang)+1:]
            break
    return item_id

def load_jsonl_config(config_path: str, english_path: str = None):
    translated_data = load_jsonl(config_path)
    
    if not english_path:
        # If no English file is provided, just assign IDs if missing and return
        for idx, item in enumerate(translated_data, 1):
            if 'id' not in item:
                item['id'] = idx
        return translated_data
        
    print(f"Aligning with English source: {english_path}")
    english_data = load_jsonl(english_path)
    
    # Map English records by normalized ID
    english_map = {}
    for item in english_data:
        item_id = item.get('id')
        if item_id:
            english_map[normalize_id(item_id)] = item
            
    aligned_data = []
    for idx, trans_item in enumerate(translated_data, 1):
        # Ensure item has ID
        item_id = trans_item.get('id')
        if not item_id:
            item_id = f"item-{idx}"
            trans_item['id'] = item_id
            
        english_item = english_map.get(normalize_id(item_id))
        if english_item:
            # Inject English texts at the top-level
            if 'pre_scene' in english_item:
                trans_item['pre_scene_en'] = english_item['pre_scene']
            if 'post_scene' in english_item:
                trans_item['post_scene_en'] = english_item['post_scene']
            if 'misconception_text' in english_item:
                trans_item['misconception_text_en'] = english_item['misconception_text']
                
            # Align dialogue turns
            for dialogue_key in ['dialogue', 'conversation', 'turns']:
                if dialogue_key in trans_item and isinstance(trans_item[dialogue_key], list):
                    trans_dialogue = trans_item[dialogue_key]
                    eng_dialogue = english_item.get(dialogue_key, [])
                    
                    # Map English turns by turn_index if available, otherwise use index alignment
                    eng_turns_map = {}
                    for eng_turn in eng_dialogue:
                        t_idx = eng_turn.get('turn_index')
                        if t_idx is not None:
                            eng_turns_map[t_idx] = eng_turn
                            
                    for turn_idx, trans_turn in enumerate(trans_dialogue):
                        t_idx = trans_turn.get('turn_index')
                        eng_turn = None
                        if t_idx is not None:
                            eng_turn = eng_turns_map.get(t_idx)
                        elif turn_idx < len(eng_dialogue):
                            eng_turn = eng_dialogue[turn_idx]
                            
                        if eng_turn:
                            # Save original English text inside the translated turn
                            trans_turn['english'] = eng_turn.get('text') or eng_turn.get('english') or eng_turn.get('original')
        else:
            print(f"Warning: No matching English record found for ID {item_id}")
            
        aligned_data.append(trans_item)
        
    return aligned_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Load translation-correction test data from a JSONL config file')
    parser.add_argument('config_path', help='Path to the translated JSONL config file')
    parser.add_argument('--english', help='Path to the original English JSONL config file (optional, for alignment)')
    parser.add_argument('--prolific', action='store_true', help='Create Prolific study')
    parser.add_argument('--description', help='Description of the test (optional)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.config_path):
        print(f"Error: Config file not found at {args.config_path}")
        sys.exit(1)
        
    if args.english and not os.path.exists(args.english):
        print(f"Error: English source file not found at {args.english}")
        sys.exit(1)
        
    config_data = load_jsonl_config(args.config_path, args.english)
    
    test_type = TestType.TRANSLATION_CORRECTION
    
    populate_database_from_config(test_type, config_data, args.prolific, args.description)
