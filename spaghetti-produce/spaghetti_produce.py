#!/usr/bin/env python3
"""
spaghetti-produce: Extract story sections from SpaghettiStories posts
and rewrite them into TTS-friendly spoken-word scripts for Grok Imagine.

Each clip targets Grok Imagine video generation with voiceover.
Clip durations: 6s (brief), 10s (standard), or 20s (10s + 10s extend).

Voiceover pacing: ~150 words/min = 2.5 words/sec (news anchor delivery)
  6s  → ~15 words  (1-2 short sentences)
  10s → ~25 words  (2-3 sentences)
  20s → ~50 words  (4-6 sentences)

Usage:
    python3 spaghetti_produce.py latest
    python3 spaghetti_produce.py <post-file.md>
    python3 spaghetti-produce.py latest --max-clips 3
"""

import re
import sys
import os
import glob
import json
import argparse
from pathlib import Path
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────
WPS = 2.5  # words per second (news anchor pace, ~150 wpm)

CLIP_PRESETS = {
    'brief':   {'seconds': 6,  'words': 15,  'label': '6s (brief)'},
    'standard': {'seconds': 10, 'words': 25,  'label': '10s (standard)'},
    'extended': {'seconds': 20, 'words': 50,  'label': '20s (10s+extend)'},
}

# ── Parsing ─────────────────────────────────────────────────────────────

def parse_frontmatter(raw: str) -> dict:
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', raw, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        kv = re.match(r'^(\w[\w-]*):\s*(.*)', line)
        if kv:
            key = kv.group(1)
            val = kv.group(2).strip()
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            if val.startswith('[') and val.endswith(']'):
                inner = val[1:-1]
                val = [v.strip().strip('"').strip("'") for v in inner.split(',') if v.strip()]
            fm[key] = val
    return fm


def extract_sections(raw: str) -> list[dict]:
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', raw, flags=re.DOTALL)
    body = re.sub(r'\{%\s*include\s+[^%]+\s*%\}', '', body)
    parts = re.split(r'\n(?=## )', body)
    sections = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.splitlines()
        heading = ''
        content_lines = []
        for line in lines:
            if line.startswith('## '):
                heading = line[3:].strip()
            else:
                content_lines.append(line)
        content = '\n'.join(content_lines).strip()
        if heading and content:
            sections.append({'heading': heading, 'content': content})
    return sections


def clean_blog_markdown(text: str) -> str:
    """Strip blog-specific markdown for TTS rewriting."""
    # Remove image includes
    text = re.sub(r'\{%\s*include\s+[^%]+\s*%\}', '', text)
    # Links → just text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\][^\(]', r'\1', text)
    # Bold/italic markers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    # Blockquotes
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    # Horizontal rules
    text = re.sub(r'^-{3,}\s*$', '', text, flags=re.MULTILINE)
    # Parenthetical asides
    text = re.sub(r'\s*\([^)]+\)\s*', ' ', text)
    # URLs
    text = re.sub(r'https?://\S+', '', text)
    # Clean up
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def wc(text: str) -> int:
    return len(text.split())


def secs(text: str) -> float:
    return wc(text) / WPS


def sentences(text: str) -> list[str]:
    """Split text into sentences."""
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]


def take_sentences(text: str, max_words: int) -> str:
    """Take complete sentences up to max_words."""
    sents = sentences(text)
    result = []
    count = 0
    for s in sents:
        w = wc(s)
        if count + w > max_words and result:
            break
        result.append(s)
        count += w
    return ' '.join(result)


# ── Blog → TTS rewriting ────────────────────────────────────────────────

