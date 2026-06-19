# This document acts as the active engineering backlog and flight checklist for the bot's core systems. 
Progression follows a strict Red 🔴 -> Green 🟢 -> Refactor 🔵 Test-Driven Development paradigm.

## TDD State Key
🔴 Red: Test suite written and failing as expected (or work not started).
🟢 Green: Implementation passing all assertions.
🔵 Refactor: Code clean, optimized, patterns unified; tests remain green.

## Database and Discord Handshake
[x] 🟢 Test Case [Database Initialization]: Assert that the database connection is established and the collections are created successfully.
[x] 🟢 Test Case [Discord Bot Initialization]: Bot connects to discord and responds to a ping command.

## Ingestion Engine
Character sheets should be ingested from D&D Beyond and stored in the database. Campaigns/Adventures should be ingested from 5e tools and stored in the database. 

[] 🔴 Test Case [Character Ingestion]: Assert that a character can be ingested from D&D Beyond and stored in the database.
[] 🔴 Test Case [Campaign Ingestion]: Assert that the campaign can be ingested from 5e tools markdown file and json bestiary
    [] 🔴 Test Case [Campaign Ingestion]: Assert that the ingested campaign markdown file populates the Campaign Nodes with all relevant fields: campaign_id, room descriptions, etc.
    [] 🔴 Test Case [Campaign Ingestion]: Assert that the ingested monster list json file populated campaign specific monsters into the Monster collection database.

## Seeding Database
[] 🔴 Test Case [Seed Data]: Assert that the markdown files provided can be parsed and inserted into database
    [] 🔴 PHB: Players Handbook 2024
    [] 🔴 DMG: Dungeon Masters Guide 2024
    [] 🔴 MM: Monster Manual 2024
    [] 🔴 XGE: Xanathar's Guide to Everything 2024 (Optional)
    [] 🔴 TCE: Tasha's Cauldron of Everything 2024 (Optional)
    [] 🔴 VGtM: Volo's Guide to Monsters 2024 (Optional)
    [] 🔴 MToF: Mordenkainen's Tome of Foes 2024 (Optional)
[] 🔴 Test Case [Seed Data]: Assert that base DnD bestiary is populated into the Monster collection database
    [] 🔴 MM: Monster Manual 2025
    [] 🔴 VGtM: Volo's Guide to Monsters 2025
    [] 🔴 MToF: Mordenkainen's Tome of Foes 2025

## Database Schema
[] 🔴 Test Case [Database Schema]: Assert that the database schema is valid and can be created without errors
    [] 🔴 📜 Monster
    [] 🔴 📜 Character
    [] 🔴 📜 Global State Tracker

## 📦 Discord Bot
[] 🔴 Test Case [Discord Bot]: Assert that the Discord bot is running and can be interacted with
    [] 🔴 Discord Cogs to compartmentalize @commands, /commands, and event listeners

## 🗺️ Spatial Routing Engine (Node Matrix)
The read-only, in-memory Directed Graph representing world spaces, POIs, and rooms.

[ ] 🔴 Test Case [Matrix Initialization]: Assert that seed_matrix.json/yaml parses perfectly into a strongly typed graph structure using Pydantic, failing if any node lacks required fields (node_id, node_type, connections).
[ ] 🔴 Test Case [Orphan Connection Validation]: Assert that a validation exception is thrown during startup if any edge destination identifier (connection_id) points to a node_id that does not exist in the matrix.
[ ] 🔴 Test Case [Room Transition Logic]: Given a player at node U5 (Room), assert that attempting to query adjacent nodes returns U6 if a directional edge exists, and throws an InvalidMovementException if a move is attempted to an unconnected node.
[ ] 🔴 Test Case [Overworld Intersection Mapping]: Assert that the engine correctly identifies a target node type as OVERWORLD when intersecting specific edge thresholds, allowing downstream forks to intercept the execution thread.

## 🧠 Session Delta Engine (Working Memory Buffer)
The volatile high-speed cache caching active session states to protect persistent layers from intensive I/O operations.

[ ] 🔴 Test Case [Layered Context Construction]: Assert that querying a character's state correctly builds a unified temporary view by overriding the base data layer (GlobalTracker) and spatial layer (Node Matrix) with the overlay variables stored in the active SessionDelta.
[ ] 🔴 Test Case [Delta Mutation Accumulation]: Assert that applying sequential modifications (e.g., taking 3 damage, then gaining 10 gold) updates the local SessionDelta attributes correctly without committing any premature writes to the persistent MongoDB character documents.
[ ] 🔴 Test Case [Relative Update Generation]: Assert that compiling the delta state for persistent flushing generates explicit MongoDB atomic relative operators (e.g., {"$inc": {"hp": -3}}) rather than a whole-document replacement object.
[ ] 🔴 Test Case [Node Matrix Drift Validation]: Assert that invoking /resume_session with a frozen/suspended session delta validates the cached location_override ID against the active Node Matrix, throwing a descriptive structural mismatch exception if the map graph shifted during the downtime.

