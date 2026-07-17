#!/usr/bin/env python3
"""
Daedalus Digest — Daily Research Briefing Engine
https://github.com/YOUR_USERNAME/daedalus-digest

Don't edit this file. Edit config.py instead.
"""

import os
import smtplib
import json
import time
import random
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import anthropic

from config import (
    ANTHROPIC_API_KEY, GMAIL_ADDRESS, GMAIL_APP_PASSWORD,
    TO_EMAIL, DIGEST_NAME, YOUR_NAME, PAPERS_PER_DAY, TOPICS
)

SEEN_FILE = "seen_papers.json"


# ── MEMORY ────────────────────────────────────────────────────────────────────

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen_set):
    trimmed = list(seen_set)[-500:]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f)


# ── FETCHING ──────────────────────────────────────────────────────────────────

def fetch_pubmed(query, max_results=10):
    results = []
    try:
        params = urllib.parse.urlencode({
            "db": "pubmed", "term": query, "retmax": max_results,
            "sort": "date", "retmode": "json", "datetype": "pdat", "reldate": 30
        })
        with urllib.request.urlopen(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}", timeout=10
        ) as r:
            ids = json.loads(r.read()).get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        params2 = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "xml"})
        with urllib.request.urlopen(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{params2}", timeout=10
        ) as r:
            root = ET.fromstring(r.read())

        for article in root.findall(".//PubmedArticle"):
            try:
                title    = article.findtext(".//ArticleTitle", "").strip()
                abstract = article.findtext(".//AbstractText", "No abstract.").strip()[:800]
                pmid     = article.findtext(".//PMID", "")
                authors  = [
                    f"{a.findtext('LastName', '')} {a.findtext('ForeName', '')}".strip()
                    for a in article.findall(".//Author")[:3]
                ]
                author_str = ", ".join(authors) + (" et al." if len(article.findall(".//Author")) > 3 else "")
                results.append({
                    "title": title, "abstract": abstract, "authors": author_str,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "source": "PubMed"
                })
            except Exception:
                continue
        time.sleep(0.4)
    except Exception as e:
        print(f"  PubMed error: {e}")
    return results


def fetch_arxiv(query, category=None, max_results=10):
    results = []
    try:
        search_q = f"cat:{category}* AND {query}" if category else query
        params = urllib.parse.urlencode({
            "search_query": search_q, "start": 0, "max_results": max_results,
            "sortBy": "submittedDate", "sortOrder": "descending"
        })
        with urllib.request.urlopen(
            f"https://export.arxiv.org/api/query?{params}", timeout=10
        ) as r:
            root = ET.fromstring(r.read())

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title   = (entry.findtext("atom:title",   "", ns) or "").replace("\n", " ").strip()
            summary = (entry.findtext("atom:summary", "", ns) or "").replace("\n", " ").strip()[:800]
            link    = (entry.findtext("atom:id",      "", ns) or "").strip()
            authors = [a.findtext("atom:name", "", ns) for a in entry.findall("atom:author", ns)]
            author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
            results.append({
                "title": title, "abstract": summary, "authors": author_str,
                "url": link, "source": "arXiv"
            })
    except Exception as e:
        print(f"  arXiv error: {e}")
    return results


# ── SUMMARIZATION ─────────────────────────────────────────────────────────────

def summarize_paper(topic_label, topic_emoji, paper, client):
    prompt = f"""You are writing one section of {DIGEST_NAME} — a daily research briefing for a curious, intelligent reader named {YOUR_NAME}.

Topic: {topic_emoji} {topic_label}
Paper: {paper['title']}
Authors: {paper['authors']}
Abstract: {paper['abstract']}
URL: {paper['url']}

Write a magazine-style briefing. Rules:
- First line: one punchy sentence on why this matters RIGHT NOW
- 2-3 paragraphs in plain vivid language — no jargon walls, explain concepts like you're talking to a brilliant curious person, not a specialist
- Surface the most surprising or counterintuitive detail
- End with one "So what?" sentence — the open question or real-world implication
- Tone: Nature News meets The Atlantic. Smart, direct, alive.
- NO bullet points. Flowing paragraphs only.
- Last line: Read more → [paper title shortened to 6 words max](url)

Return ONLY the briefing text, nothing else."""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"  Claude error: {e}")
        return None


