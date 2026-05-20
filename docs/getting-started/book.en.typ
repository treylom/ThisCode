#import "design/tokens.typ": color, font, space
#import "design/components.typ": callout, codeblock, term, table-clean, chapter

#set document(
  title: "ThisCode · ThisCodex — The Very First Guide",
  author: "Project Author",
)

#set page(
  width: 176mm,
  height: 235mm,
  margin: (outside: 24mm, inside: 20mm, y: 22mm),
  fill: color.canvas,
  numbering: "1",
  footer: context {
    set text(font: font.body, size: 8pt, fill: color.muted)
    if counter(page).get().first() > 1 [
      #line(length: 100%, stroke: 0.4pt + color.hairline)
      #v(2pt)
      #grid(columns: (1fr, auto),
        [ThisCode · ThisCodex — Getting Started],
        [#counter(page).display()])
    ]
  },
)

#set text(font: font.body, size: 10.5pt, lang: "en", fill: color.body)
#set par(justify: true, leading: 0.72em)
#set heading(numbering: none)

#show heading.where(level: 1): it => {
  v(space.lg)
  text(font: font.body, size: 14pt, weight: "bold", fill: color.ink)[#it.body]
  v(space.xs)
}
#show heading.where(level: 2): it => {
  v(space.md)
  text(font: font.body, size: 11.5pt, weight: "bold",
       fill: color.accent)[#it.body]
  v(space.xxs)
}

// ───────────────────────── Cover ─────────────────────────
#v(4.5cm)
#align(center)[
  #text(font: font.serif, size: 13pt, fill: color.accent,
        tracking: 3pt)[SAMPLE CREW · GETTING STARTED]
  #v(0.9em)
  #text(font: font.body, size: 30pt, weight: "bold", fill: color.ink)[
    ThisCode · ThisCodex
  ]
  #v(0.3em)
  #text(font: font.body, size: 19pt, weight: "bold", fill: color.ink)[
    The Very First Guide
  ]
  #v(0.5em)
  #text(font: font.body, size: 12pt, fill: color.muted)[
    A Beginner-Friendly Walkthrough — No Prior Terminal Experience Required
  ]
  #v(2em)
  #line(length: 38%, stroke: 1.2pt + color.accent)
  #v(1.4em)
  #text(size: 10.5pt, fill: color.body)[
    A single booklet for someone who has never touched this before
  ]
  #v(0.3em)
  #text(size: 9pt, fill: color.muted)[
    2026-05-20 · Project Author · v1 (EN)
  ]
]
#pagebreak()

// ───────────────────────── Intro ─────────────────────────
= Before We Start

I am writing this booklet for someone who isn't quite sure what a "terminal"
is yet. So when a technical term shows up for the first time, I'll add a
short plain-language gloss right next to it. Take it slow.

Here is the big picture in one sentence: *we built a system where you speak
to AI assistants inside a Discord chat room, and they do the work for you.*
There are two installable bundles that bring those assistants to your
computer.

#table-clean(
  columns: (auto, 1fr),
  [*Name*], [*One-line description*],
  [*ThisCode*],
  [Claude-based assistant bundle. The default home for all five team bots.],
  [*ThisCodex*],
  [Codex-based bundle (OpenAI's coding tool). Handles code review.],
)

#callout(kind: "info", title: "The promise of this book")[
  You don't need to memorize anything. A good AI user is not someone who
  memorizes commands — it's someone who can *check the current state in
  small steps and decide the next move.* This book teaches that habit.
]

// ───────────────────────── Ch 1 ─────────────────────────
#chapter("1", "Why Discord?", "A chat app as your AI console")

== Driving AI through a messenger

Most AI tools require you to type commands into a black text window — the
*terminal* (a text-based input window). For a beginner, that black window
feels scary. So we picked Discord, *an app you already know,* as the front
door.

#table-clean(
  columns: (1fr, 1fr),
  [*Using a terminal*], [*Using Discord*],
  [Must remember exact commands], [Ask in plain words],
  [Must sit at your computer], [Works from your phone, one line is enough],
  [Output scrolls away], [Chat history sticks around],
)

