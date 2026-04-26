#!/usr/bin/env python3
"""Convert Discord RP thread JSON files into HTML with chat-bubble layout."""

import json
import os
import re
import sys
from datetime import datetime
from html import escape

THREADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "threads")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rp")

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
    username = author.get("username", "").lower()
    display = author.get("global_name") or author.get("username", "Unknown")
    char_map = CAMPAIGN_CHARACTER_MAP.get(campaign, {}) if campaign else {}
    return char_map.get(username, display)


def format_timestamp(ts):
    dt = datetime.fromisoformat(ts)
    return dt.strftime("%B %d, %Y")


def format_timestamp_short(ts):
    dt = datetime.fromisoformat(ts)
    return dt.strftime("%b %d, %Y · %I:%M %p UTC")


def clean_content(content):
    content = re.sub(r"<@!?(\d+)>", "@user", content)
    content = re.sub(r"<#(\d+)>", "#channel", content)
    content = re.sub(r"<@&(\d+)>", "@role", content)
    content = re.sub(r"<a?:(\w+):\d+>", r":\1:", content)
    return content


def is_title_message(msg):
    return bool(
        re.match(r"\[(?:Closed|Open|Solo|Complete)\]\s*\S+", msg["content"], re.IGNORECASE)
    ) and len(msg["content"]) < 200


def content_to_html(content):
    """Convert Discord markdown content to HTML paragraphs with OOC handling."""
    blocks = []
    last_end = 0

    for match in re.finditer(r"\(\((.*?)\)\)", content, flags=re.DOTALL):
        ic_text = content[last_end:match.start()].strip()
        if ic_text:
            blocks.append(("ic", ic_text))
        ooc_text = match.group(1).strip()
        blocks.append(("ooc", ooc_text))
        last_end = match.end()

    remaining = content[last_end:].strip()
    if remaining:
        blocks.append(("ic", remaining))

    html_parts = []
    for block_type, text in blocks:
        if block_type == "ooc":
            escaped = text_to_paragraphs(text)
            html_parts.append(
                f'<div class="msg-bubble ooc">'
                f'<span class="ooc-label">OOC</span> {escaped}</div>'
            )
        else:
            escaped = text_to_paragraphs(text)
            html_parts.append(escaped)

    return html_parts


def text_to_paragraphs(text):
    """Convert text with newlines into HTML paragraphs, preserving Discord markdown."""
    paragraphs = re.split(r"\n{2,}", text)
    html = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        p = escape(p)
        # Discord blockquotes
        lines = p.split("\n")
        processed = []
        in_quote = False
        quote_lines = []
        for line in lines:
            if line.startswith("&gt; "):
                if not in_quote:
                    in_quote = True
                quote_lines.append(line[5:])
            else:
                if in_quote:
                    processed.append(f'<blockquote>{"<br>".join(quote_lines)}</blockquote>')
                    quote_lines = []
                    in_quote = False
                processed.append(line)
        if in_quote:
            processed.append(f'<blockquote>{"<br>".join(quote_lines)}</blockquote>')

        p = "<br>".join(processed) if not any("<blockquote>" in l for l in processed) else "".join(
            f"<p>{l}</p>" if not l.startswith("<blockquote>") else l for l in processed
        )

        # Bold
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        # Italic (single * or _)
        p = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", p)
        p = re.sub(r"__(.+?)__", r"<strong>\1</strong>", p)
        p = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<em>\1</em>", p)
        # Markdown headings inside messages
        p = re.sub(r"^### (.+?)(<br>|$)", r"<strong>\1</strong>\2", p)
        p = re.sub(r"^## (.+?)(<br>|$)", r"<strong>\1</strong>\2", p)

        html.append(f"<p>{p}</p>")

    return "\n".join(html)