# ── EMAIL BUILDING ────────────────────────────────────────────────────────────

def build_banner(label, emoji, accent):
    """Pure CSS banner — works in every email client, no external dependencies."""
    return f"""
    <div style="background:linear-gradient(135deg,#0f1420 0%,#1a2235 100%);
                border-left:4px solid {accent};
                padding:24px 32px;
                border-radius:8px;
                margin-bottom:28px;">
      <span style="font-size:32px;">{emoji}</span>
      <span style="font-family:'Courier New',monospace;
                   font-size:12px;
                   letter-spacing:4px;
                   color:{accent};
                   text-transform:uppercase;
                   margin-left:16px;
                   vertical-align:middle;">{label}</span>
    </div>"""


def build_html(sections, date_str, client):
    # Generate a short punchy intro
    try:
        intro_msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=80,
            messages=[{"role": "user", "content": f"Write ONE sentence (max 20 words) as a punchy morning greeting for a daily research digest called {DIGEST_NAME}. Today's topics: {', '.join(s['label'] for s in sections)}. Be clever and specific, not generic. No quotes."}]
        )
        intro = intro_msg.content[0].text.strip()
    except Exception:
        intro = "Your fields moved overnight. Here's what matters."

    accents = ["#7fffb2", "#66d9ff", "#ffb347", "#ff6b9d", "#c084fc", "#fbbf24"]
    section_html = ""

    for i, sec in enumerate(sections):
        accent  = accents[i % len(accents)]
        banner  = build_banner(sec["label"], sec["emoji"], accent)

        content = sec["content"]
        content = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            r'<a href="\2" style="color:' + accent + r';text-decoration:none;border-bottom:1px solid ' + accent + r';">\1</a>',
            content
        )
        content = content.replace("\n\n", "</p><p style='margin:0 0 18px 0;'>")
        content = content.replace("\n", "<br>")
        content = f"<p style='margin:0 0 18px 0;'>{content}</p>"

        section_html += f"""
    <div style="padding:48px 0; border-bottom:1px solid #1a2235;">
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:0 52px;">

        {banner}

        <div style="font-family:Georgia,'Times New Roman',serif; font-size:24px; font-weight:normal; color:#f0ede5; line-height:1.3; margin-bottom:12px;">
          {sec['paper_title']}
        </div>

        <div style="font-family:'Courier New',monospace; font-size:11px; color:#4b5563; margin-bottom:28px; letter-spacing:0.5px;">
          {sec['authors']} &nbsp;·&nbsp; <span style="color:{accent};">{sec['source_label']}</span>
        </div>

        <div style="font-family:Georgia,'Times New Roman',serif; font-size:17px; line-height:1.9; color:#c8c4bc; max-width:680px;">
          {content}
        </div>

      </td></tr></table>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{DIGEST_NAME} — {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#080c14;font-family:Georgia,serif;">
<div style="max-width:780px;margin:0 auto;background:#080c14;">

  <!-- MASTHEAD -->
  <div style="padding:64px 52px 52px; border-bottom:1px solid #1a2235;">
    <div style="font-family:'Courier New',monospace;font-size:10px;letter-spacing:6px;color:#2d3748;text-transform:uppercase;margin-bottom:20px;">
      Daily Intelligence Briefing
    </div>
    <div style="font-family:Georgia,'Times New Roman',serif;font-size:64px;font-weight:normal;color:#f0ede5;line-height:0.95;letter-spacing:-2px;margin-bottom:8px;">
      {DIGEST_NAME.split()[0]}<br><em style="color:#7fffb2;">{DIGEST_NAME.split()[1] if len(DIGEST_NAME.split()) > 1 else ""}</em>
    </div>
    <div style="margin-top:28px;display:flex;align-items:center;gap:16px;">
      <div style="height:1px;flex:1;background:#1a2235;"></div>
      <div style="font-family:'Courier New',monospace;font-size:11px;color:#4b5563;letter-spacing:3px;white-space:nowrap;">
        {date_str.upper()}
      </div>
      <div style="height:1px;flex:1;background:#1a2235;"></div>
    </div>
  </div>

  <!-- INTRO STRIP -->
  <div style="background:#7fffb2;padding:20px 52px;">
    <div style="font-family:'Courier New',monospace;font-size:12px;color:#080c14;letter-spacing:0.5px;line-height:1.6;">
      {intro}
    </div>
  </div>

  <!-- META -->
  <div style="padding:18px 52px;border-bottom:1px solid #1a2235;">
    <span style="font-family:'Courier New',monospace;font-size:10px;color:#2d3748;letter-spacing:2px;">
      {len(sections)} PAPERS TODAY &nbsp;·&nbsp; PHYSICS · CHEMISTRY · BIOLOGY · CS · MATH · ENGINEERING · MEDICINE
    </span>
  </div>

  <!-- SECTIONS -->
  {section_html}

  <!-- FOOTER -->
  <div style="padding:48px 52px;text-align:center;border-top:1px solid #1a2235;">
    <div style="font-family:Georgia,serif;font-size:28px;color:#1e2535;font-style:italic;margin-bottom:12px;">DD</div>
    <div style="font-family:'Courier New',monospace;font-size:9px;letter-spacing:4px;color:#1f2937;text-transform:uppercase;">
      {DIGEST_NAME} &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; github.com/BonahJell/daedalus-digest
    </div>
  </div>

</div>
</body>
</html>"""


