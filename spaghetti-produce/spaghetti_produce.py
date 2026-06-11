#!/usr/bin/env python3
"""
spaghetti-produce v4: LLM-enhanced pipeline using Gemma 3 27B via OpenRouter.

Pipeline:
  1. Parse blog post → extract sections
  2. LLM (Gemma 3 27B) selects the single best story
  3. LLM writes broadcast-ready voiceover scripts (10s clips, 25 words max)
  4. Output production-ready script file

Usage:
    python3 spaghetti_produce.py latest
    python3 spaghetti_produce.py latest -t 40
    python3 spaghetti_produce.py <file.md>
    python3 spaghetti_produce.py <file.md> --model google/gemma-3-27b-it:free
"""

import json, os, re, sys, time, urllib.request, argparse, glob

# ── Config ──────────────────────────────────────────────────────────────
WPS = 2.5  # words/sec for news anchor (~150 wpm)
CLIP_WORDS = 25  # hard max per 10s clip
CLIP_SECONDS = 10

DEFAULT_MODEL = 'google/gemma-3-27b-it:free'

# ── Parsing ─────────────────────────────────────────────────────────────

def parse_fm(raw):
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', raw, re.DOTALL)
    if not m: return {}
    fm = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith('#'): continue
        kv = re.match(r'^(\w[\w-]*):\s*(.*)', line)
        if kv:
            k, v = kv.group(1), kv.group(2).strip()
            for q in ['"', "'"]:
                if v.startswith(q) and v.endswith(q): v = v[1:-1]
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
        if not part: continue
        heading, content_lines = '', []
        for line in part.splitlines():
            if line.startswith('## '): heading = line[3:].strip()
            else: content_lines.append(line)
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
    return text.strip()


def wc(t): return len(t.split())


# ── OpenRouter API ─────────────────────────────────────────────────────

def get_api_key():
    kf = os.path.expanduser('~/.hermes/openrouter-key')
    if os.path.exists(kf):
        with open(kf) as f:
            key = f.read().strip()
        if key and len(key) > 20: return key
    key = os.environ.get('OPENROUTER_API_KEY', '')
    if key and len(key) > 20: return key
    print("ERROR: No API key. Saved to ~/.hermes/openrouter-key", file=sys.stderr)
    sys.exit(1)


def call_llm(model, system, prompt, api_key, retries=3):
    payload = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': prompt},
        ],
        'max_tokens': 1500,
        'temperature': 0.7,
    }).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                'https://openrouter.ai/api/v1/chat/completions',
                data=payload,
                headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())['choices'][0]['message']['content'], None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 30 * (attempt + 1)
                print(f"  Rate limited. Waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            return None, str(e)
        except Exception as e:
            return None, str(e)
    return None, "Max retries exceeded"


def parse_json(text):
    if not text: return None, "empty"
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m: text = m.group(1)
    else:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m: text = m.group(0)
    try: return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}\nRaw: {text[:200]}"


# ── LLM Prompts ────────────────────────────────────────────────────────

SELECTOR_SYS = f"""You are a news editor for "Spaghetti Stories Daily" — a short-form AI news video series. Pick the single best story for a 30-45 second video short.

Criteria:
- Clear narrative arc (setup → conflict/twist → implication)
- Surprising, controversial, or emotionally engaging
- Conversational broadcast voice works naturally
- Concrete details (names, numbers, quotes)
- Avoids lists, benchmarks, or technical specs that need diagrams

Respond with ONLY JSON:
{{"selected_section_index": <int>, "selected_heading": "<exact heading>", "reason": "<1-2 sentences>", "hook": "<1-sentence cold open for the video>"}}"""


SCRIPT_SYS = f"""You are a broadcast news writer for "Spaghetti Stories Daily". Write voiceover scripts for short AI news videos.

HARD RULES:
- Each clip is EXACTLY 10 seconds. {CLIP_WORDS} words MAX per clip. Never exceed {CLIP_WORDS}.
- Confident, conversational news-anchor voice. Active voice. No filler. Every sentence earns its place.
- Read it aloud — if it sounds weird spoken, rewrite it.
- First clip = attention hook. Last clip = forward-looking button.
- Each clip must be a complete standalone 10-second thought.
- Visual notes in [brackets] suggest newscaster expression/gesture.

Respond with ONLY JSON:
{{"clips": [{{"clip_number": <int>, "duration": {CLIP_SECONDS}, "heading": "<label>", "script": "<exact text, {CLIP_WORDS} words max>", "visual_note": "<expression/gesture>", "word_count": <int>}}], "total_clips": <int>, "total_video_seconds": <int>, "total_word_count": <int>}}"""


def format_sections(sections):
    parts = []
    for s in sections:
        c = clean(s['content'])
        # Trim to first ~100 words to keep prompt manageable
        words = c.split()
        if len(words) > 120:
            c = ' '.join(words[:120]) + '...'
        parts.append(f"Section {s['index']}: {s['heading']}\n{c}")
    return '\n\n'.join(parts)


# ── Pipeline ────────────────────────────────────────────────────────────

