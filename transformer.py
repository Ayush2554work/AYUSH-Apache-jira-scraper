import logging

def clean_text(text):
    """
    A simple text cleaner.
    Jira descriptions can have special markup. For a real project,
    this would be more complex (e.g., using regex or a markup parser).
    """
    if not text:
        return ""
    # Simple cleanup
    text = text.replace("{code}", "```").replace("{noformat}", "```")
    text = text.strip()
    return text

def transform_to_jsonl(issue_data):
    """
    Transforms a single Jira issue JSON object into a structured
    JSONL format for LLM training.
    
    Handles missing data ("malformed data" requirement).
    """
    try:
        fields = issue_data.get('fields', {})
        if not fields:
            raise ValueError("Issue data is missing 'fields'")

        # 1. Extract Metadata
        metadata = {
            "issue_id": issue_data.get('id'),
            "issue_key": issue_data.get('key'),
            "project": (fields.get('project') or {}).get('key'),
            "title": fields.get('summary'),
            "status": (fields.get('status') or {}).get('name'),
            "priority": (fields.get('priority') or {}).get('name'),
            "reporter": (fields.get('reporter') or {}).get('displayName'),
            "assignee": (fields.get('assignee') or {}).get('displayName', 'Unassigned'),
            "created_at": fields.get('created'),
            "updated_at": fields.get('updated'),
            "labels": fields.get('labels', [])
        }
        
        # 2. Extract Plain Text (Description and Comments)
        description = clean_text(fields.get('description'))
        
        comments_list = (fields.get('comment') or {}).get('comments', [])
        comments = [clean_text(c.get('body')) for c in comments_list if c.get('body')]
        
        full_text_context = f"Title: {metadata['title']}\n\nDescription:\n{description}"
        if comments:
            full_text_context += "\n\n--- Comments ---\n" + "\n\n".join(comments)
            
        # 3. Derive Tasks for LLM Training
        derived_tasks = {
            "instruction_summarize": {
                "instruction": "Summarize the following issue, including the problem and all discussion.",
                "input": full_text_context,
                "output": metadata['title'] # A simple example; a better output would be a human-written summary
            },
            "instruction_classify_priority": {
                "instruction": "Based on the issue description, classify its priority (e.g., Blocker, Critical, Major, Minor, Trivial).",
                "input": f"Title: {metadata['title']}\nDescription: {description}",
                "output": metadata['priority']
            },
            "instruction_qna_status": {
                "instruction": f"What is the current status of issue {metadata['issue_key']}?",
                "input": full_text_context,
                "output": metadata['status']
            }
        }
        
        # Final structured object
        output = {
            "doc_id": f"jira_{metadata['issue_key']}",
            "source": "apache_jira",
            "metadata": metadata,
            "text": full_text_context,
            "derived_tasks": derived_tasks
        }
        
        return output

    except Exception as e:
        issue_key = issue_data.get('key', 'UNKNOWN')
        logging.warning(f"Failed to transform issue {issue_key}: {e}. Skipping.")
        return None