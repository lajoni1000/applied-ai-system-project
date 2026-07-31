# 🎧 Model Card: Applied AI Music Recommender

## 1. Model / System Name

**Applied AI Music Recommender**

This project extends the Project 3 Music Recommender Simulation by adding input validation, LLM-generated explanations, grounding, guardrails, and deterministic fallback behavior. The recommendation engine is deterministic; a Google Gemini model is added as an *explanation layer* only, wrapped in validation, grounding, guardrails, and a deterministic fallback.

---

## 2. Intended Use

Applied AI Music Recommender recommends songs from a small music catalog based on a user's stated preferences (favorite genre, favorite mood, target energy level, and acoustic preference), and produces a short, friendly explanation of why the top songs fit those preferences.

It is a **classroom / portfolio project** built to demonstrate how a deterministic recommender can be responsibly augmented with a Large Language Model. It is intended for learning and experimentation, not for production music streaming or commercial personalization.

---

## 3. Non-Intended Use

Applied AI Music Recommender should **not** be used for:

- Real-world or commercial music recommendation where accuracy, licensing, and scale matter.
- Any decision-making beyond suggesting songs from its own 20-song catalog.
- Generating factual claims about artists, songs, or music history — the LLM is constrained to explain only the retrieved catalog rows and must not be treated as a music-knowledge source.
- Personalization based on personal or sensitive data; the system stores no user history and should not be extended to do so without a privacy review.

---

## 4. Data

The recommender uses a manually curated catalog of **20 songs** stored in `data/songs.csv`. Each song includes title, artist, genre, mood, energy, tempo, valence, danceability, and acousticness. The scoring engine uses genre, mood, energy, and acousticness; the remaining fields are stored for display or future use.

The dataset spans several genres (pop, EDM, lofi, rock, metal, R&B, country, reggae, and more) and moods (happy, uplifting, chill, romantic, intense, and others), giving enough variety to test different user profiles. As part of the original project, the starter dataset was expanded by adding 10 additional songs.

The catalog is intentionally small and hand-built for reproducibility. It cannot represent the full diversity of musical taste, and some genre/mood combinations have only one or two matching songs.

---

## 5. Algorithm

The recommender compares each song to the user's preferences and assigns a score based on how well it matches four features: **genre, mood, energy level, and acousticness.**

- A **genre match** earns the most points, because genre is the strongest preference in the scoring system.
- A **mood match** earns additional points.
- **Energy similarity** adds points based on how close a song's energy is to the user's target energy.
- If the user prefers acoustic music, highly acoustic songs receive a small **acoustic bonus.**

Every song is scored, the catalog is ranked from highest to lowest score, and the top recommendations are returned along with the deterministic reasons for each score. This scoring logic is unchanged from Project 3 and remains fully deterministic and auditable.

---

## 6. Gemini's Role

Gemini is used **only to write the explanation**, never to decide the recommendations. The flow is:

1. The deterministic engine selects the top songs.
2. `build_recommendation_context` assembles a plain-text context containing **only** the user's preferences and the actually-retrieved songs.
3. `generate_explanation` sends that grounded context to Gemini (via the `google-genai` SDK) and asks for a concise, friendly explanation that uses only the supplied facts.
4. The generated text passes through a deterministic **guardrail** before a user ever sees it.

Because the model is constrained to the retrieved context and its output is verified afterward, Gemini improves readability without being allowed to influence *which* songs are recommended or to invent song facts.

---

## 7. Evaluation Process

The system is evaluated in two complementary ways, and **neither makes a real Gemini API call** (the Gemini client is mocked in tests, and the evaluation harness simulates LLM behavior deterministically):

- **Automated tests** (`python -m pytest -v`) — **61 passed.** These cover the recommender, validation, grounded context and fallback, the mocked LLM wrapper, the guardrail, and full CLI integration (valid AI output shown, rejected output → fallback, LLM error → fallback, invalid profiles skipped before any LLM call).
- **Deterministic evaluation harness** (`python evaluate.py`) — **Score: 7/7 (100.0%).** Seven fixed cases exercise aligned, low-energy/acoustic, and conflicting profiles; out-of-range energy rejection; guardrail rejection of a hallucinated quoted title; guardrail acceptance of a grounded explanation; and a simulated LLM outage that falls back to a valid deterministic explanation.

I also checked, for each profile, that the top recommendations matched the requested genre, mood, and energy, and that recommendations changed sensibly as preferences changed.

---

## 8. Strengths

- **Reliable by design.** The system always returns a recommendation and an explanation, even when the LLM is unavailable, thanks to the deterministic fallback.
- **Grounded and auditable.** Recommendations are fully deterministic, and explanations are constrained to the retrieved songs, so every output can be traced back to concrete data.
- **Well tested.** 61 automated tests plus a 7/7 evaluation harness cover both normal and failure paths.
- **Good matches when data is well represented.** Profiles like High-Energy EDM and Low-Energy Lofi consistently receive recommendations that match the requested genre, mood, and energy.

