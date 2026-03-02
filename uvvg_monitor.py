#!/usr/bin/env python3
"""
UVVG Media Monitor – GitHub Actions version
Caută referințe despre UVVG în ultimele 3 zile și trimite digest pe email.
"""

import os
import json
import datetime
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

# ─── CONFIGURARE ─────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
EMAIL_FROM        = os.environ.get("EMAIL_FROM", "")
EMAIL_TO          = os.environ.get("EMAIL_TO", "")
EMAIL_PASSWORD    = os.environ.get("EMAIL_PASSWORD", "")

KEYWORDS = [
    "UVVG",
    "Universitatea de Vest Vasile Goldis Arad",
    "UVVG Arad",
]

OUTPUT_DIR = Path("digests")
OUTPUT_DIR.mkdir(exist_ok=True)

# ─── CĂUTARE VIA CLAUDE API ───────────────────────────────────
def search_via_claude() -> list[dict]:
    today      = datetime.date.today()
    date_limit = today - datetime.timedelta(days=3)

    prompt = f"""Caută pe internet referințe despre: {', '.join(KEYWORDS)}.

Surse de căutat: știri locale românești (aradon.ro, ziuaarad.ro, observatorulph.ro etc.), 
știri naționale (digi24.ro, g4media.ro, hotnews.ro, mediafax.ro, agerpres.ro etc.),
știri internaționale, și rețele sociale (Facebook, LinkedIn, Twitter/X).

Consideră DOAR conținut publicat între {date_limit.strftime('%Y-%m-%d')} și {today.strftime('%Y-%m-%d')}.

Returnează EXCLUSIV un array JSON valid (fără text, fără markdown, fără ```):
[
  {{
    "title": "titlul articolului",
    "url": "https://...",
    "date": "2025-03-01",
    "source": "sursa.ro",
    "summary": "Rezumat de 1-2 propoziții în română."
  }}
]

Dacă nu există rezultate returnează: []"""

    # Debug: verifică cheia (afișează doar primele/ultimele 4 caractere)
    key = ANTHROPIC_API_KEY
    print(f"[DEBUG] API Key length: {len(key)}")
    print(f"[DEBUG] API Key preview: {key[:8]}...{key[-4:]}")
    print(f"[DEBUG] Starts with 'sk-ant-': {key.startswith('sk-ant-')}")

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key.strip(),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()

    # Extrage textul final
    raw = ""
    for block in reversed(data.get("content", [])):
        if block.get("type") == "text":
            raw = block["text"].strip()
            break

    # Curăță eventualele backtick-uri markdown
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        items = json.loads(raw)
        return items if isinstance(items, list) else []
    except json.JSONDecodeError:
        print(f"[!] JSON invalid primit:\n{raw[:500]}")
        return []


# ─── CONSTRUIRE HTML ──────────────────────────────────────────
def build_html(items: list[dict], today: datetime.date) -> str:
    date_str = today.strftime("%d %B %Y")
    period_start = (today - datetime.timedelta(days=3)).strftime("%d %B %Y")

    if not items:
        body = "<p style='color:#666'>Nu au fost găsite rezultate în ultimele 3 zile.</p>"
    else:
        rows = ""
        for i, item in enumerate(items, 1):
            rows += f"""
            <tr style="background:{'#fff' if i%2==0 else '#f9f9f9'}">
              <td style="padding:10px;border:1px solid #e0e0e0;text-align:center;color:#888;width:30px">{i}</td>
              <td style="padding:10px;border:1px solid #e0e0e0">
                <a href="{item.get('url','#')}" style="color:#1a3c6b;font-weight:bold;font-size:15px;text-decoration:none">
                  {item.get('title','—')}
                </a><br/>
                <span style="color:#888;font-size:12px">
                  📰 {item.get('source','—')} &nbsp;|&nbsp; 📅 {item.get('date','—')}
                </span><br/>
                <span style="color:#444;font-size:13px;margin-top:4px;display:block">
                  {item.get('summary','')}
                </span>
              </td>
            </tr>"""
        body = f"""
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="background:#1a3c6b;color:white">
              <th style="padding:10px;width:30px">#</th>
              <th style="padding:10px;text-align:left">Articol / Postare</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/></head>
<body style="font-family:Arial,sans-serif;max-width:750px;margin:auto;padding:20px;color:#222">
  <div style="background:#1a3c6b;color:white;padding:20px;border-radius:8px 8px 0 0">
    <h2 style="margin:0">📰 UVVG Media Digest</h2>
    <p style="margin:4px 0 0;opacity:.8">{date_str}</p>
  </div>
  <div style="background:#f0f4fa;padding:12px 20px;border:1px solid #dde3f0">
    <span style="color:#555;font-size:13px">
      🔍 Cuvinte cheie: <em>UVVG, Universitatea de Vest Vasile Goldis Arad, UVVG Arad</em><br/>
      📅 Perioadă monitorizată: {period_start} – {date_str} &nbsp;|&nbsp;
      📌 Total rezultate: <strong>{len(items)}</strong>
    </span>
  </div>
  <div style="border:1px solid #dde3f0;border-top:none;padding:16px">
    {body}
  </div>
  <p style="color:#aaa;font-size:11px;text-align:center;margin-top:16px">
    Digest generat automat · UVVG Monitor via GitHub Actions
  </p>
</body></html>"""


# ─── CONSTRUIRE TEXT PLAIN ────────────────────────────────────
def build_plain(items: list[dict], today: datetime.date) -> str:
    date_str = today.strftime("%d %B %Y")
    lines = [f"UVVG Media Digest – {date_str}", f"Total rezultate: {len(items)}", "=" * 60]
    if not items:
        lines.append("Nu au fost găsite rezultate în ultimele 3 zile.")
    else:
        for i, item in enumerate(items, 1):
            lines += [
                f"\n{i}. {item.get('title','—')}",
                f"   Sursă : {item.get('source','—')}",
                f"   Data  : {item.get('date','—')}",
                f"   Link  : {item.get('url','#')}",
                f"   Rezumat: {item.get('summary','')}",
            ]
    return "\n".join(lines)


# ─── SALVARE LOCALĂ ───────────────────────────────────────────
def save(plain: str, html: str, today: datetime.date):
    ds = today.strftime("%Y-%m-%d")
    (OUTPUT_DIR / f"digest_{ds}.txt").write_text(plain, encoding="utf-8")
    (OUTPUT_DIR / f"digest_{ds}.html").write_text(html, encoding="utf-8")
    print(f"[✓] Salvat: digests/digest_{ds}.*")


# ─── TRIMITERE EMAIL ──────────────────────────────────────────
def send_email(plain: str, html: str, today: datetime.date):
    if not all([EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD]):
        print("[!] Email neconfigurat – omis.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📰 UVVG Media Digest – {today.strftime('%d %B %Y')}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))

    with smtplib.SMTP("smtp.office365.com", 587) as s:
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login(EMAIL_FROM, EMAIL_PASSWORD)
        s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print(f"[✓] Email trimis → {EMAIL_TO}")


# ─── MAIN ─────────────────────────────────────────────────────
def main():
    today = datetime.date.today()
    print(f"[→] UVVG Monitor pornit – {today}")

    items = search_via_claude()
    print(f"[→] Rezultate găsite: {len(items)}")

    html  = build_html(items, today)
    plain = build_plain(items, today)

    save(plain, html, today)
    send_email(plain, html, today)
    print("[✓] Gata!")


if __name__ == "__main__":
    main()
