# This document acts as the active engineering backlog and flight checklist for the bot's core systems. 
Progression follows a Red 🔴 -> Green 🟢 -> Refactor 🔵 Development paradigm.

## TDD State Key
🔴 Red: Test suite written and failing as expected (or work not started).
🟢 Green: Implementation passing all assertions.
🔵 Refactor: Code works but requires refactoring

## Database and Discord Handshake
[x] 🟢 Test Case [Database Initialization]: Assert that the database connection is established and the collections are created successfully.
[x] 🟢 Test Case [Discord Bot Initialization]: Bot connects to discord and responds to a ping command.

## Database Moddels/Schema
[ ] 🔵 Test Case [Database Schema]: Assert that the database schema is valid and can be created without errors
    [x] 🟢 Monster
    [x] 🟢 Character
    [x] 🟢 Channel
    [x] 🟢 Spell
    [x] 🟢 Player Registry
    [x] 🟢 Delta
    [x] 🟢 Saved_Delta
    [x] 🟢 Item 
    [x] 🔴 Node
    [ ] 🔴 Gemini Context Cache (GCC)

## Ingestion Engine
Character sheets should be ingested from D&D Beyond and stored in the database. Campaigns/Adventures should be ingested from 5e tools and stored in the database. 
[x] 🟢 Test Case [Character Ingestion]: Assert that a character can be ingested from D&D Beyond and stored in the database.
[x] 🟢 Refactor DBB Ingestor with Pydantic Data Transfer Objects (DTOs)
[x] 🟢 Test Case [Campaign Ingestion]: Assert that the adventure can be ingested from 5e tools markdown or pdf (three pass pipeline)
    [x] 🟢 Pass 1 (Map Discovery): Gemini parses over markdown adventure and creates a flat node array with node_ids
    [x] 🟢 Pass 2 (Map Discovery): Iterates over the flat node array and hydrates each node with the appropriate data from the markdown adventure.
    [x] 🟢 Pass 3 (Node Validation): Iterates over the flat node array and validates that each node has the appropriate pointers.
    [x] 🟢 Pass 4 (Blueprint Compilation Phase): Assembles master blueprint containing all necessary fields to being an adventure.

## Seeding Database
[ ] 🔴 Test Case [Seed Data]: Assert that the core rulebook markdown files in 5e repo can be parsed, cleaned, and inserted into database
    [ ] 🔴 PHB: Players Handbook 2024
    [ ] 🔴 DMG: Dungeon Masters Guide 2024
[x] 🟢 Test Case [Seed Data]: Assert that base DnD bestiary is populated into the Monster collection database
    [x] 🟢 MM: Monster Manual 2025
    [x] 🟢 VGtM: Volo's Guide to Monsters 2025
    [x] 🟢 MToF: Mordenkainen's Tome of Foes 2025
[x] 🔵 Test Case [Seed Data]: Assert that base DnD items are populated into the Item collection database
    [ ] 🔴 Refactor seed pipeline to use a dispatcher to handle partnered content (mixed json files)
[x] 🟢 Test Case [Seed Data]: Assert that base DnD spells are populated into the Spell collection database

## 📦 Discord Bot
[x] 🟢 Test Case [Discord Bot]: Assert that the Discord bot is running and can be interacted with
[x] 🔵 Discord Cogs to compartmentalize @commands, /commands, and event listeners

## Discord Cogs
[x] 🟢 Import Cog - imports characters from D&D Beyond uri using `/import <ddb_character_link>`
    [x] 🟢 DDB json response payload follows strict pydantic data transfer object, is linked with a discord user_id, and upserted into database
[ ] 🔴 Session Cog - handles session management
    [ ] 🔴 `/start_session` - displays a Discord view with a dropdown menu of adventures to choose from, selecting an adventure creates a shell session and unlocks other session commands
    [ ] 🔴 `/join_session` - displays a Discord view with a dropdown menu of characters to choose from, selecting a character adds them to the session
    [ ] 🔴 `/begin_adventure` - locks previous session commands, hydrates session delta, and initiates the adventure
    [ ] 🔴 `/end_session` - saves active session delta to the database