def convert_thread(json_path, output_path=None, campaign=None):
    with open(json_path) as f:
        messages = json.load(f)

    if not messages:
        return None

    thread_id = os.path.basename(json_path).replace(".json", "")

    title, status, title_msg = extract_title(messages)

    if not title:
        first_line = messages[0]["content"].split("\n")[0][:80]
        title = first_line.rstrip(".")
        if len(messages[0]["content"].split("\n")[0]) > 80:
            title += "..."
        status = "Unknown"

    # Gather unique authors in order and assign colors
    authors = []
    seen = set()
    author_color = {}
    color_idx = 0
    for msg in messages:
        name = get_author_name(msg["author"], campaign)
        if name not in seen:
            seen.add(name)
            authors.append(name)
            author_color[name] = color_idx
            color_idx = (color_idx + 1) % 8

    first_date = format_timestamp(messages[0]["timestamp"])
    last_date = format_timestamp(messages[-1]["timestamp"])
    date_range = first_date if first_date == last_date else f"{first_date} – {last_date}"

    # Build HTML
    h = []
    h.append("---")
    h.append("layout: default")
    h.append(f'title: "{escape(title)}"')
    h.append("---")
    h.append("")
    h.append(f'<a href="{{{{ site.baseurl }}}}/" class="back-link">← Back to Index</a>')
    h.append("")
    h.append('<div class="thread-header">')
    h.append(f"  <h1>{escape(title)}</h1>")
    h.append(f'  <div class="meta">')
    if campaign:
        h.append(f"    <span>{escape(campaign)}</span> ·")
    author_tags = ' '.join(f'<span class="char-tag">{escape(a)}</span>' for a in authors)
    h.append(f"    {author_tags}<br>")
    h.append(f"    <span>{date_range}</span>")
    h.append(f"  </div>")
    h.append(f"</div>")
    h.append("")
    h.append('<div class="chat">')

    prev_author = None
    for msg in messages:
        if is_title_message(msg):
            continue

        content = clean_content(msg["content"])
        if not content.strip():
            continue

        author = get_author_name(msg["author"], campaign)
        ts = format_timestamp_short(msg["timestamp"])
        cidx = author_color.get(author, 0)

        show_author = author != prev_author

        if show_author:
            if prev_author is not None:
                h.append("</div>")  # close prev msg-group
            h.append(f'<div class="msg-group color-{cidx}">')
            h.append(f'  <div class="msg-author">{escape(author)}</div>')

        html_blocks = content_to_html(content)

        # OOC-only blocks are already wrapped; IC blocks go in a bubble
        ic_parts = []
        for block in html_blocks:
            if block.startswith('<div class="msg-bubble ooc">'):
                # Flush IC parts first
                if ic_parts:
                    h.append(f'  <div class="msg-bubble">')
                    h.append("    " + "\n    ".join(ic_parts))
                    h.append(f'    <div class="timestamp">{ts}</div>')
                    h.append(f"  </div>")
                    ic_parts = []
                h.append(f"  {block}")
            else:
                ic_parts.append(block)

        if ic_parts:
            h.append(f'  <div class="msg-bubble">')
            h.append("    " + "\n    ".join(ic_parts))
            h.append(f'    <div class="timestamp">{ts}</div>')
            h.append(f"  </div>")

        prev_author = author

    if prev_author is not None:
        h.append("</div>")  # close last msg-group

    h.append("</div>")  # close chat
    h.append("")
    h.append(f'<div class="thread-footer">Thread ID: {thread_id}</div>')

    html_content = "\n".join(h)

    if output_path is None:
        safe_title = re.sub(r"[^\w\s-]", "", title).strip()
        safe_title = re.sub(r"\s+", "-", safe_title).lower()
        if not safe_title:
            safe_title = thread_id
        output_path = os.path.join(OUTPUT_DIR, f"{safe_title}.html")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html_content)

    return output_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Convert Discord RP thread JSON to HTML")
    parser.add_argument("files", nargs="*", help="Specific JSON files to convert (default: all)")
    parser.add_argument("--campaign", "-c", help="Campaign name")
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
