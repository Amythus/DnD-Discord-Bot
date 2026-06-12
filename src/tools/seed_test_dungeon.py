import asyncio
import sys
import os

# Append project root directory to path to ensure clean database package imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_database
from database.models.room import Room, Navigation, RoomExit, Environment, Encounters, StoryAndTriggers, RoomLLMContexts
from database.models.enums import ExitType, LightingLevel

async def seed_test_campaign():
    print("🔌 Connecting to database cluster...")
    # Initialize Beanie schemas locally
    db_success = await init_database()
    if not db_success:
        print("❌ Failed to bind to MongoDB instance.")
        return

    campaign_id = "test_dungeon"
    print(f"🧹 Purging old data entries for campaign layout blueprint: '{campaign_id}'...")
    await Room.find(Room.module_id == campaign_id).delete()

    print("🌱 Injecting sample rooms...")

    # Room 1: The Absolute Entrance Layer (Required naming string match: <campaign_id>_lvl1_room_01)
    room1 = Room(
        module_id=campaign_id,
        room_id=f"{campaign_id}_lvl1_room_01",
        title="Dungeon Entrance Antechamber",
        navigation=Navigation(
            map_layer="level_1",
            coordinates={"x": 0, "y": 0},
            exits={
                "north": RoomExit(target_room_id=f"{campaign_id}_lvl1_room_02", type=ExitType.OPEN_ARCHWAY)
            }
        ),
        environment=Environment(
            dimensions="20ft x 20ft, 10ft high flat stone ceiling",
            lighting=LightingLevel.DIM_LIGHT
        ),
        encounters=Encounters(combat_trigger_type="NONE"),
        story_and_triggers=StoryAndTriggers(),
        llm_contexts=RoomLLMContexts(
            read_aloud_text="You stand within a cold stone antechamber. Rain leaks through cracks in the ceiling, pooling around shattered limestone tiles. A singular gaping dark archway leads north into deeper shadows.",
            raw_parsed_markdown="## [CR-01] Dungeon Entrance Antechamber\nA damp 20x20 stone room. Leaks from the roof. Exit north via an open stone archway."
        )
    )

    # Room 2: The Haunted Hallway
    room2 = Room(
        module_id=campaign_id,
        room_id=f"{campaign_id}_lvl1_room_02",
        title="The Whispering Corridor",
        navigation=Navigation(
            map_layer="level_1",
            coordinates={"x": 0, "y": 1},
            exits={
                "south": RoomExit(target_room_id=f"{campaign_id}_lvl1_room_01", type=ExitType.OPEN_ARCHWAY),
                "east": RoomExit(target_room_id=f"{campaign_id}_lvl1_room_03", type=ExitType.WOODEN_DOOR, locked=True, lock_dc=12)
            }
        ),
        environment=Environment(
            dimensions="10ft wide hallway, extending 40ft north-to-south",
            lighting=LightingLevel.DARKNESS
        ),
        encounters=Encounters(combat_trigger_type="IMMEDIATE"),
        story_and_triggers=StoryAndTriggers(),
        llm_contexts=RoomLLMContexts(
            read_aloud_text="The air grows freezing cold as you step into a narrow corridor. Intricate, decaying murals of ancient battles cover the walls. To the east, a sturdy wooden door with an iron lock stands closed.",
            raw_parsed_markdown="## [CR-02] The Whispering Corridor\nLong narrow hallway. Pitch black. East exit features a locked wooden door (DC 12 Thieves Tools to pick)."
        )
    )

    # Room 3: The Crypt/Vault Room
    room3 = Room(
        module_id=campaign_id,
        room_id=f"{campaign_id}_lvl1_room_03",
        title="The Defiled Treasury",
        navigation=Navigation(
            map_layer="level_1",
            coordinates={"x": 1, "y": 1},
            exits={
                "west": RoomExit(target_room_id=f"{campaign_id}_lvl1_room_02", type=ExitType.WOODEN_DOOR)
            }
        ),
        environment=Environment(
            dimensions="30ft x 40ft chamber with supporting pillars",
            lighting=LightingLevel.DARKNESS
        ),
        encounters=Encounters(combat_trigger_type="NONE"),
        story_and_triggers=StoryAndTriggers(),
        llm_contexts=RoomLLMContexts(
            read_aloud_text="Shattered stone urns litter the floor of this ancient vault. In the center, a stone sarcophagus sits broken open, its treasures long stolen by graverobbers.",
            raw_parsed_markdown="## [CR-03] The Defiled Treasury\nA ransacked vault. Urns smashed. Contains a central broken sarcophagus."
        )
    )

    # Commit all three documents concurrently using Beanie ODM loops
    await room1.insert()
    await room2.insert()
    await room3.insert()
    print(f"✅ Injection complete! Created campaign database blueprint for id: '{campaign_id}'.")

if __name__ == "__main__":
    asyncio.run(seed_test_campaign())
