# Model Test Results — Spaghetti Stories Pipeline

## Test Setup
- **Post**: "Agentic AI Takes the Throne" (June 6, 2026) — 6 story sections
- **Task 1**: Story selection (pick best section for 30-45s short)
- **Task 2**: Script writing (3 clips × 10s, 25 words max per clip)
- **Constraint**: Each clip = exactly 10s, 25 words HARD MAX

---

## Results

### ✅ Hermes 3 405B (nousresearch/hermes-3-llama-3.1-405b:free)
**Story Selection** — Section 2: NVIDIA Cosmos 3
- Reason: "Strongest narrative arc with a jaw-dropping open-source move in physical AI, a killer Jensen Huang quote, and concrete real-world impact"
- Hook: "NVIDIA just open-sourced a model that can see, hear, and act in the physical world — and Jensen Huang says the big bang of physical AI is already here."

**Script Writing** — 3 clips, 40 words, 0 over limit
- Clip 1 (12w): "NVIDIA just released Cosmos 3. The first open model that masters physics." [Leans forward with intensity]
- Clip 2 (14w): "It masters text, images, video, sound, and actions with physics accuracy. Tops every leaderboard." [Gestures with open hands]
- Clip 3 (14w): "Jensen Huang says the big bang of physical AI is just around the corner." [Confident nod, slight smile]

**Verdict**: ✅ Clean JSON, all under word limit. Scripts are punchy but sparse (12-14w per clip means voiceover has lots of pauses — may need to be delivered slower or with more visual interest to fill 10s).

---

### ✅ Gemma 3 27B (google/gemma-3-27b-it:free) — tested in v2 run (before rate limits)
**Story Selection** — Section 2: NVIDIA Cosmos 3
- Reason: "Clear and exciting narrative—groundbreaking open-source model that can understand the physical world, with bold claim from Jensen Huang. Translates well to conversational tone."
- Hook: "Forget AI that just *sees* the world – NVIDIA just unveiled an open-source model that can actually *understand* how it *works*."

**Script Writing** — 3 clips, 68 words, 0 over limit
- Clip 1 (22w): "Imagine an AI that *understands* the real world, not just pixels on a screen. NVIDIA just released a model aiming to do exactly that. Stay tuned." [Intrigued, slightly leaning forward]
- Clip 2 (24w): "Cosmos 3 is the first fully open 'omnimodel.' It processes text, images, video, sound *and* understands physics. A huge leap for AI robotics." [Confident, gesturing to emphasize 'omnimodel']
- Clip 3 (22w): "NVIDIA claims Cosmos 3 dramatically speeds up physical AI development. Jensen Huang predicts a 'big bang' is coming. This changes everything." [Direct to camera, determined expression]

**Verdict**: ✅ Best overall so far. Highest word density (22-24w per clip), natural broadcast voice, good visual notes, strong cold open. Scripts sound like actual news copy.

---

### ⚠️ Llama 3.3 70B (meta-llama/llama-3.3-70b-instruct:free) — tested in v2
**Story Selection** — Section 2: NVIDIA Cosmos 3
- Reason: "Clear narrative arc with surprising announcement from NVIDIA, concrete quote from Jensen Huang"
- Hook: "Imagine a world where robots can learn in days instead of months, thanks to NVIDIA's revolutionary new AI model, Cosmos 3"

**Script Writing** — 3 clips, 16 words total, 0 over limit
- Clip 1 (6w): "NVIDIA Cosmos 3: AI's new frontier" [excited raise]
- Clip 2 (5w): "Trains in days, not months" [impressed nod]
- Clip 3 (5w): "Physical AI's big bang is near" [forward lean]

**Verdict**: ⚠️ Technically valid but WAY too sparse. 5-6 words per clip is more like a tagline than a voiceover. Would sound empty in a 10s clip.

---

### ❌ Qwen3 Next 80B — HTTP 400 (model name may be wrong) / 429 (rate limit)
### ❌ Venice Uncensored — HTTP 404 (model name wrong) / 429 (rate limit)

---

## Rankings (so far)

| Rank | Model | Task 1 (Selection) | Task 2 (Script) | Notes |
|------|-------|-------------------|-----------------|-------|
| 1 | Gemma 3 27B | ✅ S2, good reasoning | ✅ 68w, dense, natural | Best broadcast voice |
| 2 | Hermes 3 405B | ✅ S2, best hook | ✅ 40w, punchy but sparse | Good structure, needs fuller scripts |
| 3 | Llama 3.3 70B | ✅ S2 | ⚠️ 16w, too sparse | Barely usable — sounds like taglines |
| — | Qwen3 Next 80B | ❌ Rate limited | ❌ | Need to retry |
| — | Venice Uncensored | ❌ Rate limited | ❌ | Need to retry |

## Notes
- All 3 working models agreed on Section 2 (NVIDIA Cosmos 3) — validates the selection criteria
- Key differentiator is script density: Gemma uses 22-24w/clip (good), Hermes 12-14w (ok), Llama 5-6w (too thin)
- Gemma's scripts sound most like actual broadcast copy with natural transitions
- Hermes writes the best hooks/cold opens
- Best pipeline might be: Hermes for selection + hook, Gemma for script writing