def rewrite_section_for_tts(heading: str, content: str) -> str:
    """
    Convert a blog section into broadcast-news voiceover script.
    Strips blog-isms, restructures for spoken delivery.
    """
    text = clean_blog_markdown(content)

    # Strip attribution lines (e.g. "Simon Willison's take: ...")
    text = re.sub(r"^[\w\s'\"-]+take:\s*", '', text, flags=re.MULTILINE)

    # Remove "He's right." / "They're probably right." dangling refs
    text = re.sub(r"^He's right\.\s*", '', text, flags=re.MULTILINE)
    text = re.sub(r"^She's right\.\s*", '', text, flags=re.MULTILINE)
    text = re.sub(r"^They're probably right\.\s*", '', text, flags=re.MULTILINE)

    # Convert blog bold-label patterns to spoken transitions
    replacements = [
        (r'\*\*The pitch:\*\*', 'Here\'s the pitch.'),
        (r'\*\*The problem:\*\*', 'The problem?'),
        (r'\*\*The solution:\*\*', 'Their solution?'),
        (r'\*\*The catch:\*\*', 'The catch.'),
        (r'\*\*The real story:\*\*', 'The real story?'),
        (r'\*\*The Pattern:\*\*', 'The Pattern.'),
        (r'\*\*The deeper issue\?\*\*', 'The deeper issue?'),
        (r'\*\*Why this matters:\*\*', 'Why this matters.'),
        (r'\*\*Why this matters for builders:\*\*', 'Why this matters for you.'),
        (r'\*\*The key design choice:\*\*', 'The key design choice?'),
        (r'\*\*The tradeoff\?\*\*', 'The tradeoff?'),
        (r'\*\*This wasn\'t a bug\.\*\*', 'This wasn\'t a bug.'),
        (r'\*\*This is the first.*?\.\*\*', lambda m: m.group(0).replace('**', '')),
    ]
    for pattern, replacement in replacements:
        if callable(replacement):
            text = re.sub(pattern, replacement, text)
        else:
            text = re.sub(pattern, replacement, text)

    # Remove image alt-text lines that leaked through
    text = re.sub(r'^\s*!--.*?--\s*$', '', text, flags=re.MULTILINE)

    # Clean up lines that are just bold labels without colons
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)

    # Remove remaining markdown heading markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Strip leading/trailing whitespace per line, remove empties
    lines = [l.strip() for l in text.splitlines()]
    text = '\n'.join(l for l in lines if l.strip())

    return text.strip()


# ── Clip Planning ──────────────────────────────────────────────────────

def plan_clips_for_section(heading: str, rewritten: str, preset_key: str = 'standard') -> list[dict]:
    """
    Break a rewritten section into clips based on word budget per clip.
    Returns list of clip dicts with script text.
    """
    preset = CLIP_PRESETS[preset_key]
    max_words = preset['words']
    total_words = wc(rewritten)

    # If it fits in one clip, great
    if total_words <= max_words * 1.3:  # 30% tolerance — we can stretch pacing
        return [{
            'clip_index': 1,
            'heading': heading,
            'script': rewritten,
            'word_count': total_words,
            'duration': preset['seconds'],
            'extend': preset_key == 'extended',
            'speaking_seconds': round(secs(rewritten), 1),
        }]

    # Split into multiple clips by sentences
    all_sents = sentences(rewritten)
    clips = []
    clip_idx = 0
    current_sents = []
    current_words = 0

    for sent in all_sents:
        sent_w = wc(sent)

        # If adding this sentence would overshoot and we have content, flush
        if current_words + sent_w > max_words * 1.4 and current_sents:
            clip_idx += 1
            script = ' '.join(current_sents)
            clips.append({
                'clip_index': clip_idx,
                'heading': f"{heading} (part {clip_idx})",
                'script': script,
                'word_count': current_words,
                'duration': preset['seconds'],
                'extend': preset_key == 'extended',
                'speaking_seconds': round(secs(script), 1),
            })
            # Carry over: if this sentence is big, start new clip with it
            current_sents = [sent]
            current_words = sent_w
        else:
            current_sents.append(sent)
            current_words += sent_w

    # Flush last clip
    if current_sents:
        clip_idx += 1
        script = ' '.join(current_sents)
        if script.strip():
            clips.append({
                'clip_index': clip_idx,
                'heading': f"{heading} (part {clip_idx})" if clip_idx > 1 else heading,
                'script': script,
                'word_count': current_words,
                'duration': preset['seconds'],
                'extend': preset_key == 'extended',
                'speaking_seconds': round(secs(script), 1),
            })

    return clips


# ── Main Pipeline ───────────────────────────────────────────────────────

