#!/usr/bin/env python3
"""Convert Discord RP thread JSON files into formatted Markdown."""

import json
import os
import re
import sys
from datetime import datetime

THREADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "threads")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rp")

# Map Discord usernames to character names, per campaign
CAMPAIGN_CHARACTER_MAP = {
    "The Celstate Saga": {
        "nemo3267": "Talys",
        "penny5746": "Calarel",
        "pyroshadow": "Aurelio",
        "b3nis": "Alden",
    },
    "The Spark Saga": {
        "nemo3267": "Caspian",
        "penny5746": "Auri",
        "pyroshadow": "Sol/Sunni",
        ".tsukikage.": "Vornakir",
        "zzenonn": "Redd",
        "electrochemistry": "Zasia",
        "stressey_depressey": "DM",
        "eclipse5359": "Appo",
    },
}


def extract_title(messages):
    """Extract thread title from [Closed]/[Open]/[Solo] markers or first message."""
    for msg in messages:
        match = re.match(
            r"\[(?:Closed|Open|Solo|Complete)\]\s*(.+)", msg["content"], re.IGNORECASE
        )
        if match:
            status = re.match(r"\[(\w+)\]", msg["content"]).group(1).capitalize()
            title = match.group(1).strip()
            return title, status, msg
    return None, None, None


def get_author_name(author, campaign=None):
    """Get display name for an author."""
    username = author.get("username", "").lower()
    display = author.get("global_name") or author.get("username", "Unknown")
    char_map = CAMPAIGN_CHARACTER_MAP.get(campaign, {}) if campaign else {}
    return char_map.get(username, display)


def format_timestamp(ts):
    """Format ISO timestamp to readable date."""
    dt = datetime.fromisoformat(ts.replace("+00:00", "+00:00"))
    return dt.strftime("%B %d, %Y")


def format_timestamp_short(ts):
    """Format ISO timestamp to short date+time."""
    dt = datetime.fromisoformat(ts.replace("+00:00", "+00:00"))
    return dt.strftime("%b %d, %Y &middot; %I:%M %p UTC")


def clean_content(content):
    """Clean Discord-specific formatting from content."""
    # Replace Discord user mentions <@ID> with placeholder
    content = re.sub(r"<@!?(\d+)>", lambda m: f"@user", content)
    # Replace Discord channel mentions <#ID>
    content = re.sub(r"<#(\d+)>", lambda m: f"#channel", content)
    # Replace Discord role mentions <@&ID>
    content = re.sub(r"<@&(\d+)>", lambda m: f"@role", content)
    # Replace custom emoji <:name:id> or <a:name:id>
    content = re.sub(r"<a?:(\w+):\d+>", r":\1:", content)
    return content


def is_title_message(msg):
    """Check if a message is just a title/status marker."""
    return bool(
        re.match(r"\[(?:Closed|Open|Solo|Complete)\]\s*\S+", msg["content"], re.IGNORECASE)
    ) and len(msg["content"]) < 200


def is_ooc_only(content):
    """Check if message is purely OOC."""
    stripped = re.sub(r"\(\(.*?\)\)", "", content, flags=re.DOTALL).strip()
    return len(stripped) == 0 and "((" in content


def format_content(content):
    """Format message content with proper markdown styling."""
    # Separate OOC notes from IC content
    parts = []
    last_end = 0

    for match in re.finditer(r"\(\((.*?)\)\)", content, flags=re.DOTALL):
        # Add IC content before this OOC block
        ic_text = content[last_end : match.start()].strip()
        if ic_text:
            parts.append(ic_text)
        # Add OOC as styled aside
        ooc_text = match.group(1).strip()
        parts.append(
            f'\n> *OOC: {ooc_text}*\n'
        )
        last_end = match.end()

    # Remaining IC content
    remaining = content[last_end:].strip()
    if remaining:
        parts.append(remaining)

    return "\n\n".join(parts)


