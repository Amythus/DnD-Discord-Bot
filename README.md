# DnD Discord Dungeon Master Bot

An AI-driven Dungeon Master bot for Discord that allows players bring their own character sheets from DnD Beyond, play D&D modules, and roleplay without needing an experienced human Dungeon Master!

The bot uses a multi-model AI pipeline with MongoDB to track game state and Gemini 3.1 Flash Lite for context caching and swift replies.

---

                                [ DISCORD USER PLATFORM ]
                                            │
                    (Message Sent: Does it begin with @botname or prefix?)
                                            │
                                            ▼
                              ┌───────────────────────────┐
                              │   Discord Cog Middleware  │
                              │   (Deterministic Filter)  │
                              └─────────────┬─────────────┘
                                            │
                    ┌───────────────────────┴───────────────────────┐
                    ▼ (No prefix/@mention)                          ▼ (Prefix/@mention matched)
          ┌─────────────────┐                     ┌───────────────────────────────────────────────┐
          │   EXIT / NO-OP  │                     │                CHAT PARSER COG                │
          │ (True OOC Chat) │                     │              (Gemini 3.1 Flash)               │
          └─────────────────┘                     │                                               │
                                                  │ 1. Checks & sets concurrency_lock             │
                                                  │ 2. Extracts intents & targets                 │
                                                  │ 3. Outputs Action Queue Array format:         │
                                                  │    ["in_game_action:x", "meta_question", ...] │
                                                  └───────────────────────┬───────────────────────┘
                                                                          │
                                                                          ▼ Unpack Action Intent Queue
                                                                          │
  ┌───────────────────────────────────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────┐
  ▼ (If payload features "meta_question")                                 ▼ (If payload features mechanical "in_game_action")       ▼ (If payload features "pure_narrative")
┌───────────────────────────────────────┐                                 │                                                         ┌───────────────────────────────────────┐
│             DM ASSISTANT              │                                 ▼                                                         │       NARRATIVE & ROLEPLAY BOT        │
│          (Gemini 3.1 Flash)           │               ┌──────────────────────────────────────────────────┐                        │        (Gemini 3.1 Flash-Lite)        │
├───────────────────────────────────────┤               │           BUFFER STACK & CONTEXT LAYER           │                        ├───────────────────────────────────────┤
│ Resolves rule text, lore index maps,  │               │ - Node Matrix     (Immutable read-only map graph)│                        │ Directly processes player text against│
│ and manual lookups out-of-band.       │               │ - Global Tracker  (Persistent MongoDB base truth)│                        │ basic location logs to synthesize localized│
│ Bypasses live mutations completely.   │               │ - Session Delta   (Active volatile live cache)   │                        │ responses.                            │
└───────────────────┬───────────────────┘               └────────────────────────┬─────────────────────────┘                        └───────────────────┬───────────────────┘
                    │                                                            │                                                                      │
                    │                                                            ▼ Capture Snapshot A                                                   │
                    │                                                            │ (Absolute ground-truth state before batch)                           │
                    │                                                            ▼                                                                      │
                    │                   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐     │
                    │                   │                                  PYTHON ENGINE BATCH TRANSACTION LOOP                                   │     │
                    │                   │                                                                                                         │     │
                    │                   │    ┌──────────────────────────────────────────────────────────────────────────────────────────────┐     │     │
                    │                   │    │                                                                                              │     │     │
                    │                   │    ▼                                                                                              │     │     │
                    │                   │ [Evaluate Next Action]                                                                            │     │     │
                    │                   │    │                                                                                              │     │     │
                    │                   │    ▼                                                                                              │     │     │
                    │                   │ Rule Adjudicator (Gemini 3.5 Flash) ◄── (Pulls directly from pinned Rulebook Context Cache)         │     │     │
                    │                   │    │                                                                                              │     │     │
                    │                   │    ├──► [Returns is_legal: false] ──► SHORT CIRCUIT! Rollback context stack to Snapshot A         │     │     │
                    │                   │    │                                                                                              │     │     │
                    │                   │    ▼                                                                                              │     │     │
                    │                   │ Deterministic Mutation Engine ──► Enforces MongoDB atomic operators ($inc, $set, $delete)         │     │     │
                    │                   │    │                              strictly modifying target sub-elements in Session Delta         │     │     │
                    │                   │    ▼                                                                                              │     │     │
                    │                   │ Python Event Trigger Middleware                                                                   │     │     │
                    │                   │    ├──► Immediate Trigger? ──► (Injects Cascade Mutation into Active Session Delta)               │     │     │
                    │                   │    └──► Delayed Trigger?   ──► (Registers future execution timestamp to scheduled_events Array)   │     │     │
                    │                   │    │                                                                                              │     │     │
                    │                   │    ▼                                                                                              │     │     │
                    │                   │ Append Result Logs ──► Pushed to local chronological context action_results_list                  │     │     │
                    │                   │    │                                                                                              │     │     │
                    │                   │    └─► Iterates sequentially until action queue is fully exhausted ───────────────────────────────┘     │     │
                    │                   └────────────────────────────────────────┬────────────────────────────────────────────────────────────────┘     │
                    │                                                            │                                                                      │
                    │                                                            ▼ Capture Snapshot B                                                   │
                    │                                                            │ (Absolute post-mutation state)                                       │
                    │                                                            ▼                                                                      │
                    │                                   ┌──────────────────────────────────────────────────┐                                            │
                    │                                   │            STATE COMPARISON HANDSHAKE            │                                            │
                    │                                   │ - Runs locally in native Python code             │                                            │
                    │                                   │ - Diffs Snapshot A & B to extract micro-logs     │                                            │
                    │                                   │ - Compiles structural minimized semantic diff map│                                            │
                    │                                   └────────────────────────┬─────────────────────────┘                                            │
                    │                                                            │                                                                      │
                    │                                                            │ (Passes structural diff payload)                                     │
                    │                                                            ▼                                                                      │
                    └────────────────────────────────────────────────────────────►          ◄───────────────────────────────────────────────────────────┘
                                                                                 │
                                                                                 ▼
                                                ┌──────────────────────────────────────────────────┐
                                                │          FINAL COMBINED RESPONSE ROUTER          │
                                                │             (Gemini 3.1 Flash-Lite)              │
                                                ├──────────────────────────────────────────────────┤
                                                │ - Harmonizes dice outcomes, rule adjustments,    │
                                                │   and character speech into a unified sequence.  │
                                                │ - Synthesizes Snapshot A, Diff Map, & Result Logs│
                                                │ - Releases session concurrency_lock: false       │
                                                └────────────────────────┬─────────────────────────┘
                                                                         │
                                                                         ▼
                                                             Cinematic Discord Output

