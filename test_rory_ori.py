import imaplib
import email
import os
import re
from email.header import decode_header


# ================= 配置区 =================
GMAIL_USER = 'chujun.yang@ontra.ai'
GMAIL_PASS = 'icgqnzuighupvrnx'  
SAVE_ROOT = r'D:\NDA Review'
# =========================================

def ask_ai_for_project_advanced(subject, body, filename):
    """
    Advanced AI extraction:
    Priority 1: Project name (NDA, Lease, etc.)
    Priority 2: Target Company name
    Default: 'General_Archive'
    """
    prompt = f"""
    Analyze this legal email and extract a 2-word English folder name.
    
    Subject: {subject}
    Body snippet: {body[:300]}
    Attachment name: {filename}
    
    Instructions:
    1. Look for a project name (e.g., 'Crown', 'Skyline').
    2. If no project name, look for a Target Company name (e.g., 'Tesla_Inc').
    3. Output ONLY the name in English with underscores. No explanation.
    """
    try:
        # import ollama
        response = ollama.chat(model='llama3.2', messages=[{'role': 'user', 'content': prompt}])
        project = response.message.content.strip()
        project = re.sub(r'[^a-zA-Z0-9_]', '', project.replace(" ", "_"))
        if len(project) > 50:
            project = project[:50]
        return project if len(project) > 2 else "General_Archive"
    except Exception as e:
        print(f"⚠️ AI classification failed: {e}")
        return "General_Archive"

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
        print("🔓 Gmail 登录成功！")
    except Exception as e:
        print(f"❌ Login Error: {e}")
        return

    # 搜索指定日期之后的所有邮件（格式: DD-Mon-YYYY，如 01-Jan-2026）
    SINCE_DATE = '01-Feb-2026'
    _, data = mail.search(None, 'SINCE', SINCE_DATE)
    email_ids = data[0].split()

    if not email_ids:
        print("📭 收件箱为空，没有邮件可处理。")
        mail.logout()
        return

    print(f"📬 找到 {len(email_ids)} 封邮件（{SINCE_DATE} 之后），开始处理...")

    for num in email_ids:
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
    print("✨ 所有邮件处理完毕。")

if __name__ == "__main__":
    main()