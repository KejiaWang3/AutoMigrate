import argparse
import os
import sys
import base64
import requests
import pandas as pd
import subprocess

def get_auth_header(username, token):
    return {
        'Authorization': 'Basic ' + base64.b64encode(f"{username}:{token}".encode()).decode('utf-8'),
        'Content-Type': 'application/json'
    }

def ensure_pages_exist(base_url, path_parts, username, token, space_key):
    headers = get_auth_header(username, token)
    last_page_name = None

    for part in path_parts:
        page_title = part.replace('_', ' ')
        last_page_name = page_title
        search_url = f"{base_url}/rest/api/content?title={page_title}&spaceKey={space_key}&expand=history.lastUpdated"
        response = requests.get(search_url, headers=headers)
        if response.status_code == 200 and response.json()['size'] > 0:
            ancestor_id = response.json()['results'][0]['id']
        else:
            data = {
                "type": "page",
                "title": page_title,
                "ancestors": [{"id": ancestor_id}] if ancestor_id else [],
                "space": {"key": space_key},
                "body": {
                    "storage": {
                        "value": "<p>Created automatically by the script.</p>",
                        "representation": "storage"
                    }
                }
            }
            create_url = f"{base_url}/rest/api/content"
            create_response = requests.post(create_url, headers=headers, json=data)
            if create_response.status_code != 200:
                print(f"Failed to create page {page_title}, error: {create_response.text}")
                return None

    return last_page_name

def parse_parent_page_and_path(link):
    # parts = [part.strip() for part in link.split('\') if part.strip()]
    parts = [part.strip() for part in link.split('\\') if part.strip()]
    if len(parts) > 2:
        parent_page_parts = parts[:-1]
        full_path = '\\\\' + '\\'.join(parts)
        if not full_path.lower().endswith('.md'):
            full_path += '.md'
        return parent_page_parts, full_path
    return [], ""

def migrate_documents(contains_sensitive_words, username, token, base_url, space_key):
    df = pd.read_excel('updated_report.xlsx')
    if contains_sensitive_words.lower() == 'no':
        df_filtered = df[df['Contains Sensitive Words'].str.lower() == 'no']
    else:
        df_filtered = df

    for index, row in df_filtered.iterrows():
        if row['File Type'] == 'md':
            path_parts, full_md_path = parse_parent_page_and_path(row['Link'])
            if os.path.exists(full_md_path):
                last_page_name = ensure_pages_exist(base_url, path_parts, username, token, space_key)
                if last_page_name:
                    command = f"python md2conf.py \"{full_md_path}\" {space_key} -a \"{last_page_name}\" -u \"{username}\" -p \"{token}\" -o dpdd"
                    subprocess.run(command, shell=True)
                else:
                    print(f"Failed to ensure Confluence page structure for {full_md_path}")
            else:
                print(f"Error: Markdown file does not exist: {full_md_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate markdown documents to Confluence pages.")
    parser.add_argument("contains_sensitive_words", help="Specify if the documents contain sensitive words (yes/no).")
    parser.add_argument("-u", "--username", default=os.environ.get('CONFLUENCE_USERNAME'), help="Confluence username.")
    parser.add_argument("-p", "--apikey", default=os.environ.get('CONFLUENCE_API_KEY'), help="Confluence API key.")
    parser.add_argument("-b", "--baseurl", default=os.environ.get('CONFLUENCE_BASE_URL'), help="Confluence base URL.")
    parser.add_argument("-s", "--spacekey", default=os.environ.get('CONFLUENCE_SPACE_KEY'), help="Confluence space key.")
    args = parser.parse_args()

    migrate_documents(args.contains_sensitive_words, args.username, args.apikey, args.baseurl, args.spacekey)
