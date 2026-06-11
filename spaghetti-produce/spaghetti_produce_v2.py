#!/usr/bin/env python3
"""
spaghetti-produce: Spaghetti Stories blog post → Grok Imagine production script.

Usage:
    python3 spaghetti_produce.py latest
    python3 spaghetti_produce.py latest -t 60
    python3 spaghetti_produce.py latest --clips 4
    python3 spaghetti_produce.py <file.md>
"""

import re, sys, os, glob, argparse

WPS = 2.5  # words/sec, news anchor pace

CLIP_Words = {6: 15, 10: 25, 20: 50}


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


def wc(t): return len(t.split())


def sents(t): return [p.strip() for p in re.split(r'(?<=[.!?])\s+', t) if p.strip()]


def take_words(text, max_w):
    result, count = [], 0
    for s in sents(text):
        w = wc(s)
        if count + w > max_w and result:
            break
        result.append(s)
        count += w
    return ' '.join(result), count


def score_section(heading, content):
    """Heuristic: how good is this section as a video clip?"""
    c = clean(content)
    score = 0
    score += len(re.findall(r'\*\*', content))  # emphasis
    score += len(re.findall(r'"[^"]+"', c)) * 2  # quotes = quotable
    score += len(re.findall(r'\d', c))  # numbers = concrete facts
    if '?' in c:
        score += 3  # questions are engaging
    # Penalize walls of text
    if wc(c) > 250:
        score -= 5
    # Bonus for punchy headlines
    if any(w in heading.lower() for w in ['secret', 'backfire', 'war', 'crisis', 'hack', 'exploit', 'break', 'first', 'new']):
        score += 4
    return score


def build_plan(title, sections, target_secs=30, max_clips=None):
    """Select best sections and plan clips to fill target duration."""
    # Score and rank sections
    ranked = sorted(sections, key=lambda s: score_section(s['heading'], s['content']), reverse=True)

    clips = []
    remaining = target_secs
    idx = 0

    for sec in ranked:
        if remaining <= 0:
            break
        if max_clips and len(clips) >= max_clips:
            break

        cleaned = clean(sec['content'])
        words = wc(cleaned)

        # Choose clip duration based on content volume
        if words >= 40 and remaining >= 20:
            dur = 20
        elif words >= 15 and remaining >= 10:
            dur = 10
        elif remaining >= 6:
            dur = 6
        else:
            continue

        budget = CLIP_Words[dur]
        script, script_wc = take_words(cleaned, budget)

        if script_wc < 5:
            continue

        idx += 1
        clips.append({
            'idx': idx,
            'heading': sec['heading'],
            'duration': dur,
            'extend': dur == 20,
            'words': script_wc,
            'speech_secs': round(script_wc / WPS, 1),
            'script': script,
            'image_toggle': idx > 1 and idx % 2 == 0,  # alternate image every other clip
        })
        remaining -= dur

    total_video = sum(c['duration'] for c in clips)
    return {
        'title': title,
        'target_secs': target_secs,
        'total_secs': total_video,
        'num_clips': len(clips),
        'clips': clips,
    }


def format_output(plan):
    lines = [
        f"# {plan['title']}",
        f"Target: ~{plan['target_secs']}s → Planned: {plan['total_secs']}s across {plan['num_clips']} clips",
        "",
        "═" * 60,
        "",
    ]

    for c in plan['clips']:
        ext = "  [+ EXTEND to 20s]" if c['extend'] else ""
        toggle = "  🖼 SWITCH base image" if c['image_toggle'] else ""
        lines += [
            f"── CLIP {c['idx']} │ {c['heading']} │ {c['duration']}s{ext}{toggle} ──",
            f"Words: {c['words']} │ Speech time: ~{c['speech_secs']}s",
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
    for c in plan['clips']:
        ext = " → extend" if c['extend'] else ""
        lines.append(f"- [ ] Clip {c['idx']}: {c['heading']} ({c['duration']}s{ext})")
    lines += [
        "",
        "# After all clips done:",
        "- [ ] Download each clip",
        "- [ ] ffmpeg concat in order",
        "- [ ] Add intro/outro card",
        "- [ ] Review and export 9:16 vertical",
    ]
    return '\n'.join(lines)


def find_latest(d):
    f = sorted(glob.glob(os.path.join(d, '*.md')), reverse=True)
    return f[0] if f else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('input')
    p.add_argument('-t', '--target', type=int, default=30)
    p.add_argument('-c', '--clips', type=int)
    p.add_argument('-o', '--output')
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

    with open(fp) as f:
        raw = f.read()

    fm = parse_fm(raw)
    sections = extract_sections(raw)
    title = fm.get('title', 'Untitled')

    plan = build_plan(title, sections, args.target, args.clips)
    out = format_output(plan)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(out)
        print(f"Written: {args.output}", file=sys.stderr)
    else:
        print(out)

    print(f"\n{plan['num_clips']} clips, {plan['total_secs']}s total", file=sys.stderr)


if __name__ == '__main__':
    main()
