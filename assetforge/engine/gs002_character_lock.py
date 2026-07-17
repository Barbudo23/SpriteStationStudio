"""
AssetForge Engine
GS002 - Character Lock
Version 0.1
"""

from assetforge.core.state import AssetForgeState


class GS002CharacterLock:
    step_id = "GS002"
    name = "Character Lock"

    LOCKED_FIELDS = {
        "face": True,
        "hair": True,
        "helmet": True,
        "armor": True,
        "vest": True,
        "backpack": True,
        "weapon": True,
        "gloves": True,
        "boots": True,
        "body_proportions": True,
        "silhouette": True,
        "lighting": True,
        "color_palette": True,
        "scale": True,
    }

    def execute(self, state: AssetForgeState) -> AssetForgeState:

        state.current_step = self.step_id
        state.log("Creating immutable character profile.")

        state.metadata["character_lock"] = self.LOCKED_FIELDS.copy()

        state.metadata["character_profile"] = {
            "status": "LOCKED",
            "lock_count": len(self.LOCKED_FIELDS),
        }

        state.log(
            f"Locked {len(self.LOCKED_FIELDS)} character attributes."
        )

        state.approve()

        return state
