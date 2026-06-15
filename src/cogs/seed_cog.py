import os
import re
import json
import aiohttp
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from google import genai
from google.genai import types
from pydantic import BaseModel
from beanie import WriteRules
from beanie.odm.operators.update.general import Set
# Import core system helper utilities and Beanie document schemas
from services.template_service import prompt_service
from database.models.ingestion import CharacterSheetIngestionSchema
from database.models.character import CharacterSheet
from database.models.room import Room, Navigation, RoomExit, Environment, Encounters, StoryAndTriggers, RoomLLMContexts
from database.connection import init_database
from database.models.enums import ExitType, LightingLevel

class TestSeedDBCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def perform_seeding(self):
        # Move your seeding logic here
        print("🔌 Connecting to database cluster...")
        # Initialize Beanie schemas locally
        db_success = await init_database()
        if not db_success:
            print("❌ Failed to bind to MongoDB instance.")
            return

        campaign_id = "test_dungeon"

        # =========================================================================
        # PHASE 1: SEED MONSTER MANUAL REGISTRY (Immutable Blueprint)
        # =========================================================================
        print("🧹 Purging old monster manual registry blueprints for 'goblin_sentry'...")
        await Monster.find(Monster.monster_id == "goblin_sentry").delete()

        print("🌱 Injecting immutable Goblin Blueprint into Centralized Manual...")
        goblin_blueprint = Monster(
            monster_id="goblin_sentry",
            name="Goblin Sentry",
            source_book="D&D 2024 Monster Manual",
            meta=MonsterMeta(size=CreatureSize.SMALL, type="Humanoid", alignment="Neutral Evil", challenge_rating=0.25, xp_value=50),
            attributes=Attributes(
                str=AttributeScore(score=8, modifier=-1),
                dex=AttributeScore(score=14, modifier=2),
                con=AttributeScore(score=10, modifier=0),
                int=AttributeScore(score=10, modifier=0),
                wis=AttributeScore(score=8, modifier=-1),
                cha=AttributeScore(score=8, modifier=-1)
            ),
            defenses=Defenses(
                armor_class=15, armor_type="Leather Armor, Shield",
                hit_points=HitPoints(average=7, hit_dice_formula="2d6")
            ),
            mobility_and_senses=MobilityAndSenses(speed={"walk": 30}, darkvision_ft=60, passive_perception=9),
            actions=[
                MonsterAction(
                    name="Scimitar strike", type=AttackType.MELEE_ATTACK, hit_modifier=4,
                    range_ft=5, targets="One creature", damage_formula="1d6+2", damage_type="Slashing"
                )
            ],
            llm_contexts=LLMContexts(
                narrative_description="A small, green-skinned humanoid with beady black eyes and sharp yellowed fangs.",
                rules_engine_markdown="Small humanoid. Prefers hiding behind cover using Nimble Escape mechanics."
            )
        )
        await goblin_blueprint.insert()

        print("🌱 Injecting sample rooms...")

        # =========================================================================
        # PHASE 2: SEED DYNAMIC ADVENTURE GRAPH NODES (Mutable Behavior State Machines)
        # =========================================================================
        print(f"🧹 Purging old map configurations for campaign graph: '{campaign_id}'...")
        await Node.find(Node.parent_node_id == campaign_id).delete()
        # Also delete any master node references labeled as the campaign ID itself
        await Node.find(Node.node_id == f"{campaign_id}_lvl1_room_01").delete()
        await Node.find(Node.node_id == f"{campaign_id}_lvl1_room_02").delete()
        await Node.find(Node.node_id == f"{campaign_id}_lvl1_room_03").delete()
        await Node.find(Node.node_id == f"{campaign_id}_lvl1_room_vault").delete()

        print("🌱 Injecting Theatre of the Mind World Nodes...")

        # -------------------------------------------------------------------------
        # ROOM 1: THE ANTECHAMBER (Contains the Spike Trap)
        # -------------------------------------------------------------------------
        room1 = Node(
            node_id=f"{campaign_id}_lvl1_room_01",
            parent_node_id=campaign_id,
            node_type="INTERIOR_ROOM",
            title="Dungeon Entrance Antechamber",
            navigation=Navigation(
                map_layer="level_1",
                exits=[
                    ExitNode(direction="north", type=ExitType.OPEN_ARCHWAY, is_open=True, target_node_id=f"{campaign_id}_lvl1_room_02")
                ]
            ),
            environment={
                "dimensions": "20ft x 20ft damp room", "lighting": "DIM_LIGHT", "resting_safety": "UNSAFE"
            },
            sensory_profile=SensoryProfile(ambient_sound="Dripping water", olfactory_clue="Damp stone"),
            node_metadata=NodeMetadata(
                room_states={
                    "spike_trap_triggered": False
                },
                behavior_triggers=[
                    BehaviorTrigger(
                        trigger_type="player_action",
                        condition="inspect_false_door",
                        action_required="trigger_spike_trap",
                        instruction_to_narrator="As you touch the brass handles of the false wooden door on the wall, a mechanism clicks! "
                                                "A spring-loaded spike shoots outward! Everyone must make a DC 12 Dexterity Saving Throw "
                                                "to jump clear, or take 1d4 piercing damage as the spike grazes your flesh!"
                    )
                ]
            ),
            skill_checks=[
                SkillCheck(
                    skill="perception", dc=12, target_type="ENVIRONMENT",
                    success_outcome="You spot a small hidden seam in the stonework revealing the north exit archway.",
                    failure_outcome="You stumble blindly in the dark antechamber."
                )
            ],
            llm_contexts={
                "read_aloud_text": "You step into a dark, damp limestone antechamber. To your left stands what looks like a heavy wooden door. Ahead, a faint draft blows from a dark shadow along the north wall."
            }
        )

        # -------------------------------------------------------------------------
        # ROOM 2: THE HALLWAY OF REFLECTION (Contains the Hidden Gold Ring)
        # -------------------------------------------------------------------------
        room2 = Node(
            node_id=f"{campaign_id}_lvl1_room_02",
            parent_node_id=campaign_id,
            node_type="INTERIOR_ROOM",
            title="The Whispering Corridor",
            navigation=Navigation(
                map_layer="level_1",
                exits=[
                    ExitNode(direction="south", type=ExitType.OPEN_ARCHWAY, is_open=True, target_node_id=f"{campaign_id}_lvl1_room_01"),
                    ExitNode(direction="east", type=ExitType.IRON_DOOR, is_open=False, is_locked=True, lock_dc=99, target_node_id=f"{campaign_id}_lvl1_room_03") # Lock DC 99 means unpickable without the key!
                ]
            ),
            environment={
                "dimensions": "10ft wide, 40ft long hallway", "lighting": "DARKNESS", "resting_safety": "UNSAFE"
            },
            sensory_profile=SensoryProfile(olfactory_clue="Dust and decay"),
            node_metadata=NodeMetadata(
                room_states={
                    "has_ring_been_found": False
                },
                behavior_triggers=[
                    BehaviorTrigger(
                        trigger_type="player_action",
                        condition="use_goblin_key",
                        action_required="unlock_east_door",
                        instruction_to_narrator="You slide the rusted iron key recovered from the goblin into the heavy iron door lock. "
                                                "With a loud grinding sound of gears shifting, the lock turns, and the heavy door swings open to the East!"
                    )
                ]
            ),
            skill_checks=[
                SkillCheck(
                    skill="investigation", dc=12, target_type="ENVIRONMENT",
                    success_outcome="Sifting through the floor debris, your fingers brush against metal. You unearth a beautiful Golden Ring worth 20 GP hidden under the dust!",
                    failure_outcome="You search the rubble but find nothing but ancient dirt and broken shale."
                )
            ],
            llm_contexts={
                "read_aloud_text": "This long, narrow hallway is choked with dust. To the East stands a massive, imposing Iron Door etched with crude tribal symbols, locked shut tight."
            }
        )

        # -------------------------------------------------------------------------
        # ROOM 3: THE BARRACKS (Contains the Ambush Goblin holding the Key)
        # -------------------------------------------------------------------------
        room3 = Node(
            node_id=f"{campaign_id}_lvl1_room_03",
            parent_node_id=campaign_id,
            node_type="INTERIOR_ROOM",
            title="The Ruined Barracks",
            navigation=Navigation(
                map_layer="level_1",
                exits=[
                    ExitNode(direction="west", type=ExitType.IRON_DOOR, is_open=True, target_node_id=f"{campaign_id}_lvl1_room_02"),
                    ExitNode(direction="north", type=ExitType.WOODEN_DOOR, is_open=False, is_locked=True, lock_dc=99, target_node_id=f"{campaign_id}_lvl1_room_vault")
                ]
            ),
            environment={
                "dimensions": "30ft x 30ft messy chamber", "lighting": "DIM_LIGHT", "resting_safety": "DANGEROUS"
            },
            sensory_profile=SensoryProfile(ambient_sound="Faint scuffling noises", olfactory_clue="Roasting meat"),
            node_metadata=NodeMetadata(
                room_states={
                    "ambush_sprung": False,
                    "goblin_has_key": True
                },
                behavior_triggers=[
                    BehaviorTrigger(
                        trigger_type="player_action",
                        condition="enter_barracks",
                        action_required="spring_goblin_ambush",
                        instruction_to_narrator="The second you cross the threshold, a green creature screeches in malice! ""A Goblin Sentry jumps out from behind a pile of rotten cots, its scimitar drawn! ""Roll Initiative immediately!"),
                    BehaviorTrigger(
                        trigger_type="death_event",
                        condition="goblin_sentry_1_dead",
                        action_required="drop_goblin_key",
                        instruction_to_narrator="The Goblin Sentry collapses to the blood-stained tiles. As its body goes limp, ""a heavy, cruderly carved copper key clatters out of its loincloth onto the stone floor. This must be the Goblin Key!"),
                    BehaviorTrigger(
                        trigger_type="player_action",
                        condition="unlock_treasure_vault",
                        action_required="open_vault_door",
                        nstruction_to_narrator="You use the Goblin Key on the north wooden door. It clicks softly and creaks open, ""revealing the tiny hidden treasure vault of the complex!"
                    )
                ]
            ),
            encounters=[
                EncounterInstance(creature_id="goblin_sentry", quantity=1, initial_placement="Behind broken cots", combat_trigger_type="IMMEDIATE")
            ],
            llm_contexts={
                "read_aloud_text": "Overturned tables and rotten sleeping cots litter this square room. A small cooking fire smolders in the corner. Along the north wall stands a simple wooden door."
            }
        )    
        
        # -------------------------------------------------------------------------# ROOM 4: THE VAULT (The End of the Dungeon Stash)# -------------------------------------------------------------------------
        room_vault = Node(
            node_id=f"{campaign_id}_lvl1_room_vault",
            parent_node_id=campaign_id,
            node_type="INTERIOR_ROOM",
            title="The Secret Stash",
            navigation=Navigation(
                map_layer="level_1",
                exits=[
                    ExitNode(direction="south", type=ExitType.WOODEN_DOOR, is_open=True, target_node_id=f"{campaign_id}_lvl1_room_03")
                ]
            ),
            environment={
                "dimensions": "10ft x 10ft small vault", "lighting": "BRIGHT_LIGHT", "resting_safety": "SAFE_HAVEN"
            },
            sensory_profile=SensoryProfile(
                ambient_sound="Absolute silence"
            ),
            node_metadata=NodeMetadata(
                room_states={"campaign_ended": True},
                behavior_triggers=[
                    BehaviorTrigger(
                        trigger_type="player_action",
                        condition="open_vault_chest",
                        action_required="end_dungeon_run",
                        instruction_to_narrator="You lift the heavy lid of the iron-bound chest. Sitting inside is a massive mound of shimmering coins! "
                        "You have successfully navigated the dungeon and recovered the goblin hoard of 50 Gold Pieces! "
                        "Your quest is complete!"
                        )
                    ]
            ),
            treasure=Treasure(
                gold_value=50,items=[
                    TreasureItem(item_id="goblin_hoard_gold", quantity=1, associated_object_id="vault_chest")
                ]
            ),
            rewards=Rewards(combat_xp=50, story_milestone_xp=100),
            llm_contexts={
                "read_aloud_text": "This small, clean alcove contains a singular, heavily pristine iron-bound treasure chest sitting atop a velvet-covered stone pedestal."
            }
        )

        # Execute concurrent upserts to prevent duplicate records
        await room1.insert()
        await room2.insert()
        await room3.insert()
        await room_vault.insert()
        print(f"✅ Seeding Complete! Successfully loaded test dungeon for campaign ID: '{campaign_id}'.")
        pass

    @app_commands.command(name="seed_db_test", description="Seed the database with test data")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only
    async def seed_db_room_test(self, interaction: discord.Interaction):
        await self.perform_seeding()
        await interaction.response.send_message("Database seeded!")

async def setup(bot):
    await bot.add_cog(TestSeedDBCog(bot))