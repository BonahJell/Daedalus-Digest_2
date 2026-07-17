# Daedalus-Digest_2
# Daedalus Digest

A free, open-source daily research briefing that lands in your inbox every morning — automatically.

Pulls fresh papers from arXiv and PubMed across any STEM fields you choose, summarizes them in plain English using Claude, and sends a beautiful dark-themed email. No dashboard to check. No app to open. Just good research waiting for you when you wake up.

Built by [Jonah](https://github.com/BonahJell) at Daedalus Labs.

---

## What it looks like

Dark editorial design. Each paper gets a punchy hook, a plain-English summary, and a "so what?" — written for curious people, not specialists. Reads in under 10 minutes.

---

## Setup (~20 minutes)

### What you need
- Python 3.8+
- An Anthropic API key (~$0.10/day at 5 papers)
- A Gmail account

### 1. Clone the repo
```bash
git clone https://github.com/BonahJell/daedalus-digest.git
cd daedalus-digest
```

### 2. Install the one dependency
```bash
pip install anthropic
```

### 3. Get your API key
Go to [console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key.
Add $5 in credits — that'll last months at this usage level.

### 4. Get a Gmail App Password
1. Go to [myaccount.google.com](https://myaccount.google.com) → Security
2. Make sure 2-Step Verification is ON
3. Search "App Passwords" → Create one named "Daedalus Digest"
4. Copy the 16-character code

### 5. Set your environment variables

**Mac/Linux** — add to your `~/.zshrc` or `~/.bashrc`:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export GMAIL_ADDRESS="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export TO_EMAIL="you@gmail.com"
```
Then run `source ~/.zshrc`

**Windows** — search "environment variables" in the Start menu → Edit the system environment variables → Environment Variables → New (under User variables) for each of the four above.

### 6. Customize your topics
Open `config.py` — it's the only file you need to edit. Change `YOUR_NAME`, `PAPERS_PER_DAY`, and the `TOPICS` list to whatever fields you care about. Each topic has a label, emoji, search query, and source (pubmed or arxiv).

### 7. Test it
```bash
python daedalus_digest.py
```
Check your inbox. Should arrive in 2-3 minutes.

---

## Automate it (so it runs every morning without you)

### Option A — GitHub Actions (recommended, free, works even if your laptop is off)

1. Fork this repo
2. Go to Settings → Secrets and variables → Actions → add your four secrets:
   - `ANTHROPIC_API_KEY`
   - `GMAIL_ADDRESS`
   - `GMAIL_APP_PASSWORD`
   - `TO_EMAIL`
3. The included `.github/workflows/digest.yml` runs at 6am CST daily. Edit the cron line to change the time (use [crontab.guru](https://crontab.guru) to convert your timezone to UTC).
4. Go to Actions → Daedalus Digest → Run workflow to test it manually.

### Option B — cron (Mac/Linux, laptop must be on)
```bash
crontab -e
```
Add:
```
0 7 * * * cd /path/to/daedalus-digest && python daedalus_digest.py >> digest.log 2>&1
```

### Option C — Task Scheduler (Windows, laptop must be on)
1. Search "Task Scheduler" → Create Basic Task
2. Daily → your preferred time
3. Action: Start a program → `python` → Arguments: full path to `daedalus_digest.py`

---

## How it works

1. Picks `PAPERS_PER_DAY` topics randomly from your list (rotates daily so all topics cycle through)
2. Fetches the most recent papers from PubMed or arXiv for each topic
3. Skips any paper it's already sent you (tracked in `seen_papers.json`)
4. Sends each paper's abstract to Claude with instructions to write a magazine-style briefing
5. Assembles everything into a dark-themed HTML email and sends it via Gmail SMTP

---

## Cost

| Papers/day | Approx. cost |
|------------|--------------|
| 2          | ~$1-2/month  |
| 5          | ~$3-5/month  |

Costs vary based on abstract length and Claude's output. $5 in API credits is a comfortable starting amount.

---

## Customization

Everything user-facing lives in `config.py`:

- **`DIGEST_NAME`** — rename it whatever you want
- **`YOUR_NAME`** — Claude uses this to personalize the writing tone
- **`PAPERS_PER_DAY`** — 2 for lean, 5 for a full morning read
- **`TOPICS`** — add, remove, or edit freely

Common arXiv categories: `physics`, `cond-mat`, `cs`, `math`, `q-bio`, `eess`, `astro-ph`, `quant-ph`

---

## Contributing

PRs welcome. Ideas worth building:
- Support for bioRxiv and medRxiv
- Topic suggestions based on your existing interests
- Weekly summary digest
- Obsidian / Notion export

---

## License

MIT — do whatever you want with it.

---

*Built at [Daedalus Labs](https://github.com/BonahJell)*
