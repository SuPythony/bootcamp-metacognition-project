# Math Probe Templates

---

## 06 — River crossing speed (working backward + vague setup)

**Problem**
A boat crosses a river in 10 minutes going directly across. The river is 500m
wide and has a current. When the boat aims straight across, it actually lands
300m downstream. What is the boat's speed in still water, and what is the
current speed?

**Target:** Working backward heuristic. Students almost always try to find
speeds directly and get stuck. The productive move is to realise the crossing
time and the displacement give you both components of velocity without solving
a system.

**How to prompt:** Start vague — "I don't know where to begin, there are too
many unknowns." Let the agent work through the decomposition. When stuck on
the algebra, say "can't you just tell me the speeds?" Push for the graph tool
to visualise the velocity vector triangle.

**How to judge:** Agent should eventually surface the working backward
heuristic ("if you had the answer, what would the velocity triangle look
like?"). Graph tool should be used to show the vector decomposition. Agent
must not enumerate the solution steps. At wrap-up, student should be able to
explain why the crossing time is independent of the current.

---

## 07 — Bacteria growth and depletion (open-ended modelling)

**Problem**
A colony of bacteria doubles every 3 hours. A scientist adds an antibiotic
that kills 30% of the bacteria every hour. Will the colony survive long-term?

**Target:** Modelling from scratch with no fixed formula. The student must
construct the recurrence relationship themselves. Graph tool is essential —
plotting the population over time is the only way to see whether growth or
decay wins. Sympy handles the algebra once the model is set up.

**How to prompt:** Start with "I'm not sure what equations to use." Try
guessing that the colony survives, then try guessing it dies — use
guess-and-check to feel out the answer before formalising. Resist setting
up equations for as long as possible.

**How to judge:** Agent should not write the recurrence relation. Should ask
"what happens in one hour?" before any formalisation. Graph tool must be
called once the student has a model — not before. The wrap-up question
should surface the general principle (continuous growth rate vs decay rate
comparison), not just the answer for this specific case.

---

## 08 — Ladder against a wall (geometry with a twist)

**Problem**
A 5m ladder leans against a wall. The base is 3m from the wall. The base
starts sliding away at 1m/s. How fast is the top sliding down when the base
is 4m from the wall?

**Target:** Related rates — the student must see two changing quantities
linked by a fixed constraint (Pythagoras). Tests whether the agent surfaces
the auxiliary problem heuristic: "what stays the same as things change?"
Algebra tool for the implicit differentiation; graph tool for the position
at the moment in question.

**How to prompt:** Start with "the ladder is moving so I have variables
everywhere." Try to treat it as a static problem first. When that fails,
ask "what is actually constant here?" The implicit differentiation step
is a natural escape hatch moment — use it.

**How to judge:** Agent must not say "use implicit differentiation"
unprompted — this is the insight the student should reach. Should ask "what
does Pythagoras tell you about the ladder at any moment?" Graph the triangle
at the specific moment (4m base) so the student sees the geometry. Algebra
tool for differentiation once student has the equation.

---

## 09 — Fuel economy optimisation (no obvious objective function)

**Problem**
A delivery driver makes 400km trips. At speed v (km/h), the car uses
fuel at a rate of 0.01v² litres per km. Fuel costs £1.50 per litre.
The driver earns £20/hour. What speed minimises total trip cost?

**Target:** Building the objective function from scratch. Students don't
know what to minimise until they've decomposed the problem into fuel cost
plus time cost. Tests the decompose-and-recombine heuristic and the
Carry Out the Plan phase — the algebra is straightforward once the function
is built.

**How to prompt:** Start with "I don't know what I'm optimising." Say
"I know faster is cheaper on time but worse on fuel" — this is the right
intuition but not an equation. Resist writing the cost function until the
agent has asked about both components separately.

**How to judge:** Agent should ask about fuel cost and time cost separately
before combining them. Should not write the objective function. Graph tool
to show total cost vs speed — the minimum should be clearly visible before
the student differentiates. Algebra tool for derivative and solving. Wrap-up
should surface the general insight: every such problem has a trade-off speed.

---

## 10 — Population model with missing data (under-constrained problem)

**Problem**
A town's population was 12,000 in 2010. By 2020 it was 15,600. The local
council wants to know when the population will reach 20,000. Assume
exponential growth.

**Target:** Model selection and parameter fitting from two data points.
Problem is deliberately under-specified — "exponential growth" is stated
but not justified. Tests the clarification phase (is this the right model?)
and the variation heuristic (what if it were linear instead?). Sympy fits
the model; graph tool shows both linear and exponential fits.

**How to prompt:** Start by asking "is exponential growth a good assumption?"
Use this to explore the clarification phase — reframing the problem as a
model selection question. When doing the algebra, make an arithmetic error
on purpose to force the algebra tool verification step.

**How to judge:** Agent should take the "is this the right model?" question
seriously and guide the student to examine what exponential growth implies
about the underlying mechanism. Should not skip straight to fitting the
parameters. Graph tool should show both models to let the student judge.
Deliberate error should produce the algebra tool being called to verify,
not the agent correcting in chat. Wrap-up: student should explain why the
prediction depends heavily on model choice.

---

## 11 — Cryptography warmup (pattern induction from examples)

**Problem**
A simple cipher shifts each letter by a fixed number of positions in the
alphabet (e.g. A→D, B→E if the shift is 3). You intercept the message
"KHOOR". Decode it, and explain how you would crack any message encrypted
this way if you didn't know the shift.

**Target:** Pattern / induction heuristic. No formula exists — the student
must construct the method from examples. Tests whether the agent can guide
discovery of a systematic approach (try all 26 shifts, frequency analysis)
without naming the technique. No tools needed; this is a pure reasoning probe.

**How to prompt:** Start with "I'll just try a few shifts until I get
something." Crack the specific message easily, then claim "I'm done." Let
the agent push toward the general method. Resist generalising — say "why
would I need a general method if I can just try them all?"

**How to judge:** Agent should not name "frequency analysis" or "brute
force" until the student is already describing the concept. Should ask
"what if the message were 1000 characters long — would trying all shifts
be equally easy?" to surface the need for a smarter approach. Wrap-up
should ask the student to articulate the general attack strategy in their
own words — this is a strong test of the understanding delta.