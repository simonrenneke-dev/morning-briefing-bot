# Morning Briefing Bot

A personal daily briefing generator that pulls weather data and news via RSS feeds, summarizes everything using Claude AI, and saves the result as a Markdown note directly into your Obsidian vault.

## Features

- **Weather** — current conditions and forecast for your city (via Open-Meteo, no API key needed)
- **Politics** — top stories from Germany, EU, and the world
- **Economy & Finance** — market movements and relevant business news
- **Tech & AI** — latest from the tech world
- **Sport** — notable non-football events (skipped if nothing relevant)
- **Quote of the day** — an inspiring or thought-provoking quote
- **Self-improvement tip** — one concrete, actionable tip for the day

Output is saved as `YYYY-MM-DD.md` in a dedicated Obsidian folder.

## Tech Stack

| Component | Tool |
|---|---|
| Language | Python 3.9+ |
| AI Summary | [Anthropic Claude](https://anthropic.com) (`claude-opus-4-8`) |
| Weather | [Open-Meteo API](https://open-meteo.com) |
| News | RSS feeds (Spiegel, Handelsblatt, The Verge, Heise) |
| Output | Obsidian Markdown |

## Setup

**1. Clone and install dependencies**

```bash
git clone https://github.com/simonrenneke-dev/morning-briefing-bot.git
cd morning-briefing-bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
```

Then fill in your values in `.env`.

**3. Run**

```bash
python morning_briefing.py
```

## Automation (optional)

To run every morning at 7:00 AM, add this to your crontab (`crontab -e`):

```
0 7 * * * cd /path/to/morning-briefing-bot && ./venv/bin/python morning_briefing.py
```

## Configuration

Edit the `FEEDS` dict in `morning_briefing.py` to add or remove news sources. Any RSS feed URL works.

## License

MIT