# ── EMAIL SENDING ─────────────────────────────────────────────────────────────

def send_email(html, date_str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{DIGEST_NAME} — {date_str}"
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        s.sendmail(GMAIL_ADDRESS, TO_EMAIL, msg.as_string())
    print(f"  ✓ Sent to {TO_EMAIL}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'═'*52}")
    print(f"  {DIGEST_NAME} — {datetime.now().strftime('%B %d, %Y')}")
    print(f"{'═'*52}\n")

    if not ANTHROPIC_API_KEY:
        print("❌ Set ANTHROPIC_API_KEY environment variable"); return
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("❌ Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables"); return

    client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    sections = []
    date_str = datetime.now().strftime("%B %d, %Y")
    seen     = load_seen()
    print(f"Memory: {len(seen)} papers already sent\n")

    # Shuffle topics with a daily seed so rotation is consistent but varied
    shuffled = TOPICS[:]
    random.seed(datetime.now().timetuple().tm_yday)
    random.shuffle(shuffled)

    for topic in shuffled:
        if len(sections) >= PAPERS_PER_DAY:
            break

        print(f"Fetching: {topic['emoji']} {topic['label']}")
        papers = (
            fetch_pubmed(topic["query"], max_results=10)
            if topic["source"] == "pubmed"
            else fetch_arxiv(topic["query"], topic.get("category"), max_results=10)
        )
        if not papers:
            print("  No papers found"); continue

        # Pick the first paper we haven't sent before
        new_paper = None
        for p in papers:
            key = p["title"].strip().lower()[:80]
            if key not in seen:
                new_paper = p
                seen.add(key)
                break

        if not new_paper:
            print("  All papers already seen, skipping"); continue

        print(f"  → {new_paper['title'][:65]}...")
        summary = summarize_paper(topic["label"], topic["emoji"], new_paper, client)

        if summary:
            sections.append({
                "label":        topic["label"],
                "emoji":        topic["emoji"],
                "paper_title":  new_paper["title"],
                "authors":      new_paper["authors"],
                "source_label": new_paper["source"],
                "content":      summary,
            })
            print("  ✓ Done")
        time.sleep(0.5)

    if not sections:
        print("❌ No new content found."); return

    save_seen(seen)

    print(f"\nBuilding email ({len(sections)} sections)...")
    html = build_html(sections, date_str, client)

    preview_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"preview_{datetime.now().strftime('%Y%m%d')}.html"
    )
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Preview saved: {preview_path}")

    print("Sending...")
    send_email(html, date_str)
    print("\n✓ Done.\n")


if __name__ == "__main__":
    main()