---

Session Lifecycle:

 ┌────────────────────────────────────────────────────────────────────────┐
 │ 1. SESSION STAGING & COMPOSING PHASE                                   │
 │                                                                        │
 │   [GM invokes /start_session command]                                  │
 │                    │                                                   │
 │                    ▼                                                   │
 │   Render Discord View with Dropdown (Pre-seeded modules list)          │
 │                    │                                                   │
 │                    ▼                                                   │
 │   Create Shell Session & Assign Globally Unique session_id (UUID)      │
 │   (Adventure chosen; structural baseline set)                          │
 │                    │                                                   │
 │                    ▼                                                   │
 │   [Players invoke /join_session command]                               │
 │                    │                                                   │
 │                    ▼                                                   │
 │   Render Discord View with Dropdown (Pre-imported sheets by discord_id)│
 │                    │                                                   │
 │                    ▼                                                   │
 │   Execute Out-of-Band Handshake with D&D Beyond API;                   │
 │   Update Character Registry with Fresh Upstream Absolute Metrics       │
 │                    │                                                   │
 │                    ▼                                                   │
 │   Construct Structural Delta Baseline from Updated Character Registry, │
 │   & Register Volatile Profile Object to Active Session                 │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ 2. RUNTIME ENFORCEMENT & ADVENTURE LOCK IN                             │
 │                                                                        │
 │   [GM invokes /begin_adventure command]                                │
 │                    │                                                   │
 │                    ▼                                                   │
 │   Lock Baseline Session Architecture (State setup becomes immutable)   │
 │                    │                                                   │
 │                    ▼                                                   │
 │   Reroute All Live Mutations to Session Delta Transaction Pipeline     │
 │   ┌──────────────────────────────────────────────────────────────────┐ │
 │   │  1. Unstructured text captures stream through ChatParserCog      │ │
 │   │  2. Intercept via Concurrency Lock Manager & StagedAction Cache  │ │
 │   │  3. Evaluate Inputs + Background Scheduled Events Array Ticks    │ │
 │   │     against Node Matrix Layout & Rulebook Context Cache          │ │
 │   │  4. Apply Atomic Operators ($inc, $set) strictly to Delta subdocs│ │
 │   └──────────────────────────────────────────────────────────────────┘ │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ 3. TERMINATION & DELTA DATABASE STORAGE                                │
 │                                                                        │
 │   [GM invokes /end_session save command]                               │
 │                    │                                                   │
 │                    ▼                                                   │
 │   Bypass Upstream Sync/Merge (No raw character state reconciliation)   │
 │                    │                                                   │
 │                    ▼                                                   │
 │   Generate Fresh snapshot_id (UUID) to Fork Current Frame History       │
 │                    │                                                   │
 │                    ▼                                                   │
 │   Serialize Session Delta Object State Linked to parent session_id      │
 │                    │                                                   │
 │                    ▼                                                   │
 │   Commit Active Delta Stash into MongoDB Document Collections         │
 │   - Primary ID Key: snapshot_id (Unique state identifier for rollback) │
 │   - Relational Identifier: session_id (Parent campaign anchor UUID)    │
 │   - Metadata Stamp: guild_id (Active server tracking coordinate)       │
 │   - Metadata Stamp: discord_id (Initiating GM anchor marker)           │
 │                    │                                                   │
 │                    ▼                                                   │
 │   Wipe/Reset active_session_id Fields from All Whitelisted             │
 │   ChannelConfig Documents (Decouples multi-channel locks)              │
 │                    │                                                   │
 │                    ▼                                                   │
 │   Tear Down Context Layers & Clear Channel Concurrency Locks           │
 └────────────────────────────────────────────────────────────────────────┘