def process_post(filepath: str, preset: str = 'standard', max_clips: int = None,
                 sections: list = None) -> dict:
    with open(filepath, 'r') as f:
        raw = f.read()

    fm = parse_frontmatter(raw)
    all_sections = extract_sections(raw)

    # Filter to specific sections if requested
    if sections:
        selected = []
        for s in sections:
            if isinstance(s, int):
                if 1 <= s <= len(all_sections):
                    selected.append(all_sections[s - 1])
            else:
                # Match by heading substring
                for sec in all_sections:
                    if s.lower() in sec['heading'].lower():
                        selected.append(sec)
                        break
        all_sections = selected

    preset_cfg = CLIP_PRESETS[preset]
    all_clips = []

    for sec in all_sections:
        rewritten = rewrite_section_for_tts(sec['heading'], sec['content'])
        if not rewritten or wc(rewritten) < 5:
            continue
        sec_clips = plan_clips_for_section(sec['heading'], rewritten, preset)
        all_clips.extend(sec_clips)

    # Apply max_clips limit
    if max_clips and len(all_clips) > max_clips:
        all_clips = all_clips[:max_clips]

    total_speech = sum(c['speaking_seconds'] for c in all_clips)
    total_video = sum(c['duration'] for c in all_clips)

    return {
        'source_file': os.path.basename(filepath),
        'title': fm.get('title', 'Untitled'),
        'date': str(fm.get('date', '')),
        'author': fm.get('author', ''),
        'tags': fm.get('tags', []),
        'excerpt': fm.get('excerpt', ''),
        'preset': preset_cfg['label'],
        'total_clips': len(all_clips),
        'total_video_seconds': total_video,
        'total_speech_seconds': round(total_speech, 1),
        'clips': all_clips,
    }


def find_latest_post(posts_dir: str) -> str:
    pattern = os.path.join(posts_dir, '*.md')
    files = glob.glob(pattern)
    if not files:
        sys.exit(f"No .md files found in {posts_dir}")
    files.sort(reverse=True)
    return files[0]


def format_output(data: dict, fmt: str = 'yaml') -> str:
    """Format output for clipboard/paste into Grok Imagine."""
    if fmt == 'txt':
        # Plain text: ready to paste into Grok Imagine
        lines = [
            f"# {data['title']}",
            f"Preset: {data['preset']}",
            f"Clips: {data['total_clips']} | Video: {data['total_video_seconds']}s | Speech: {data['total_speech_seconds']}s",
            "",
        ]
        for clip in data['clips']:
            extend_note = " [+ EXTEND]" if clip['extend'] else ""
            lines.extend([
                f"── Clip {clip['clip_index']} ({clip['duration']}s{extend_note}) ──",
                f"Words: {clip['word_count']} | Speaking time: {clip['speaking_seconds']}s",
                "",
                clip['script'],
                "",
            ])
        return '\n'.join(lines)
    else:
        # YAML
        try:
            import yaml
            return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        except ImportError:
            return json.dumps(data, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description='Spaghetti Stories → Grok Imagine script generator')
    parser.add_argument('input', help='Post file path, "latest", or _posts directory')
    parser.add_argument('--preset', '-p', choices=['brief', 'standard', 'extended'],
                        default='standard', help='Clip duration preset (default: standard)')
    parser.add_argument('--max-clips', '-m', type=int, help='Limit total number of clips')
    parser.add_argument('--sections', '-s', nargs='+', help='Section indices (1-based) or heading substrings')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--format', '-f', choices=['yaml', 'txt'], default='txt',
                        help='Output format (default: txt for pasting)')
    parser.add_argument('--posts-dir', default=os.path.expanduser('~/projects/SpaghettiStories/_posts'))
    args = parser.parse_args()

    if args.input == 'latest':
        filepath = find_latest_post(args.posts_dir)
    elif os.path.isdir(args.input):
        filepath = find_latest_post(args.input)
    else:
        filepath = args.input

    if not os.path.exists(filepath):
        sys.exit(f"File not found: {filepath}")

    # Parse section args
    sec_filter = None
    if args.sections:
        sec_filter = []
        for s in args.sections:
            try:
                sec_filter.append(int(s))
            except ValueError:
                sec_filter.append(s)

    print(f"Processing: {filepath}", file=sys.stderr)
    result = process_post(filepath, args.preset, args.max_clips, sec_filter)

    print(f"Title: {result['title']}", file=sys.stderr)
    print(f"Preset: {result['preset']}", file=sys.stderr)
    print(f"Clips: {result['total_clips']}", file=sys.stderr)
    print(f"Total video: {result['total_video_seconds']}s | Speech: {result['total_speech_seconds']}s\n", file=sys.stderr)

    output = format_output(result, args.format)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Written to: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()