def run_pipeline(filepath, target_secs, model, api_key):
    with open(filepath) as f:
        raw = f.read()

    fm = parse_fm(raw)
    sections = extract_sections(raw)
    title = fm.get('title', 'Untitled')
    date = str(fm.get('date', ''))

    print(f"Post: {title}", file=sys.stderr)
    print(f"Sections: {len(sections)}", file=sys.stderr)

    # Step 1: Story Selection
    print(f"\n[1/2] Selecting best story (model: {model})...", file=sys.stderr)
    sel_prompt = f"Title: {title}\nDate: {date}\n\nSections:\n{format_sections(sections)}\n\nPick the best story for a ~{target_secs}s video. Respond ONLY with JSON."
    raw1, err1 = call_llm(model, SELECTOR_SYS, sel_prompt, api_key)
    if err1:
        print(f"  ERROR: {err1}", file=sys.stderr)
        return None

    sel, perr1 = parse_json(raw1)
    if perr1:
        print(f"  PARSE ERROR: {perr1}", file=sys.stderr)
        return None

    print(f"  → Section {sel['selected_section_index']}: {sel['selected_heading'][:60]}", file=sys.stderr)
    print(f"  → {sel['reason'][:100]}", file=sys.stderr)

    # Find selected section content
    sel_idx = sel['selected_section_index']
    story_text = ''
    for s in sections:
        if s['index'] == sel_idx:
            story_text = clean(s['content'])
            break
    if not story_text:
        story_text = sel['selected_heading']

    # Step 2: Script Writing
    n_clips = target_secs // CLIP_SECONDS
    scr_prompt = f"Write {n_clips} broadcast voiceover clips (each 10s, {CLIP_WORDS} words MAX) for:\n\n{sel['selected_heading']}\n\n{story_text}\n\n{n_clips} clips. Cold open hook first. Forward-looking button last. {CLIP_WORDS} words HARD MAX per clip. Each clip standalone. Respond ONLY with JSON."

    print(f"\n[2/2] Writing script ({n_clips} clips, ~{target_secs}s)...", file=sys.stderr)
    raw2, err2 = call_llm(model, SCRIPT_SYS, scr_prompt, api_key)
    if err2:
        print(f"  ERROR: {err2}", file=sys.stderr)
        return None

    scr, perr2 = parse_json(raw2)
    if perr2:
        print(f"  PARSE ERROR: {perr2}", file=sys.stderr)
        return None

    clips = scr.get('clips', [])
    over = sum(1 for c in clips if c.get('word_count', 0) > CLIP_WORDS)
    print(f"  → {len(clips)} clips, {scr.get('total_word_count', 0)} words, {over} over limit", file=sys.stderr)

    return {
        'title': title,
        'date': date,
        'selection': sel,
        'script': scr,
    }


def format_output(data):
    sel = data['selection']
    scr = data['script']
    clips = scr.get('clips', [])

    lines = [
        f"# {data['title']}",
        f"Date: {data['date']}",
        "",
        f"## Selected Story: {sel['selected_heading']}",
        f"Reason: {sel['reason']}",
        f"",
        f"Clips: {len(clips)} | Video: {scr.get('total_video_seconds', 0)}s | Words: {scr.get('total_word_count', 0)}",
        "",
        "═" * 60,
        "",
    ]

    for c in clips:
        lines += [
            f"── CLIP {c['clip_number']} │ {c['heading']} │ {c['duration']}s ──",
            f"Words: {c['word_count']} | Max: {CLIP_WORDS}",
            f"Visual: {c.get('visual_note', 'Newscaster at desk')}",
            "",
            c['script'],
            "",
        ]

    lines += [
        "═" * 60,
        "",
        "## Production Checklist",
        "",
    ]
    for c in clips:
        lines.append(f"- [ ] Clip {c['clip_number']}: {c['heading']} ({c['duration']}s, {c['word_count']}w)")
    lines += [
        "",
        "# After all clips:",
        "- [ ] Download each clip from Grok Imagine",
        f"- [ ] ffmpeg concat: `ffmpeg {' '.join('-i clip' + str(c['clip_number']) + '.mp4' for c in clips)} -filter_complex concat=n={len(clips)}:v=1:a=1 -movflags faststart output.mp4`",
        "- [ ] Add intro/outro card",
        "- [ ] Export 9:16 vertical (1080x1920)",
    ]
    return '\n'.join(lines)


# ── CLI ─────────────────────────────────────────────────────────────────

def find_latest(d):
    f = sorted(glob.glob(os.path.join(d, '*.md')), reverse=True)
    return f[0] if f else None


def main():
    p = argparse.ArgumentParser(description='Spaghetti Stories → Grok Imagine script generator')
    p.add_argument('input', help='Post file, "latest", or _posts directory')
    p.add_argument('-t', '--target', type=int, default=30, help='Target video seconds (default: 30)')
    p.add_argument('-m', '--model', default=DEFAULT_MODEL, help=f'OpenRouter model (default: {DEFAULT_MODEL})')
    p.add_argument('-o', '--output', help='Output file')
    p.add_argument('--posts-dir', default=os.path.expanduser('~/projects/SpaghettiStories/_posts'))
    args = p.parse_args()

    if args.input == 'latest':
        fp = find_latest(args.posts_dir)
    elif os.path.isdir(args.input):
        fp = find_latest(args.input)
    else:
        fp = args.input

    if not fp or not os.path.exists(fp):
        sys.exit(f"Not found: {fp or args.input}")

    api_key = get_api_key()
    result = run_pipeline(fp, args.target, args.model, api_key)
    if not result:
        sys.exit("Pipeline failed")

    output = format_output(result)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"\nWritten: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()
