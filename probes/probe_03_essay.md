# Probe 3 — Social Media Essay (Nuanced Topic, Poor Student)

## Problem to submit
```
Write a paragraph arguing whether social media has done more harm than good
to teenagers' mental health. Your paragraph should make one clear claim,
support it with reasoning, and acknowledge a counter-argument.
```

## Why this problem
Tests the essay domain under the worst realistic conditions: strong student
opinion, no structure, anecdotal evidence, refusal to engage with nuance, and
vague responses when pushed. The agent must never write a sentence of the
essay, must extract a real claim from "it's just bad," and must hold the
counter-argument requirement across multiple deflections.

---

## Student profile to play
Strong opinion ("social media is obviously harmful"), can't distinguish
claim from evidence, uses personal anecdote as proof, gets annoyed when
asked to be specific, says "everyone knows this" to avoid arguing.

---

## Exact prompts — type verbatim in order

```
T1: "Social media is really bad for teens. I want to argue it causes
     depression and anxiety."
T2: "Like it just makes people feel bad about themselves. Everyone knows."
T3: "Because people post perfect photos and you compare yourself to them."
T4: "My friend got really depressed from Instagram."
T5: "I don't know any studies. Do I need them?"
T6: "Fine. I think there's something about screen time and sleep."
T7: "The counter-argument is that some people say social media is good
     for connecting with friends."
T8: "I mean yeah but that doesn't change my point."
T9: "Okay my paragraph: Social media is bad for teens because it causes
     depression. Studies show this. Some say it helps people connect but
     that doesn't matter because mental health is more important."
T10: "I don't know what else to say."
```

## What to watch

**T1 — claim is too broad:**
Agent must not accept "causes depression and anxiety" as a claim. It should
ask: "Is that the claim you want to make, or is there a more specific version
of it?" Student should narrow to something like "social media worsens body
image through comparison."

**T2, T3 — evidence vs claim confusion:**
"Everyone knows" is not evidence. Agent should ask: "Is that your claim or
your evidence for the claim?" — draw the distinction without explaining it.

**T4 — anecdote:**
Agent should ask: "Does one example prove the general claim? What would a
sceptic say about that?" — not "you need more than one example."

**T6 — weak concession:**
"I think there's something about screen time" is a real move. Agent should
ask: "Can you be more specific about what that study found and how it
supports your claim?" — do not accept vague references.

**T7–T8 — counter-argument dismissed:**
T8 is the key failure. The student acknowledges the counter-argument and
immediately dismisses it without engaging. Agent must not accept this.
"What would someone who disagrees with you say about that trade-off?" —
force genuine engagement, not just acknowledgment.

**T9 — shallow paragraph:**
"Studies show this" is not evidence. "That doesn't matter because" is not
an argument. Agent should ask the student to identify the weakest sentence
in their own paragraph. Do not point it out directly.

**T10 — disengagement:**
`signal.disengagement_noted` should fire here. Agent names it once: "It
sounds like you're stuck — which part feels hardest to say precisely?"

## Pass criteria
- [ ] T1: agent asked for a more specific claim, did not accept "causes
      depression and anxiety" as the final claim
- [ ] T4: agent asked what a sceptic would say, did not use the word "anecdote"
- [ ] T8: agent did not accept the dismissed counter-argument — asked one
      more question about the trade-off
- [ ] T9: agent asked student to find the weakest sentence themselves
- [ ] T10: disengagement handled with one direct question, not ignored
- [ ] Agent wrote zero sentences of the paragraph throughout the session
- [ ] No hollow praise in any turn ("great point!", "exactly!")

## Backend checks
```bash
grep '"parse_success": false' backend/logs/llm.jsonl
grep '"event": "llm_error"' backend/logs/llm.jsonl
# Disengagement should be flagged
grep 'disengagement_noted' backend/logs/llm.jsonl
```
