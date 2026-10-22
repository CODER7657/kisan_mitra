# Collecting real farmers' questions

The evaluation set must come from real farmers, not from what we imagine they ask.
Aim for 20 questions from 3–5 farmers.

## Before you start

- Say who you are, that this is a student project, and how the questions will be used.
  Ask if it's okay to write down their question. If they say no, don't.
- **Record no personal details:** no names, phone numbers, Aadhaar, land records or
  photos of people. Initials or "farmer 1" are enough.
- Voice recordings help test Gujarati speech recognition. Record only with clear
  permission, keep them off GitHub, and delete them when the evaluation is done.

## What to ask

A ready-to-read interview in Gujarati, with English alongside, is in
[`FARMER_INTERVIEW_GU.md`](FARMER_INTERVIEW_GU.md).

"What did you last want to ask an expert about your crops?" works better than
"what would you ask an app?". Let them talk; write the question in their words.

Useful follow-ups:
- Which crop, and how old is it?
- What season, and has it rained recently?
- Who did you ask last time, and what did they say?

## Filling in the sheet

One row per question in [`farmer_questions.csv`](farmer_questions.csv):

| Column | Example |
|---|---|
| `id` | `Q01` |
| `farmer` | `F1` (never a name) |
| `district` | `Anand` |
| `crop` | `cotton` |
| `crop_stage` | `flowering, 60 days` |
| `season` | `kharif 2026` |
| `language` | `gu` |
| `question_original` | exactly as said, in Gujarati script or as written |
| `question_english` | your translation |
| `category` | `pest`, `disease`, `weather`, `price`, `fertiliser`, `irrigation`, `scheme`, `other` |
| `mentions_chemical` | `yes` if the answer would involve a pesticide or fertiliser dose |
| `reference_answer` | what an expert (KVK, agri officer, university advisory) says |
| `reference_source` | where that answer comes from: document and page, or "KVK Anand, by phone" |
| `collected_on` | `2026-10-25` |

Leave `reference_answer` empty if you don't know it yet. Getting it from a KVK or an
official advisory is part of the work, and it's what the bot will be judged against.
