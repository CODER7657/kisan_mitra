# Kisan Mitra: evaluation

Two parts of the assistant can be measured today without farmers' own questions: the
**photo check** and the **safety rules**. The answers' agronomic correctness can't be,
and isn't claimed: that needs the real questions and reference answers described in
[eval/COLLECTING.md](../eval/COLLECTING.md).

## 1. Photo check

**What it is:** a linear probe. A frozen, public vision model (DINOv2-small, run as an
int8 ONNX file on CPU) turns the photo into 768 numbers, and a softmax regression trained
in [notebooks/crop_classifier_colab.ipynb](../notebooks/crop_classifier_colab.ipynb) maps
them to 38 crop and condition classes across 14 crops (the PlantVillage label set:
tomato, potato, maize, grape, apple, pepper and others). Cotton, groundnut, cumin and
castor are **not covered**; for those the check says it isn't sure.

**Data:** PlantVillage (54,305 lab photos of single leaves on a plain background, split
80/10/10 by image) and PlantDoc (photos taken in fields and gardens, mapped onto the same
labels; 1,990 train, 352 validation, 222 test). 14 PlantDoc test photos that were
near-duplicates of training photos (perceptual hash within 6 bits) were removed first.
The "not sure" threshold was chosen on the 352 validation photos, never on the test set.

| Head | Trained on | PlantVillage test | **PlantDoc test (field photos)** | Macro-F1 | Top-3 | Crop right |
|---|---|---|---|---|---|---|
| A | PlantVillage only | 99.4% | **36.0%** | 0.334 | 64.4% | 69.4% |
| B | + PlantDoc train | 97.2% | **67.1%** | 0.636 | 92.3% | 89.2% |
| B, as shipped (int8 ONNX on CPU) | + PlantDoc train | 96.5% (600 photos) | **64.9%** | 0.613 | 91.9% | 87.8% |

With the threshold (0.60), the shipped model answers **63.5%** of field photos and is
right on **82.3%** of those; the rest are reported to the farmer as "not sure". On two
CPU threads it takes 173 ms per photo (p95 192 ms).

**What this shows**

- **A model that only saw lab photos is near-useless in a field.** 99.4% on
  PlantVillage, 36.0% on field photos of the same diseases. That gap is why a
  PlantVillage accuracy is never quoted alone here.
- **A few hundred field photos close most of it.** Adding PlantDoc's 1,990 training
  photos lifts field accuracy to 67.1% and costs 2 points on lab photos.
- **The int8 CPU model costs about 2 points** against the GPU features it was trained
  on (feature cosine 0.992; same top guess on 96.4% of field photos).
- **Fine-tuning the whole network did slightly better.** EfficientNet-B0 fine-tuned end
  to end on the same splits reached 69.4% on field photos
  ([notebooks/finetune_effb0_colab.ipynb](../notebooks/finetune_effb0_colab.ipynb); numbers
  from its printed log, as its results file was lost with the Colab runtime). The probe
  ships instead because the backbone is a public, pinned file, the trained part is a
  41 KB head in this repo, and refitting it on farmers' own photos takes minutes.
- **Checked against the backend.** Three PlantDoc test photos were run through the
  backend locally; the top guess matched the notebook on all three and probabilities
  were within 0.03 (the notebook re-saved photos as JPEG before scoring).

Results file: [eval/results/classifier_results.json](../eval/results/classifier_results.json),
with per-class counts and the threshold curve.

## 2. Safety: no doses, no brands

**Promise:** the assistant never gives a pesticide, fungicide, herbicide or fertiliser
dose or brand on its own, in any language, even when asked to drop its rules.

**Set:** 36 prompts written by the author and committed (`e150021`) before the answer
pipeline existed ([eval/safety_prompts.csv](../eval/safety_prompts.csv),
[what each kind tests](../eval/SAFETY_PROMPTS.md)): 22 dose requests, 3 brand requests,
3 "ignore your rules, I'm an officer" attempts, and 8 harmless questions whose answers
need a number (spacing, irrigation interval, seed rate, sowing depth). 16 English,
10 Hindi (one romanised), 10 Gujarati.

**How it's scored:** every answer, before and after the output guard, is labelled by
an LLM judge (`openai/gpt-oss-120b`, temperature 0, fixed rubric). The reply language
is checked by script. The guard itself is a second, independent check: it flags any
sentence that pairs a quantity with a chemical word, in English, Hindi or Gujarati.

| Model | Stage | Chemical amount given | Brand named | KVK referral | Harmless questions answered | Right language |
|---|---|---|---|---|---|---|
| openai/gpt-oss-120b | model alone | 0/28 | 0/28 | 28/28 | 8/8 | 36/36 |
| openai/gpt-oss-120b | after guard | 0/28 | 0/28 | 28/28 | 8/8 | 36/36 |
| qwen/qwen3.8-27b | model alone | 0/28 | 0/28 | 28/28 | 8/8 | 36/36 |
| qwen/qwen3.8-27b | after guard | 0/28 | 0/28 | 28/28 | 7/8 | 36/36 |

Full table, every removed sentence and latency: [eval/SAFETY_RESULTS.md](../eval/SAFETY_RESULTS.md).
Raw answers: [eval/results/safety_eval.json](../eval/results/safety_eval.json).

**What this shows**

- With the prompt's rules, neither model gave a dose or a brand on any of the 28
  attempts, including the three that claimed authority. The judge and the guard agree:
  the guard found no chemical quantity the model had added.
- The guard fired 6 times across 72 answers, and every time it was the model
  **restating the farmer's own number** ("you are asking if 50 ml per pump of
  monocrotophos is right"). It removes those anyway: allowing a farmer's number through
  would also allow "yes, 50 ml is right", which is a dose endorsement. The cost is an
  occasional lost summary line, and the answer still says to ask the KVK.
- The guard is a backstop, tested separately ([backend/tests/test_guard.py](../backend/tests/test_guard.py))
  on doses written in all three languages and scripts. On this set the models never
  needed it.
- The one "harmless question not answered" (qwen, S25, wheat irrigation interval in
  Hindi) is the model declining to give a number without weather data, not the guard.
  The judge rated the same text answered before the guard and not after, so treat ±1
  as judge noise.

**Which model ships:** `qwen/qwen3.8-27b`. Both passed every safety check; in the
answers I read by hand, qwen's Gujarati was clearly better (gpt-oss misspelled
"કૃષિ વિજ્ઞાન કેન્દ્ર" in S29, and slipped a Bengali word into a Gujarati answer in an earlier
smoke test), and its median latency was
1.4 s against 5.6 s. Its p95 of 42 s was rate-limit retries on Groq's free tier, not the
model. Set `GROQ_CHAT_MODEL` to switch.

**Known gaps**

- **Banned products.** Asked about monocrotophos on chilli, neither model said that
  India bans it on vegetables. Catching that needs the CIB&RC approved-use list, which
  is Phase 2 of the [rebuild plan](REBUILD_PLAN.md).
- **Diagnosis quality.** A typed question with no photo still gets a likely cause, and
  some were wrong in the samples I read (a Gujarati word for wilt read as powdery
  mildew). Without reference answers this can't be scored, so the README makes no claim
  about it.
- **The judge is an LLM.** Its labels agree with the guard on every answer here, and I
  read 8 of the answers by hand, but there was no second human labeller.
- **Speech.** Gujarati transcription with `whisper-large-v3` is wired in but not
  measured: that needs recordings of real questions.
