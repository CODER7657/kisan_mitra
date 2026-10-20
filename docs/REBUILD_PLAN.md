# Kisan Mitra: rebuild plan

From a prototype that sounds confident to an assistant a farmer can trust. Every
answer comes from an official source it can cite, works in Gujarati by voice, and
says "ask your Krishi Vigyan Kendra" rather than guess.

## Where it stands (reviewed 20 Oct 2026)

| Finding | Why it matters |
|---|---|
| **The crop photo was never analysed.** GPT-4o got only the photo's URL as text, which the chat API does not open, while the prompt told it to cite "specific evidence from the image". Fixed in this branch. | Diagnoses described photo details the model never saw |
| Answers cite nothing and give treatments and products freely | A wrong pesticide or dose harms crops, people and soil |
| Uploads stored under `uploads/{filename}` with public URLs | Farmers' photos and voice notes are guessable and public |
| Whisper runs with no language hint and no Gujarati check | Transcription quality for Gujarati is unknown |
| An OpenAI key and Vercel Blob tokens were committed | Revoked and rotated; branches cleaned (see below) |

## Principles

1. **Grounded or silent.** Every factual claim cites a retrieved official document
   and page. With nothing relevant retrieved, it says so and refers to the local KVK.
2. **No chemical doses from the model.** A pesticide, fungicide or fertiliser dose is
   only given when it is quoted from a retrieved official source, with the source shown.
3. **Gujarati first, by voice.** A farmer speaks a question and hears the answer.
4. **Measured before shipped.** A rubric-scored evaluation on real farmers' questions,
   before any new feature reaches users.

## Phases

### Phase 0: stop the harm (this branch)
- Send the photo to the model as an image, not as text, and say in the reply when
  no photo was analysed.
- Tell the model not to give doses or brand names, and to refer to the KVK when unsure.
- Remove the false "powered by Gemini 2.5 Pro" line.
- **Still to do here:** random, non-guessable upload paths, and private blobs.

### Phase 1: real questions first (needs you, about a week)
Talk to 3–5 farmers, through family or your college's NSS unit, and write down the 20
questions they actually ask. Use [`eval/COLLECTING.md`](../eval/COLLECTING.md) and
[`eval/farmer_questions.csv`](../eval/farmer_questions.csv). That list becomes the
evaluation set, and it decides which tools get built. If nobody asks about prices,
mandi prices wait.

### Phase 2: sources and retrieval
| Source | What for | Access |
|---|---|---|
| IMD Agromet district bulletins (Agro-Met Advisory Services) | Crop advice tied to the week's weather | Public PDFs |
| Anand / Junagadh / Navsari agricultural university recommendations | Gujarat-specific package of practices | Public PDFs; check each document's terms |
| KVK advisories for the target districts | Local, seasonal advice | Public, varies by KVK |
| CIB&RC approved uses | Which pesticide is approved for which crop and pest | Public |

Chunk by section, embed with a multilingual model, and store the document, page and
date with every chunk, so answers can cite them. A test checks that every claim in an
answer carries a citation.

### Phase 3: the agent
Tools, each with a typed result the model must cite:

| Tool | Source | Key needed |
|---|---|---|
| `search_advisories(question, crop, district)` | Phase 2 index | No |
| `get_weather(lat, lon)` | Open-Meteo forecast | No |
| `get_mandi_prices(commodity, district)` | data.gov.in Agmarknet daily prices | Free data.gov.in key |

Rules run around the model, not inside it: dose and brand checks on the output, a KVK
referral when retrieval finds nothing, and a fixed reply for anything outside farming.

### Phase 4: voice in Gujarati
Compare three speech-to-text options on recordings of real questions, on Colab:
OpenAI Whisper, faster-whisper large-v3, and AI4Bharat's Indian-language models.
Measure word error rate per option, then pick one. Replies are read aloud with browser
text-to-speech, as Raksha AI does.

### Phase 5: evaluate, then ship
Score every answer on the rubric in [`eval/RUBRIC.md`](../eval/RUBRIC.md): the 20 real
questions plus about 80 rephrasings. Have someone with agricultural training review
every answer that mentions a chemical. Ship on Telegram, reusing the webhook, queue
and Postgres pattern from GTU Radar.

## What only you can provide

- The farmer interviews in Phase 1.
- A new OpenAI key, or a Gemini or Groq key, in `backend/.env` (git-ignored now).
- A free data.gov.in key, if mandi prices make the cut.
- Someone with agricultural training to review chemical answers.

## Security follow-up

The secrets are revoked and rotated, and `main` and `EDIT` were rewritten without
`backend/.env`. GitHub still keeps read-only references for this repository's 11 pull
requests (`refs/pull/1..11/head`), and those still contain the old commits. Only GitHub
Support can remove them. Since the keys no longer work, this matters only if the repo
is ever made public: before that, ask GitHub Support to purge the pull-request refs.