def convert_thread(json_path, output_path=None, campaign=None):
    """Convert a single thread JSON file to markdown."""
    with open(json_path) as f:
        messages = json.load(f)

    if not messages:
        return None

    thread_id = os.path.basename(json_path).replace(".json", "")

    # Extract title
    title, status, title_msg = extract_title(messages)

    # If no explicit title, use first line of first message
    if not title:
        first_line = messages[0]["content"].split("\n")[0][:80]
        title = first_line.rstrip(".")
        if len(messages[0]["content"].split("\n")[0]) > 80:
            title += "..."
        status = "Unknown"

    # Gather authors (excluding title-only messages)
    authors = []
    seen = set()
    for msg in messages:
        name = get_author_name(msg["author"], campaign)
        if name not in seen:
            seen.add(name)
            authors.append(name)

    # Date range
    first_date = format_timestamp(messages[0]["timestamp"])
    last_date = format_timestamp(messages[-1]["timestamp"])
    date_range = first_date if first_date == last_date else f"{first_date} &ndash; {last_date}"

    # Build markdown
    lines = []

    # Jekyll front matter
    lines.append("---")
    lines.append(f"layout: default")
    lines.append(f"title: \"{title}\"")
    lines.append("---")
    lines.append("")

    # Header with styling
    lines.append(f'<div align="center">\n')
    lines.append(f"# {title}\n")

    status_colors = {
        "Closed": "#e74c3c",
        "Open": "#2ecc71",
        "Solo": "#9b59b6",
        "Complete": "#3498db",
        "Unknown": "#95a5a6",
    }
    color = status_colors.get(status, "#95a5a6")
    lines.append(
        f'<img src="https://img.shields.io/badge/status-{status}-{color[1:]}?style=for-the-badge" alt="{status}" />\n'
    )

    if campaign:
        lines.append(f"**Campaign:** {campaign}  ")
    lines.append(f"**Writers:** {' &bull; '.join(authors)}  ")
    lines.append(f"**Date:** {date_range}\n")
    lines.append(f"</div>\n")

    # Separator
    lines.append("---\n")

    # No style block needed — OOC uses blockquotes for Jekyll compatibility

    # Messages
    prev_author = None
    for msg in messages:
        # Skip title-only messages
        if is_title_message(msg):
            continue

        content = clean_content(msg["content"])
        if not content.strip():
            continue

        author = get_author_name(msg["author"], campaign)
        ts = format_timestamp_short(msg["timestamp"])

        # Author header — show when author changes
        if author != prev_author:
            lines.append(f"\n### &#x270D; {author}")
            lines.append(f'<sub>{ts}</sub>\n')
        else:
            lines.append(f'\n<sub>{ts}</sub>\n')

        # Message body
        formatted = format_content(content)
        lines.append(f"{formatted}\n")

        prev_author = author

    # Footer
    lines.append("\n---\n")
    lines.append(
        f'<div align="center"><sub>Thread ID: {thread_id} &bull; Fetched from Discord</sub></div>\n'
    )

    markdown = "\n".join(lines)

    # Write output
    if output_path is None:
        safe_title = re.sub(r"[^\w\s-]", "", title).strip()
        safe_title = re.sub(r"\s+", "-", safe_title).lower()
        if not safe_title:
            safe_title = thread_id
        output_path = os.path.join(OUTPUT_DIR, f"{safe_title}.md")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(markdown)

    return output_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Convert Discord RP thread JSON to Markdown")
    parser.add_argument("files", nargs="*", help="Specific JSON files to convert (default: all)")
    parser.add_argument("--campaign", "-c", help="Campaign name (e.g. 'The Celstate Saga')")
    args = parser.parse_args()

    if args.files:
        for path in args.files:
            result = convert_thread(path, campaign=args.campaign)
            if result:
                print(f"Converted: {result}")
    else:
        for f in sorted(os.listdir(THREADS_DIR)):
            if f.endswith(".json"):
                result = convert_thread(os.path.join(THREADS_DIR, f), campaign=args.campaign)
                if result:
                    print(f"Converted: {result}")


if __name__ == "__main__":
    main()