---

## 9. Limitations and Bias

- **Four features only.** Scoring considers genre, mood, energy, and acousticness; it ignores other characteristics that shape taste.
- **Small dataset.** Some genres and moods are underrepresented. For the R&B / romantic profile, the system finds one excellent match, then fills the rest of the list mostly by energy similarity.
- **Genre is weighted most heavily.** In the adversarial Metal / Happy profile, the recommender prefers a metal song over happy songs because the genre match outweighs the mood match. This can overemphasize one preference even when another matters equally to the user.
- **Uneven quality across users.** Users whose tastes are well represented in the catalog get stronger recommendations than users with less-represented preferences, which can make results feel less fair or less diverse for the latter.
- **Structural, not semantic, guardrail.** The guardrail verifies grounding by structure (titles, length, placeholders); it does not fact-check every sentence the LLM writes.

> Note: Project 3 previously lacked input validation and would accept an invalid energy value such as 1.5. **Project 4 fixes this** — validation now rejects out-of-range or malformed input before any recommendation or LLM call.

---

## 10. Misuse Risks

- **Over-trust in AI text.** A user might treat a fluent explanation as authoritative. Mitigated by grounding and the guardrail, but fluent text can still feel more certain than it is.
- **Hallucinated song facts.** Without constraints, an LLM could invent songs or attributes and present them convincingly.
- **API key exposure.** A committed `GEMINI_API_KEY` could be abused for someone else's quota or billing.
- **Scope creep.** Repurposing this classroom tool for real recommendations, or adding user tracking, would raise accuracy, licensing, and privacy concerns it was not designed for.

---

## 11. Mitigations

- **Grounding** — the LLM only receives the retrieved songs' real facts, limiting what it can claim.
- **Guardrail** — generated explanations are rejected if they are empty, over-long, contain placeholders, quote a song that wasn't retrieved, or fail to name the top recommendation.
- **Deterministic fallback** — any LLM failure or rejected explanation is transparently replaced by a grounded explanation built from the scoring reasons.
- **Input validation** — malformed or out-of-range preferences are rejected before scoring or any API call.
- **Secret hygiene** — `.env` is git-ignored; only `.env.example` with a placeholder value is committed.
- **Free, offline evaluation** — `evaluate.py` never spends real API calls, so reliability can be checked repeatedly.

---

## 12. Future Work

- Add more song features (tempo, danceability, valence, release year, popularity) and a larger dataset.
- Develop **stronger semantic guardrails** that check claims against song attributes, not just titles.
- Improve **recommendation diversity** so results aren't near-duplicates.
- Allow users to weight preferences or choose multiple favorite genres/moods.
- Add a **UI or web app** front end and a broader evaluation dataset with more adversarial cases.

---

## 13. Responsible-AI Reflection

**1. How I collaborated with AI.**
I worked with an AI coding assistant as a pair programmer throughout Project 4. I set the architecture and requirements — validation, grounding, guardrails, fallback, evaluation — and used the assistant to draft modules and tests, then reviewed, ran, and corrected everything myself. AI accelerated the work, but I stayed responsible for the design decisions and for verifying that the code actually did what I intended.

**2. One AI suggestion that helped.**
The **evaluation-harness design** was a genuinely useful suggestion. Rather than testing the LLM by calling it live, the harness runs fixed profiles and *simulates* LLM behavior — including an outage — so it verifies validation, recommendation consistency, the guardrail, and the fallback deterministically, for free, and identically every run. This made reliability something I could check on demand instead of something I had to trust.

**3. One AI suggestion that was flawed.**
An earlier version of the guardrail incorrectly flagged the real song **`"Gym Hero,"`** as a hallucinated title. The guardrail extracted quoted phrases and compared them to the retrieved titles, but it did not normalize surrounding punctuation — so a title written with a trailing comma inside the quotes (`"Gym Hero,"`) became `gym hero,`, which failed to match the real title `gym hero` and was wrongly rejected as a hallucination.

**4. How I verified and corrected it.**
I caught the issue through **manual CLI testing**, where a valid explanation was being rejected unexpectedly. The fix was **punctuation normalization** — stripping trailing punctuation from each quoted title before comparison. I then added a **regression test** (`test_quoted_title_with_trailing_comma_is_valid`) so the bug can't return silently, and confirmed the fix with a full **pytest verification** run (all tests passing).

**5. What surprised me during reliability testing.**
I was surprised that the hardest failures weren't dramatic model errors but **small, boring details** — like a comma — that quietly broke correct behavior. I was also struck by how much confidence the *fallback* gave me: once I knew the system could never be left without a valid explanation, an LLM failure stopped feeling like a crisis and started feeling like a handled case.

**6. Limitations and future improvements.**
The guardrail is still structural rather than semantic, the dataset is small, and the scoring weights are fixed. In the future I'd add semantic verification of explanation claims, expand the dataset, and broaden the evaluation set with more adversarial cases so reliability testing keeps pace with new failure modes.
