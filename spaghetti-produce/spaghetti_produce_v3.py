#!/usr/bin/env python3
"""
spaghetti-produce v3: LLM-enhanced pipeline for Spaghetti Stories → Grok Imagine.

Pipeline:
  1. Parse blog post → extract sections
  2. LLM selects the single best story for a short video
  3. LLM writes broadcast-ready voiceover scripts (10s/20s clips)
  4. Output production-ready script file

Usage:
    python3 spaghetti_produce_v3.py latest
    python3 spaghetti_produce_v3.py latest --clips 3
    python3 spaghetti_produce_v3.py <file.md> --model google/gemini-2.0-flash-001
"""

import re, sys, os, glob, argparse, json, subprocess

# ── Config ──────────────────────────────────────────────────────────────
WPS = 2.5  # words/sec for news anchor

CLIP_BUDGET = {
    6:  15,
    10: 25,
    20: 50,
}

# Free/cheap OpenRouter models good for this task
MODELS = {
    'fast':    'google/gemini-2.0-flash-001',     # fast, cheap, good quality
    'quality': 'meta-llama/llama-4-maverick',      # free tier, strong writing
    'budget':  'deepseek/deepseek-chat-v3-0324',   # very cheap
}

DEFAULT_MODEL = 'fast'

# ── Parsing (same as v2) ────────────────────────────────────────────────

def parse_fm(raw):
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
            k, v = kv.group(1), kv.group(2).strip()
            for q in ['"', "'"]:
                if v.startswith(q) and v.endswith(q):
                    v = v[1:-1]
            if v.startswith('[') and v.endswith(']'):
                v = [x.strip().strip('"').strip("'") for x in v[1:-1].split(',') if x.strip()]
            fm[k] = v
    return fm


def extract_sections(raw):
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', raw, flags=re.DOTALL)
    body = re.sub(r'\{%\s*include\s+[^%]+\s*%\}', '', body)
    sections = []
    for part in re.split(r'\n(?=## )', body):
        part = part.strip()
        if not part:
            continue
        heading, content_lines = '', []
        for line in part.splitlines():
            if line.startswith('## '):
                heading = line[3:].strip()
            else:
                content_lines.append(line)
        content = '\n'.join(content_lines).strip()
        if heading and content:
            sections.append({'heading': heading, 'content': content, 'index': len(sections)+1})
    return sections


def clean(text):
    text = re.sub(r'\{%\s*include\s+[^%]+\s*%\}', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s*\([^)]+\)\s*', ' ', text)
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── LLM Prompts ────────────────────────────────────────────────────────

STORY_SELECTOR_SYSTEM = """You are a news editor for "Spaghetti Stories Daily" — a short-form AI news video series. Your job is to pick the single best story from a daily blog post to turn into a 30-60 second video short.

Criteria for a good video story:
- Has a clear narrative arc (setup → conflict/twist → implication)
- Contains a surprising, controversial, or emotionally engaging element
- Can be explained in 30-60 seconds of spoken word
- Has concrete details (names, numbers, quotes) that make it feel real
- Avoids overly technical deep-dives that need diagrams or code

You must respond with ONLY a JSON object:
{
  "selected_section_index": <1-based index of the chosen section>,
  "selected_heading": "<exact heading of the section>",
  "reason": "<1-2 sentences why this is the best video story>",
  "hook": "<a 1-sentence cold open that grabs attention — this becomes Clip 1>"
}"""

STORY_SELECTOR_USER = """Here is today's blog post. Each section is a separate story. Pick the best one for a short video.

Title: {title}
Date: {date}

{sections}

Remember: respond with ONLY the JSON object, no other text."""


SCRIPT_WRITER_SYSTEM = """You are a broadcast news writer for "Spaghetti Stories Daily" — a short-form AI news video series. You write voiceover scripts for 10-second and 20-second video clips.

Rules:
- Write in a confident, conversational news-anchor voice
- Each word costs time — be punchy and direct
- 10s clip = ~25 words max. 20s clip = ~50 words max.
- Write like you're talking TO the viewer, not reading a blog
- Use active voice. Cut filler words. Every sentence must earn its place.
- For 20s clips (which are 10s + 10s extension), the first 10s should work as a complete thought, and the extension adds depth
- Include visual direction notes in [brackets] where the newscaster's expression/gesture matters
- End each clip with a "button" — a line that feels complete and transitions well

You must respond with ONLY a JSON object:
{
  "clips": [
    {
      "clip_number": <int>,
      "duration": <6, 10, or 20>,
      "extend": <true if 20s>,
      "heading": "<short label for this clip>",
      "script": "<the exact voiceover text, broadcast-ready>",
      "visual_note": "<suggested expression/pose for the newscaster>",
      "word_count": <exact word count of script>
    }
  ],
  "total_clips": <int>,
  "total_video_seconds": <sum of durations>,
  "total_word_count": <sum of all clip word counts>
}"""

