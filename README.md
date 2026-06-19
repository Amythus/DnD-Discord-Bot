# DnD Discord Dungeon Master Bot

An AI-driven Dungeon Master bot for Discord that allows players bring their own character sheets from DnD Beyond, play D&D modules, and roleplay without needing an experienced human Dungeon Master!

The bot uses a multi-model AI pipeline with MongoDB to track game state and Gemini 3.1 Flash Lite for context caching and swift replies.

---

                          [ DISCORD USER PLATFORM ]
                                      │
              (Message Sent: Does it begin with @botname or command prefix?)
                                      ▼
                        ┌───────────────────────────┐
                        │   Discord Cog Middleware  │
                        │   (Deterministic Filter)  │
                        └─────────────┬─────────────┘
                                      │
             ┌────────────────────────┴────────────────────────┐
             ▼ (No prefix/@mention)                            ▼ (Prefix/@mention matched)
    ┌─────────────────┐                               ┌──────────────────────────────┐
    │  EXIT / NO-OP   │                               │       CHAT PARSER COG        │
    │ (True OOC Chat) │                               │      (Gemini 3.1 Flash)      │
    └─────────────────┘                               │                              │
                                                      │ 1. Checks: concurrency_lock  │
                                                      │ 2. Outputs array format:     │
                                                      │    ["in_game_action:x",...]  │
                                                      └──────────────┬───────────────┘
                                                                     │
              ┌──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┐
              ▼ (If has "meta_question")                             ▼ (If has "in_game_action:mechanical")                 ▼ (If has "in_game_action:pure_narrative")
  ┌───────────────────────────────┐                      ┌───────────────────────────────┐                      ┌───────────────────────────────┐
  │        DM ASSISTANT           │                      │       RULE ADJUDICATOR        │                      │   NARRATIVE & ROLEPLAY BOT    │
  │      (Gemini 3.1 Flash)       │                      │  (Gemini 3.5 Pro + Rule Cache)│                      │    (Gemini 3.1 Flash-Lite)    │
  │                               │                      │                               │                      │                               │
  │ Resolves rule text/lore       │                      │ Evaluates rules matrix & keys │                      │ Directly processes player text│
  │ lookups completely out-of-band│                      │ out deterministic state diffs.│                      │ against basic location logs.  │
  └───────────────────────────────┘                      └───────────────┬───────────────┘                      └───────────────┬───────────────┘
                                                                         │                                                      │
                                                                         │ [Snapshot A Captured]                                │
                                                                         ▼                                                      │
                                                      ┌──────────────────────────────────────────────────┐                      │
                                                      │           DETERMINISTIC MUTATION ENGINE          │                      │
                                                      │ - Applies target $inc delta metrics atomically.  │                      │
                                                      │ - Flips inspiration / room positioning arrays.   │                      │
                                                      └──────────────────┬───────────────────────────────┘                      │
                                                                         │                                                      │
                                                                         │ [Snapshot B Captured]                                │
                                                                         ▼                                                      │
                                                      ┌──────────────────────────────────────────────────┐                      │
                                                      │             STATE COMPARISON HANDSHAKE           │                      │
                                                      │ - Extracts precise micro-diff logs locally.      │                      │
                                                      │ - Compiles structural semantic payload.          │                      │
                                                      └──────────────────┬───────────────────────────────┘                      │
                                                                         │                                                      │
                                                                         │ (Passes minimized semantic diff)                     │
                                                                         └───────────────────────┬──────────────────────────────┘
                                                                                                 │
                                                                                                 ▼
                                                                      ┌──────────────────────────────────────────────────┐
                                                                      │            FINAL COMBINED RESPONSE ROUTER        │
                                                                      │               (Gemini 3.1 Flash-Lite)            │
                                                                      │                                                  │
                                                                      │ Harmonizes dice outcomes, rule adjustments, and  │
                                                                      │ character speech into a cinematic Discord reply.  │
                                                                      │ - Releases session concurrency_lock: false       │
                                                                      └──────────────────────────────────────────────────┘