## 🔒 Concurrency Lock Manager
The state protection matrix preventing multi-event state corruption at the individual guild_id boundary.

[ ] 🔴 Test Case [Acquire Execution Lock]: Assert that when a command transaction initiates, is_processing_transaction flags as True for that specific guild_id, and any subsequent rapid-fire inputs from the same server are instantly and gracefully rejected or deferred.
[ ] 🔴 Test Case [Command Lock Isolation]: Assert that holding an active transaction lock on Server Alpha (guild_id: 111) does not block, delay, or impact concurrent command execution flows originating from Server Beta (guild_id: 222).
[ ] 🔴 Test Case [Asynchronous Lock Releasing]: Assert that the termination of an execution pipeline successfully reverts is_processing_transaction back to False, unblocking the text input parsing channel for the server.
[ ] 🔴 Test Case [Lock Timeout Boundary]: Assert that if a complex command evaluation thread hangs or errors out internally, a background circuit breaker forces a release of the lock after a strict 3000ms threshold to prevent server-wide command paralysis.

## ⚔️ Interaction Engine & Staged Actions
The asynchronous UI component system handling buttons, modal responses, timeouts, and multi-click race conditions.

[ ] 🔴 Test Case [Staged Action Registration]: Assert that initiating a rolling prompt or choice populates the StagedAction properties inside the active SessionDelta, complete with its specific callback payload and a dynamic UTC expiration timestamp.
[ ] 🔴 Test Case [Atomic Deletion Protection]: Assert that when an interaction occurs (or a background expiration worker fires), the thread executes an atomic find_one_and_delete logic on the sub-document. Verify that the winner handles execution rights, while the losing thread receives None and exits cleanly.
[ ] 🔴 Test Case [Automated Timeout Execution]: Mock an elapsed timeout clock and assert that a background cron/worker thread automatically identifies expired StagedAction entities, clears them out atomically, and pushes a "Time Expired" alert to the targeted Discord channel.
[ ] 🔴 Test Case [Intent Parser Constraints]: Assert that the Intent Parser / Lock Manager throws an immediate user exception ("You have an action pending!") if a player types a new text command while an unresolved StagedAction button prompt is counting down in their session cache.

## 🗳️ Overworld Voting Engine
The asynchronous multi-user voting apparatus controlling safe macro-travel across points of interest.

[ ] 🔴 Test Case [Overworld Travel Interception]: Assert that when a movement intent resolves to an OVERWORLD node type, the movement engine halts immediate displacement and routes the request into a new vote ledger inside the SessionDelta.
[ ] 🔴 Test Case [Immediate Lock Release]: Assert that initializing an overworld travel vote releases the server's is_processing_transaction lock immediately, verifying that players can continue text chat and interact with other bot components while the poll is active.
[ ] 🔴 Test Case [Vote Accumulation & Duplication Prevention]: Assert that a player can submit a vote to the active ledger, changing their choice iteratively, but cannot inject multiple parallel votes into the tally array.
[ ] 🔴 Test Case [Majority Resolution Flow]: Given a party of 4, assert that when a 3rd vote matching the destination threshold is recorded, the engine instantly resolves the ledger, flushes the new location_override to the delta, and posts a travel-start embed.

## 🤖 LLM Context Cache Layer
The rules adjudication component managing markdown data compaction and context caching anchors.

[ ] 🔴 Test Case [Rulebook Concatenation Ordering]: Assert that running the rule ingestion pipeline retrieves individual chapters from MongoDB, sorts them perfectly by their hierarchical index, and builds a single unified, unfragmented text string (phb_text / dmg_text).
[ ] 🔴 Test Case [Markdown Metadata Injection]: Assert that deep sub-headings lacking explicit parent context (e.g., ### Actions) are successfully caught by the processing script and prefixed into normalized structural headers (e.g., ### Combat: Actions) before transit.
[ ] 🔴 Test Case [Context Cache Refresh Validation]: Assert that on bot boot-up, the systems perform a handshake with the Gemini Caching API to verify token validation hashes, catching expirations and re-binding the master rules strings cleanly if a cache miss occurs.