SCRIPT_WRITER_USER = """Write the voiceover scripts for a {target_duration}s video short about this story.

Story heading: {heading}

Full story text:
{story_text}

Requirements:
- Target total duration: ~{target_duration} seconds
- Use 10s clips (25 words) and 20s clips (50 words, with extension)
- First clip should hook the viewer immediately
- Last clip should wrap up with a forward-looking statement or call to action
- Total word count should be close to {target_words} words ({target_duration}s × 2.5 words/sec)

Respond with ONLY the JSON object."""


# ── LLM Call via Hermes CLI ─────────────────────────────────────────────

def call_llm_via_hermes(prompt, system, model):
    """
    Call LLM through Hermes agent CLI.
    Uses `hermes ask` or falls back to direct API call.
    """
    # Try using hermes CLI if available
    full_prompt = f"System: {system}\n\nUser: {prompt}"
    try:
        result = subprocess.run(
            ['hermes', 'ask', '--model', model, '--no-stream', full_prompt],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: use openrouter API directly
    return call_openrouter_api(prompt, system, model)


def call_openrouter_api(prompt, system, model):
    """Direct OpenRouter API call."""
    import urllib.request, json as _json

    # Try environment variable first, then hermes config
    api_key = os.environ.get('OPENROUTER_API_KEY', '')
    
    if not api_key:
        # Try to read from hermes config
        config_paths = [
            os.path.expanduser('~/.hermes/config.yaml'),
            os.path.expanduser('~/.hermes/config.json'),
        ]
        for cp in config_paths:
            if os.path.exists(cp):
                with open(cp) as f:
                    content = f.read()
                m = re.search(r'api_key["\s:]+([^\s"\']+)', content)
                if m and m.group(1) not in ('', "''", '""'):
                    api_key = m.group(1)
                    break
    
    # Fallback: check for a dedicated key file
    if not api_key:
        key_file = os.path.expanduser('~/.hermes/openrouter-key')
        if os.path.exists(key_file):
            with open(key_file) as f:
                api_key = f.read().strip()

    if not api_key:
        return None, "No OpenRouter API key found. Set OPENROUTER_API_KEY env var or create ~/.hermes/openrouter-key"

    payload = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': prompt},
        ],
        'max_tokens': 2000,
        'temperature': 0.7,
    }).encode()

    req = urllib.request.Request(
        'https://openrouter.ai/api/v1/chat/completions',
        data=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data['choices'][0]['message']['content'], None
    except Exception as e:
        return None, str(e)


def parse_llm_json(text):
    """Extract JSON from LLM response (handles markdown code fences)."""
    if not text:
        return None
    # Try to find JSON block
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        # Try to find bare JSON object
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            text = m.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ── Pipeline ────────────────────────────────────────────────────────────

def format_sections_for_llm(sections):
    """Format sections as text for LLM consumption."""
    parts = []
    for s in sections:
        cleaned = clean(s['content'])
        parts.append(f"--- Section {s['index']}: {s['heading']} ---\n{cleaned}")
    return '\n\n'.join(parts)


def run_story_selector(title, date, sections, model):
    """Use LLM to pick the best story."""
    sections_text = format_sections_for_llm(sections)
    prompt = STORY_SELECTOR_USER.format(
        title=title, date=date, sections=sections_text
    )
    raw, err = call_openrouter_api(prompt, STORY_SELECTOR_SYSTEM, model)
    if err:
        print(f"  Story selector error: {err}", file=sys.stderr)
        return None
    result = parse_llm_json(raw)
    if not result:
        print(f"  Story selector bad response: {raw[:200]}", file=sys.stderr)
        return None
    return result


def run_script_writer(heading, story_text, target_duration, model):
    """Use LLM to write broadcast scripts."""
    target_words = int(target_duration * WPS)
    prompt = SCRIPT_WRITER_USER.format(
        heading=heading,
        story_text=story_text,
        target_duration=target_duration,
        target_words=target_words,
    )
    raw, err = call_openrouter_api(prompt, SCRIPT_WRITER_SYSTEM, model)
    if err:
        print(f"  Script writer error: {err}", file=sys.stderr)
        return None
    result = parse_llm_json(raw)
    if not result:
        print(f"  Script writer bad response: {raw[:200]}", file=sys.stderr)
        return None
    return result


def format_final_output(title, date, selection, script_data):
    """Format the final production script."""
    lines = [
        f"# {title}",
        f"Date: {date}",
        "",
        f"## Selected Story: {selection['selected_heading']}",
        f"Reason: {selection['reason']}",
        "",
        f"Clips: {script_data['total_clips']} | Video: {script_data['total_video_seconds']}s | Words: {script_data['total_word_count']}",
        "",
        "═" * 60,
        "",
    ]

    for clip in script_data['clips']:
        ext = "  [+ EXTEND]" if clip.get('extend') else ""
        lines += [
            f"── CLIP {clip['clip_number']} │ {clip['heading']} │ {clip['duration']}s{ext} ──",
            f"Words: {clip['word_count']} | Speech: ~{clip['word_count']/WPS:.0f}s",
            f"Visual: {clip.get('visual_note', 'Newscaster at desk')}",
            "",
            clip['script'],
            "",
        ]

    lines += [
        "═" * 60,
        "",
        "## Production Checklist",
        "",
    ]
    for clip in script_data['clips']:
        ext = " → extend" if clip.get('extend') else ""
        lines.append(f"- [ ] Clip {clip['clip_number']}: {clip['heading']} ({clip['duration']}s{ext})")
    lines += [
        "",
        "# After all clips:",
        "- [ ] Download each clip from Grok Imagine",
        "- [ ] ffmpeg concat: ffmpeg -i clip1.mp4 -i clip2.mp4 -filter_complex concat=n={}:v=1:a=1".format(script_data['total_clips']),
        "- [ ] Add intro/outro card",
        "- [ ] Export 9:16 vertical (1080x1920)",
    ]
    return '\n'.join(lines)


# ── Main ────────────────────────────────────────────────────────────────

def find_latest(d):
    f = sorted(glob.glob(os.path.join(d, '*.md')), reverse=True)
    return f[0] if f else None


def main():
    p = argparse.ArgumentParser(description='Spaghetti Stories → Grok Imagine (LLM-enhanced)')
    p.add_argument('input', help='Post file, "latest", or _posts directory')
    p.add_argument('-t', '--target', type=int, default=30, help='Target video seconds (default: 30)')
    p.add_argument('-m', '--model', default=DEFAULT_MODEL,
                   choices=list(MODELS.keys()), help='Model tier (default: fast)')
    p.add_argument('--model-name', help='Override with exact OpenRouter model string')
    p.add_argument('-o', '--output', help='Output file')
    p.add_argument('--posts-dir', default=os.path.expanduser('~/projects/SpaghettiStories/_posts'))
    p.add_argument('--dry-run', action='store_true', help='Parse only, skip LLM calls')
    args = p.parse_args()

    # Resolve model
    model = args.model_name or MODELS[args.model]

    # Resolve input file
    if args.input == 'latest':
        fp = find_latest(args.posts_dir)
    elif os.path.isdir(args.input):
        fp = find_latest(args.input)
    else:
        fp = args.input

    if not fp or not os.path.exists(fp):
        sys.exit(f"Not found: {fp or args.input}")

    with open(fp) as f:
        raw = f.read()

    fm = parse_fm(raw)
    sections = extract_sections(raw)
    title = fm.get('title', 'Untitled')
    date = str(fm.get('date', ''))

    print(f"Post: {title}", file=sys.stderr)
    print(f"Sections: {len(sections)}", file=sys.stderr)
    for s in sections:
        print(f"  {s['index']}. {s['heading']} ({len(s['content'].split())} words)", file=sys.stderr)

    if args.dry_run:
        print("\nDry run — skipping LLM calls", file=sys.stderr)
        sys.exit(0)

    # Step 1: Select the best story
    print(f"\n[1/2] Selecting best story (model: {model})...", file=sys.stderr)
    selection = run_story_selector(title, date, sections, model)
    if not selection:
        sys.exit("Story selection failed")

    sel_idx = selection.get('selected_section_index', 1)
    sel_heading = selection.get('selected_heading', '')
    print(f"  → Selected: {sel_heading}", file=sys.stderr)
    print(f"  → Reason: {selection.get('reason', '')}", file=sys.stderr)
    print(f"  → Hook: {selection.get('hook', '')}", file=sys.stderr)

    # Find the selected section content
    story_text = ''
    for s in sections:
        if s['index'] == sel_idx or s['heading'] == sel_heading:
            story_text = clean(s['content'])
            break

    if not story_text:
        sys.exit(f"Could not find section: {sel_idx} / {sel_heading}")

    # Step 2: Write the scripts
    print(f"\n[2/2] Writing scripts for ~{args.target}s video...", file=sys.stderr)
    script_data = run_script_writer(sel_heading, story_text, args.target, model)
    if not script_data:
        sys.exit("Script writing failed")

    print(f"  → {script_data['total_clips']} clips, {script_data['total_video_seconds']}s, {script_data['total_word_count']} words", file=sys.stderr)

    # Format output
    output = format_final_output(title, date, selection, script_data)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"\nWritten: {args.output}", file=sys.stderr)
    else:
        print(f"\n{output}")

    print("\nDone.", file=sys.stderr)


if __name__ == '__main__':
    main()