== Your team has several assistants

One bot does not do everything. The bots split the work by role and
collaborate inside a Discord channel — much like a human team.

#table-clean(
  columns: (auto, 1fr),
  [*Bot (generic name)*], [*Role*],
  [research-bot], [Research, fact-checking],
  [code-review-bot], [Code review],
  [schedule-bot], [Schedule, reminders],
  [writing-bot], [Writing, documents],
  [orchestrator-bot], [Overall coordination, meetings],
)

#callout(kind: "success", title: "Chapter 1 checkpoint")[
  "Discord is the front door, and inside live several role-specific bots."
  Take that one sentence with you.
]

// ───────────────────────── Ch 2 ─────────────────────────
#chapter("2", "Which Bot to Run?", "Pick by situation, not by name")

== Choose by what you want to do

Don't memorize bot names. Pick by *"what am I trying to do right now?"*

#table-clean(
  columns: (1fr, auto),
  [*What you want to do*], [*Bot to wake up*],
  [Find and organize information], [research-bot],
  [Have someone review my code], [code-review-bot],
  [Track what I planned and when], [schedule-bot],
  [Write a document or article], [writing-bot],
  [Coordinate several bots together], [orchestrator-bot (calls the rest)],
)

== If this is your first time, start with one

Don't turn them all on. Start with *the one you'll use most often,* get
comfortable, then add more. Most beginners start with research or writing.

#callout(kind: "warning", title: "Why not all at once?")[
  More running bots means more computer resources used, and it gets harder
  to tell who said what. Follow the order *one → comfortable → add.*
]

// ───────────────────────── Ch 3 ─────────────────────────
#chapter("3", "Installation (Branch by Situation)", "Pick your path")

== The big picture is just three steps

The setup helper asks you the details one at a time. You only need to know
the overall flow.

#table-clean(
  columns: (auto, 1fr),
  [*Step*], [*What happens*],
  [1. Get the bundle], [Download ThisCode or ThisCodex to your computer],
  [2. Run the setup helper], [The helper *asks* about folders and bot location],
  [3. Connect Discord], [Link your Discord channel to the bots],
)

== Which branch are you on?

#callout(kind: "info", title: "Branch A — I mainly use Claude")[
  Install *ThisCode*. The setup helper is called `/thiscode:setup`. Ask
  for it in chat like this, and the helper will walk you through step by
  step.
]

#codeblock("Please run /thiscode:setup and help me install it", lang: "text")

#callout(kind: "info", title: "Branch B — I also need code review")[
  Add *ThisCodex*. The install command is the one line below. `--apply`
  means "don't just check — actually apply the changes."
]

#codeblock("thiscodex init --apply", lang: "bash")

#callout(kind: "warning", title: "When the helper asks questions")[
  The setup helper asks *one question at a time.* If you don't know what
  to answer, press Enter to accept the safe default — the helper is built
  to stop safely rather than do something risky. Don't be afraid.
]

#callout(kind: "success", title: "Chapter 3 checkpoint")[
  Install = receive → run helper → connect Discord. The helper *asks* its
  way through. You only need to remember the one or two commands above.
]

// ───────────────────────── Ch 4 ─────────────────────────
#chapter("4", "alias · yolo · discord", "Three words you'll hear a lot")

Let me unpack the three words that come up most often. Knowing what they
mean is enough.

== alias — a short nickname for a long command

An *alias* (nickname) lets you give a *short label* to a long, complex
command. For example, the long command that wakes up a bot can be
shortened to a single word like `mybot`. The setup helper creates the
alias for you and writes it down so it persists.

#codeblock("mybot   # nickname for 'wake up my bot' (long command)", lang: "bash")

== yolo — proceed automatically without asking each time

*yolo* (auto-proceed mode) lets the bot finish a task *on its own* instead
of asking "is it OK to do the next step?" each time. It's faster, but
also means you trust the bot to keep going — so the helper asks once
before enabling it.

