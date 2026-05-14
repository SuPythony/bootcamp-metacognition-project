# Day 2 Reflections

**Today, I contributed most by...**
Putting forward the initial structured idea in terms of 3 phases: framing the problem, working through it, and reflection. This gave the team a concrete starting point to improve on. The final design kept the spirit of that but generalized it to work across domains, not just coding. Update: I prepared a [pitch](./programming-tutor-pitch.html) with a few more details worked out and presented it to the team.

**One thing I understood clearly was...**
The core principle the whole design rests on: the assistant shouldn't engage with the problem until the user has said something meaningful about their own understanding of it. This is what separates this from a normal chatbot.

**One thing I pretended to understand, or only partly understood, was...**
How the framing phase should actually work in practice --- what kinds of clarifying questions the assistant should ask before breaking down the problem. Claude gave me a suggestion on this that I accepted without serious thought. It was too vague to be useful at all, and I came back and made it more concrete later.

**One moment where AI helped me was...**
Working out the user reflection and summary metrics part of the tool. They are essential components to track and understand learning but I did not have any good ideas for metrics beyond the obvious ones, I used Claude for help with that.

**One moment where AI made me less careful was...**
The framing phase suggestion. It came out of Claude sounding plausible and well-structured, so I didn't question it on the spot. I learned that even if it sounds reasonable, it needs to still be well-defined enough to count as innovation in our product.

**One thing another teammate knew that I depended on was...**
That generalizing away from a live code editor was the right move. My instinct was to build around that specifically, and they pushed back (which as good) since the same learning goals can be achieved with a chat-based approach and for different domains like math, and that live editing would have been a torture to implement from the start.