[ ] 🔴 Chat Parser Cog - listens for `@<botname> <message>` and dispatches player messages into player intent payloads: [in_game_action],[dialogue],[status_check],[meta_question],[OOC]
    [ ] 🔴 [in_game_action] is dispatched to the rule adjudicator model
    [ ] 🔴 [dialogue] is dispatched to the narrative roleplay model
    [ ] 🔴 [status_check] is dispatched to a python that queries the session delta for the status of the character against the character registory
    [ ] 🔴 [meta_question] is dispatched to the meta question model
    [ ] 🔴 [OOC] is out of context or typos and is ignored by the bot and discarded
[ ] 🔴 DM Assistant Cog - handles @bot questions about meta gamestate (e.g. What NPC are we looking for?) - responds to dispatched messages from the chat parser cog 

## Game Engine/Pipeline

## 🔒 Concurrency Lock Manager
[ ] 🔴 The state protection matrix preventing multi-event state corruption at the individual guild_id boundary.


## ⚔️ Interaction Engine & Staged Actions
The asynchronous UI component system handling buttons, modal responses, timeouts, and multi-click race conditions.

[ ] 🔴 Test Case [Staged Action Registration]: Assert that initiating a rolling prompt or choice populates the StagedAction properties inside the active SessionDelta, complete with its specific callback payload and a dynamic UTC expiration timestamp.
[ ] 🔴 Test Case [Atomic Deletion Protection]: Assert that when an interaction occurs (or a background expiration worker fires), the thread executes an atomic find_one_and_delete logic on the sub-document. Verify that the winner handles execution rights, while the losing thread receives None and exits cleanly.
[ ] 🔴 Test Case [Automated Timeout Execution]: Mock an elapsed timeout clock and assert that a background cron/worker thread automatically identifies expired StagedAction entities, clears them out atomically, and pushes a "Time Expired" alert to the targeted Discord channel.
[ ] 🔴 Test Case [Intent Parser Constraints]: Assert that the Intent Parser / Lock Manager throws an immediate user exception ("You have an action pending!") if a player types a new text command while an unresolved StagedAction button prompt is counting down in their session cache.

## 🗳️ Overworld Voting Engine
🔴 [ ] The asynchronous multi-user voting apparatus controlling safe macro-travel across points of interest.


## 🤖 LLM Context Cache Layer
Google Gemini Models paid tier APIs have implicit and explicit context caching to reduce token usage and allow for more complex interactions.
[ ] 🔴 The world state model requires caching of the core rulebooks and the world state
[ ] 🔴 The rules adjudication model requires caching of the core rulebooks
[ ] 🔴 The narration/roleplay model requires caching of the adventure specific lorebooks and session delta
[ ] 🔴 The DM assistant model requires caching of all of the above? (may skip implementing this to reduce costs)

## Bugfixes
[ ] must be strictly enforced You perform a synchronous "Call LLM -> Mutate State -> Re-build Context Matrix -> Call LLM" loop for every item in the queue.
[ ] Implement a strict Short-Circuit Error Registry in the Python transaction loop. The Rule Adjudicator's structured JSON output schema must include a boolean is_legal or execution_halted flag. If Python catches a failed action state or validation exception mid-queue, it must immediately wipe the remaining pending actions in that specific batch, roll back any transient mid-queue mutations to restore Snapshot A, and flag the failure to the Response Router
[ ] The Python middleware layer must possess absolute veto rights over the remaining queue. If an Immediate Environmental Interrupt or Reactive Action condition is met (e.g., monster.active_reactions: ["shield_cast"]), Python must pause the player's queue execution, finalize a partial Snapshot B, run the partial handshake diff, and force a prompt change back to the Discord channel before executing the player's remaining actions.