#callout(kind: "danger", title: "yolo pitfall")[
  Don't enable it just because it's convenient. yolo can perform
  hard-to-undo actions (such as deleting files) automatically. Start with
  it *off,* then turn it on once you're comfortable.
]

== discord — the channel between you and the bots

Setting up the *Discord* connection means deciding "which chat room's bot
listens to me." Once you connect it, just typing into that room is enough
to make the bot work — even from your phone.

#callout(kind: "success", title: "Chapter 4 in one line")[
  alias (nickname) shortens commands · yolo (auto) lets the bot finish on
  its own (handle with care) · discord (link) builds the channel you talk
  through.
]

// ───────────────────────── Ch 5 ─────────────────────────
#chapter("5", "How the Memory Works", "What the bots remember and why")

== Bots have memory too

So a bot doesn't forget important things between conversations, there is
a *memory* (a place where the bot stores facts). It comes in two flavors.

#table-clean(
  columns: (auto, 1fr),
  [*Memory kind*], [*What goes in*],
  [Shared memory], [Facts, rules, and user preferences all bots can see],
  [Per-bot memory], [The bot's own tone, recovered mistakes, personal notes],
)

== Today's approach vs. a better one

Today, when a session starts the bot loads the entire shared memory
*all at once.* As the pile grows, you hit the "it remembers everything
but can't surface the right thing" problem. So we are studying the
better-built memory systems out there and designing an improved approach.

#callout(kind: "info", title: "Research takeaways (in plain words)")[
  - *Hybrid search is the standard* — combining meaning-based search and
    relationship-based search is today's default. Single-method search
    is the older way.
  - *Time-handling is the differentiator* — instead of deleting old
    memories, mark them as "old version." It makes retracing easier.
  - *Memory should evolve* — when a new note arrives, it can update the
    links of older notes automatically (A-MEM style). This fits our
    Obsidian-based structure well.
]

#callout(kind: "warning", title: "What a beginner actually needs to know")[
  The bot takes care of the memory internals. As a user, it's enough to
  remember this: *"the bot keeps important things, and instead of deleting
  old stuff it marks it as old."*
]

// ───────────────────────── Ch 6 ─────────────────────────
#chapter("6", "When It Doesn't Work", "Troubleshooting basics")

Don't panic if you're stuck. *Don't guess — narrow it down, top to
bottom.* Going through the list one item at a time solves most issues.

== Four common symptoms

#table-clean(
  columns: (1fr, 1fr),
  [*Symptom*], [*Where to look first*],
  [The bot doesn't respond], [Is the Discord connection alive? (Ch. 4)],
  ["command not found"], [Is the alias saved? Did you open a new window?],
  [Korean / non-ASCII text looks broken], [Font installation (the PDF uses system fonts)],
  [The bot touches the wrong folder], [Rerun the setup helper to reset the location],
)

== If it still doesn't work

#callout(kind: "info", title: "Just check these three lines")[
  1. Am I in the right folder? · 2. Is the bot awake (does it respond on
  Discord)? · 3. What did I just change? — Tell the bot these three lines
  as-is, and the bot will narrow down the rest.
]

#callout(kind: "danger", title: "Don't do this")[
  Don't keep running the same command in hope it will start working, and
  don't blindly run delete commands you don't understand. The fastest
  path is to *write one sentence describing what's broken* and ask the
  bot.
]

#callout(kind: "success", title: "One last word")[
  Twenty minutes of fighting in the wrong folder is worse than ten
  seconds of "wait — am I in the right place?" Go slowly, check in small
  steps. — Project Author
]

#pagebreak()
#align(center)[
  #v(2cm)
  #text(font: font.serif, size: 11pt, fill: color.muted)[
    Sample Crew · ThisCode · ThisCodex
  ]
  #v(0.3em)
  #text(size: 9pt, fill: color.muted)[
    This booklet is updated at every milestone.
  ]
]
