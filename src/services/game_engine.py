import math
from typing import Dict, Any

class GameEngineService:
    """
    Handles pure, deterministic D&D 5e mathematics and rules evaluations.
    Maintains code logic for ability modifiers, passive scores, initiative calculation,
    and automated proficiency level recalculations.
    """

    @staticmethod
    def evaluate_active_buffs(vitals: Any, action_type: str) -> tuple[int, str]:
        """
        Sweeps the character's active buffs to find modifiers matching the current action.
        Returns a tuple of (total_buff_bonus, math_breakdown_string).
        """
        total_bonus = 0
        breakdown_parts = []
        
        # Action categories mapped from the Rule Check Model: "saving_throws", "attack_rolls", "skills"
        for buff in vitals.active_buffs:
            if action_type in buff.applies_to:
                # Handle dice parsing strings (like '1d4' for Bless)
                if buff.dice_modifier == "1d4":
                    roll = random.randint(1, 4)
                    total_bonus += roll
                    breakdown_parts.append(f"+ {roll} ({buff.buff_name} [1d4])")
                elif buff.dice_modifier == "1d6":
                    roll = random.randint(1, 6)
                    total_bonus += roll
                    breakdown_parts.append(f"+ {roll} ({buff.buff_name} [1d6])")
                    
        return total_bonus, " ".join(breakdown_parts)

    @staticmethod
    def calculate_modifier(ability_score: int) -> int:
        """
        Applies standard D&D 5e ability score modifier math.
        Formula: floor((score - 10) / 2)
        """
        return math.floor((ability_score - 10) / 2)

    @staticmethod
    def calculate_proficiency_bonus(level: int) -> int:
        """
        Calculates a character's core Proficiency Bonus based on their total level.
        Formula: 1 + ceil(level / 4)
        """
        return 1 + math.ceil(level / 4)

    @classmethod
    def compile_base_skills(cls, stats: Dict[str, int], proficiencies: Dict[str, int], level: int) -> Dict[str, int]:
        """
        Maps standard skill proficiencies to their governing base attributes and 
        returns the absolute final modifiers for the database cache sheets.
        
        Proficiency Tiers (proficiencies dict mapping):
        0 = No Proficiency
        1 = Standard Proficiency (Add flat proficiency bonus)
        2 = Expertise (Add 2x proficiency bonus)
        """
        prof_bonus = cls.calculate_proficiency_bonus(level)
        
        # Standard D&D 5e Skill to Attribute Governing Matrix
        skill_map = {
            "Acrobatics": "dexterity", "Sleight of Hand": "dexterity", "Stealth": "dexterity",
            "Athletics": "strength",
            "Arcana": "intelligence", "History": "intelligence", "Investigation": "intelligence", 
            "Nature": "intelligence", "Religion": "intelligence",
            "Animal Handling": "wisdom", "Insight": "wisdom", "Medicine": "wisdom", 
            "Perception": "wisdom", "Survival": "wisdom",
            "Deception": "charisma", "Intimidation": "charisma", "Performance": "charisma", 
            "Persuasion": "charisma"
        }
        
        compiled_skills = {}
        
        for skill, attribute in skill_map.items():
            # 1. Fetch baseline ability score modifier
            stat_score = stats.get(attribute, 10)
            base_mod = cls.calculate_modifier(stat_score)
            
            # 2. Extract explicitly trained tier flag
            prof_tier = proficiencies.get(skill, 0)
            
            # 3. Calculate scaling modifiers
            if prof_tier == 1:
                final_bonus = base_mod + prof_bonus
            elif prof_tier == 2:
                final_bonus = base_mod + (prof_bonus * 2)
            else:
                final_bonus = base_mod
                
            compiled_skills[skill] = final_bonus
            
        return compiled_skills

    @classmethod
    def process_level_up_delta(cls, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates a complete stat sheet recalculation matrix when a character levels up
        or when a fresh D&D Beyond baseline sheet is synced to an ongoing session.
        """
        stats = character_data.get("stats", {})
        prof_skills = character_data.get("proficiencies", {}).get("skills", {})
        current_level = character_data.get("level", 1)
        
        # Automatically update proficiency milestones
        new_prof_bonus = cls.calculate_proficiency_bonus(current_level)
        
        # Fully recalculate all skill modifier totals
        updated_base_skills = cls.compile_base_skills(
            stats=stats,
            proficiencies=prof_skills,
            level=current_level
        )
        
        # Calculate dynamic combat bonuses
        dex_score = stats.get("dexterity", 10)
        dex_mod = cls.calculate_modifier(dex_score)
        
        return {
            "level": current_level,
            "proficiency_bonus": new_prof_bonus,
            "base_skills": updated_base_skills,
            "initiative_bonus": dex_mod # Base initiative scales off Dex mod
        }

# Instantiate global service instance
game_engine = GameEngineService()
