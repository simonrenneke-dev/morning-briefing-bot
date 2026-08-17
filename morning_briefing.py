"""Täglicher Morning-Briefing-Bot: Wetter + RSS-News -> Claude-Zusammenfassung -> Obsidian."""

import logging
import os
from datetime import date

import feedparser
import requests
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("morning_briefing")

FEEDS = {
    "Politik (FAZ)": "https://www.faz.net/rss/aktuell/politik/",
    "Allgemein (Spiegel)": "https://www.spiegel.de/schlagzeilen/index.rss",
    "Wirtschaft (Handelsblatt)": "https://www.handelsblatt.com/contentexport/feed/schlagzeilen",
    "Tech & KI (The Verge)": "https://www.theverge.com/rss/index.xml",
    "Tech & KI (Heise)": "https://www.heise.de/rss/heise-atom.xml",
}
ARTICLES_PER_FEED = 5
CLAUDE_MODEL = "claude-haiku-4-5"


WMO_CODES = {
    0: "Klarer Himmel", 1: "Überwiegend klar", 2: "Teilweise bewölkt", 3: "Bedeckt",
    45: "Neblig", 48: "Neblig (Reifnebel)",
    51: "Leichter Nieselregen", 53: "Mäßiger Nieselregen", 55: "Starker Nieselregen",
    61: "Leichter Regen", 63: "Mäßiger Regen", 65: "Starker Regen",
    71: "Leichter Schneefall", 73: "Mäßiger Schneefall", 75: "Starker Schneefall",
    80: "Leichte Regenschauer", 81: "Mäßige Regenschauer", 82: "Starke Regenschauer",
    95: "Gewitter", 96: "Gewitter mit Hagel", 99: "Gewitter mit schwerem Hagel",
}


def fetch_weather():
    logger.info("Lade Wetter für Paderborn (Open-Meteo)")
    try:
        # Koordinaten Paderborn
        url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=51.7189&longitude=8.7575"
            "&current=temperature_2m,apparent_temperature,weather_code"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
            "precipitation_probability_max,weather_code"
            "&timezone=Europe%2FBerlin&forecast_days=1"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        current = data["current"]
        daily = data["daily"]

        temp = current["temperature_2m"]
        feels = current["apparent_temperature"]
        max_t = daily["temperature_2m_max"][0]
        min_t = daily["temperature_2m_min"][0]
        precip_sum = daily["precipitation_sum"][0]
        precip_prob = daily["precipitation_probability_max"][0]
        desc = WMO_CODES.get(daily["weather_code"][0], "Unbekannt")

        logger.info("Wetter geladen")
        return (
            f"{desc}, aktuell {temp}°C (gefühlt {feels}°C), "
            f"Tagesbereich {min_t}–{max_t}°C, "
            f"Regen: {precip_prob}% Wahrscheinlichkeit / {precip_sum} mm erwartet"
        )
    except Exception as exc:
        logger.warning("Wetter nicht abrufbar: %s", exc)
        return None


def fetch_feed(name, url):
    logger.info("Lade Feed: %s", name)
    try:
        parsed = feedparser.parse(url)
        # feedparser wirft keine Exceptions, sondern setzt bozo bei Parse-Problemen.
        if parsed.bozo and not parsed.entries:
            raise RuntimeError(parsed.get("bozo_exception", "unbekannter Feed-Fehler"))
        articles = []
        for entry in parsed.entries[:ARTICLES_PER_FEED]:
            title = entry.get("title", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            if len(summary) > 200:
                summary = summary[:200].rsplit(" ", 1)[0] + "…"
            articles.append({"title": title, "summary": summary})
        logger.info("  %d Artikel von %s", len(articles), name)
        return articles
    except Exception as exc:
        logger.warning("  Feed %s nicht erreichbar: %s", name, exc)
        return []


def collect_news():
    news = {}
    for name, url in FEEDS.items():
        articles = fetch_feed(name, url)
        if articles:
            news[name] = articles
    return news


def build_news_text(news):
    lines = []
    for source, articles in news.items():
        lines.append(f"Quelle: {source}")
        for article in articles:
            lines.append(f"- {article['title']}")
            if article["summary"]:
                lines.append(f"  {article['summary']}")
        lines.append("")
    return "\n".join(lines).strip()


def summarize(news_text, weather):
    logger.info("Erstelle Zusammenfassung mit %s", CLAUDE_MODEL)
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    weather_section = (
        f"Wetterdaten für Paderborn heute: {weather}\n\n" if weather
        else "Wetterdaten heute nicht verfügbar.\n\n"
    )

    prompt = f"""Du erstellst ein persönliches Morning-Briefing für Simon.

{weather_section}Hier sind die heutigen News aus verschiedenen Quellen:

{news_text}

Erstelle daraus ein Morning-Briefing mit genau diesen Abschnitten in dieser Reihenfolge:

## Wetter
Kurze, lockere Zusammenfassung des Wetters für Paderborn heute. Was muss Simon wissen (Jacke? Regenschirm?)?

## Politik
Die wichtigsten politischen Ereignisse aus Deutschland, EU und Welt. Kurze, prägnante Sätze.

## Wirtschaft & Finanzen
Wichtige wirtschaftliche Ereignisse und Marktbewegungen. Nur was wirklich relevant ist.

## Tech & KI
Neuigkeiten aus Tech und KI – was ist neu, was ist wichtig zu wissen.

## Sport
Nur ein kurzer Satz zu bemerkenswerten Sportereignissen – kein Fußball, nur andere Sportarten falls relevant. Falls nichts Erwähnenswertes, diesen Abschnitt weglassen.

## Zitat des Tages
Ein inspirierendes oder interessantes Zitat (mit Quelle).

## Self-Improvement Tipp
Ein konkreter, umsetzbarer Tipp für den heutigen Tag – etwas das Simon direkt anwenden kann.

Schreib locker und freundlich, wie ein guter Freund der die News erklärt. Kein Fachchinesisch. Lesezeit: 3–5 Minuten. Auf Deutsch (außer englische Eigennamen/Zitate)."""

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1100,
        messages=[{"role": "user", "content": prompt}],
    )
    result = "".join(block.text for block in message.content if block.type == "text")
    logger.info("Zusammenfassung fertig (%d Zeichen)", len(result))
    return result.strip()


def save_to_obsidian(body):
    vault = os.environ["OBSIDIAN_VAULT_PATH"]
    today = date.today().strftime("%Y-%m-%d")
    folder = os.path.join(vault, "50 - News Briefing")
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, f"{today}.md")
    content = f"# Morning Briefing {today}\n\n{body}"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("Briefing gespeichert: %s", filepath)


def main():
    logger.info("Starte Morning-Briefing")

    weather = fetch_weather()
    news = collect_news()

    if not news:
        logger.error("Keine News geladen – breche ab.")
        raise SystemExit(1)

    news_text = build_news_text(news)

    try:
        briefing = summarize(news_text, weather)
    except Exception as exc:
        logger.error("Zusammenfassung fehlgeschlagen: %s", exc)
        raise SystemExit(1)

    try:
        save_to_obsidian(briefing)
    except Exception as exc:
        logger.error("Obsidian-Speicherung fehlgeschlagen: %s", exc)
        raise SystemExit(1)

    logger.info("Morning-Briefing erfolgreich abgeschlossen")


if __name__ == "__main__":
    main()
