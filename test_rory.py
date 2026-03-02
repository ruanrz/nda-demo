# -*- coding: utf-8 -*-
import imaplib
import email
import os
import re
import logging
from pathlib import Path
from email.header import decode_header

from providers.llm_client import get_llm_client, LLMCallError

logger = logging.getLogger(__name__)

# ================= 配置区 =================
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")
SAVE_ROOT = Path(os.environ.get("NDA_SAVE_ROOT", Path.home() / "NDA_Review"))
# =========================================


def ask_ai_for_project_advanced(subject: str, body: str, filename: str) -> str:
    """
    Use LLMClient to extract a short English folder name from email metadata.
    Priority: project name > target company > 'General_Archive'.
    """
    prompt = (
        "Analyze this legal email and extract a 2-word English folder name.\n\n"
        f"Subject: {subject}\n"
        f"Body snippet: {body[:300]}\n"
        f"Attachment name: {filename}\n\n"
        "Instructions:\n"
        "1. Look for a project name (e.g., 'Crown', 'Skyline').\n"
        "2. If no project name, look for a Target Company name (e.g., 'Tesla_Inc').\n"
        "3. Output ONLY the name in English with underscores. No explanation."
    )
    try:
        llm = get_llm_client()
        raw = llm.call(
            task_type="parsing",
            system_prompt="You are a legal document classifier. Reply with only the folder name.",
            user_prompt=prompt,
            json_mode=False,
            max_tokens=64,
        )
        project = re.sub(r"[^a-zA-Z0-9_]", "", raw.strip().replace(" ", "_"))
        return project if len(project) > 2 else "General_Archive"
    except (LLMCallError, Exception) as e:
        logger.warning("AI classification failed, falling back to General_Archive: %s", e)
        return "General_Archive"


def decode_mime_words(s: str) -> str:
    if not s:
        return ""
    try:
        decoded_words = decode_header(s)
        result = []
        for word, enc in decoded_words:
            if isinstance(word, bytes):
                result.append(word.decode(enc or "utf-8"))
            else:
                result.append(word)
        return "".join(result)
    except Exception as e:
        logger.debug("MIME decode failed: %s", e)
        return str(s)


def get_email_body(msg: email.message.Message) -> str:
    """Extracts plain text body from email."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="ignore")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(errors="ignore")
    return ""


def main():
    if not GMAIL_USER or not GMAIL_PASS:
        print("❌ 请设置环境变量 GMAIL_USER 和 GMAIL_APP_PASSWORD")
        print("   export GMAIL_USER='your@gmail.com'")
        print("   export GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx'")
        return

    print(f"📊 Scanning Gmail for {GMAIL_USER} ...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER.strip(), GMAIL_PASS.strip())
        mail.select("inbox")
        _, data = mail.search(None, "UNSEEN")
    except Exception as e:
        print(f"❌ Login / IMAP Error: {e}")
        return

    email_ids = data[0].split()
    if not email_ids:
        print("📭 No unread emails found.")
        mail.logout()
        return

    print(f"📬 Found {len(email_ids)} unread email(s).")

    for num in email_ids:
        try:
            _, msg_data = mail.fetch(num, "(RFC822 X-GM-LABELS)")
            if not msg_data or not msg_data[0] or not isinstance(msg_data[0], tuple):
                logger.warning("Skipping email %s: unexpected IMAP response", num)
                continue

            raw_metadata = msg_data[0][0]
            if isinstance(raw_metadata, bytes):
                raw_metadata = raw_metadata.decode(errors="ignore")

            # Layer 1: Client from Gmail Label
            found_labels = re.findall(r'"([^"]*)"', raw_metadata)
            system_labels = {"\\Inbox", "\\Unread", "\\Important", "\\Starred", "\\Sent",
                             "Inbox", "Unread", "Important", "Starred", "Sent"}
            client_folder = next((l for l in found_labels if l not in system_labels), "Unclassified")

            # Layer 2: Project/Company via AI
            msg = email.message_from_bytes(msg_data[0][1])
            subject = decode_mime_words(msg["Subject"])
            body = get_email_body(msg)

            first_file = ""
            for part in msg.walk():
                if part.get("Content-Disposition"):
                    fn = decode_mime_words(part.get_filename())
                    if fn:
                        first_file = fn
                        break

            project_folder = ask_ai_for_project_advanced(subject, body, first_file)
            print(f"📂 Routing: {client_folder} -> {project_folder}")

            # Layer 3: Save attachments
            target_dir = SAVE_ROOT / client_folder / project_folder
            target_dir.mkdir(parents=True, exist_ok=True)

            saved = 0
            for part in msg.walk():
                if part.get_content_maintype() == "multipart" or not part.get("Content-Disposition"):
                    continue
                filename = decode_mime_words(part.get_filename())
                if filename:
                    filepath = target_dir / filename
                    filepath.write_bytes(part.get_payload(decode=True))
                    print(f"  ✅ Saved: {filename}")
                    saved += 1

            if saved == 0:
                print("  ⚠️  No attachments found in this email.")

        except Exception as e:
            logger.error("Failed to process email %s: %s", num, e)
            print(f"  ❌ Error processing email {num}: {e}")

    mail.logout()
    print("✨ Finished.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
