import imaplib
import email
import os
import re
from email.header import decode_header
import ollama

# ================= 配置区 =================
GMAIL_USER = 'chujun.yang@ontra.ai'
GMAIL_PASS = 'icgqnzuighupvrnx'  
# SAVE_ROOT = r'D:\NDA Review'
SAVE_ROOT = r'/Users/zrr/projects/ailegal/nda_demo/rory_output'
# =========================================

def ask_ai_for_project_advanced(subject, body, filename):
    """
    Extract a short project/company folder name via LLM.
    Robust against verbose LLM responses.
    """
    prompt = f"""Subject: {subject}
Body snippet: {body[:300]}
Attachment: {filename}

Extract a short folder name (1-3 words) from the above email.
Use the project name or target company name.
Use underscores between words. No explanation. No sentences.

Examples:
- "NDA for Tesla acquisition" → Tesla_NDA
- "Crown project  documents" → Crown
- "Lease agreement Skyline Corp" → Skyline_Lease

Reply with ONLY the folder name, nothing else:"""

    try:
        response = ollama.chat(model='llama3.2', messages=[
            {'role': 'system', 'content': 'Reply with ONLY a short folder name (1-3 words, underscores). No explanation. No sentences. No quotes.'},
            {'role': 'user', 'content': prompt},
        ])
        raw = response['message']['content'].strip()
        project = _sanitize_folder_name(raw)
        return project if project else "General_Archive"
    except Exception as e:
        print(f"⚠️ AI extraction failed: {e}")
        return "General_Archive"


def _sanitize_folder_name(raw: str) -> str:
    """Post-process LLM output into a safe, short folder name."""
    line = raw.split('\n')[0].strip()

    for prefix in ('Answer:', 'Output:', 'Result:', 'Folder:', 'Name:', 'Folder name:'):
        if line.lower().startswith(prefix.lower()):
            line = line[len(prefix):].strip()

    line = line.strip('"\'`*')

    cleaned = re.sub(r'[^a-zA-Z0-9_ ]', '', line).strip()
    cleaned = re.sub(r'[\s_]+', '_', cleaned)

    if len(cleaned) > 50:
        parts = cleaned.split('_')
        cleaned = '_'.join(parts[:3])

    cleaned = cleaned[:50].strip('_')

    return cleaned if len(cleaned) > 2 else ""

def decode_mime_words(s):
    if not s: return ""
    try:
        decoded_words = decode_header(s)
        result = []
        for word, encoding in decoded_words:
            if isinstance(word, bytes):
                result.append(word.decode(encoding or 'utf-8'))
            else:
                result.append(word)
        return "".join(result)
    except:
        return str(s)

def get_email_body(msg):
    """Extracts plain text body from email"""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(errors='ignore')
    else:
        return msg.get_payload(decode=True).decode(errors='ignore')
    return ""

def main():
    print("📊 Status: Scanning Gmail with AI Logic...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER.strip(), GMAIL_PASS.replace(" ", "").strip())
        mail.select("inbox")
        _, data = mail.search(None, 'UNSEEN')
    except Exception as e:
        print(f"❌ Login Error: {e}")
        return

    for num in data[0].split():
        _, msg_data = mail.fetch(num, '(RFC822 X-GM-LABELS)')
        raw_metadata = msg_data[0][0].decode()
        
        # 1. Layer 1: Client from Gmail Label
        found_labels = re.findall(r'"([^"]*)"', raw_metadata)
        system_labels = ['Inbox', 'Unread', 'Important', 'Starred', 'Sent']
        client_folder = next((l for l in found_labels if l not in system_labels), "Unclassified")

        # 2. Layer 2: Project/Company via AI
        msg = email.message_from_bytes(msg_data[0][1])
        subject = decode_mime_words(msg['Subject'])
        body = get_email_body(msg)

        print(f"📧 Subject: {subject}")
        print(f"📧 Body: {body}")
        # Find first attachment name to help AI
        first_file = ""
        attachments = []
        for part in msg.walk():
            if part.get('Content-Disposition'):
                fn = decode_mime_words(part.get_filename())
                if fn: 
                    attachments.append(fn)
                    if not first_file: first_file = fn

        project_folder = ask_ai_for_project_advanced(subject, body, first_file)
        print(f"📂 Routing: {client_folder} -> {project_folder}")

        # 3. Save Files
        target_dir = os.path.join(SAVE_ROOT, client_folder, project_folder)
        os.makedirs(target_dir, exist_ok=True)

        for part in msg.walk():
            if part.get_content_maintype() == 'multipart' or part.get('Content-Disposition') is None:
                continue
            filename = decode_mime_words(part.get_filename())
            if filename:
                filepath = os.path.join(target_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(part.get_payload(decode=True))
                print(f"✅ Saved: {filename}")

    mail.logout()
    print("✨ Finished.")

if __name__ == "__main__":
    main()