"""Provider-facing grounding for current headless AVATAR presentation."""
from __future__ import annotations

import json

from .presentation import AttireMode, PresentationProjection


def presentation_prompt(projection: PresentationProjection) -> str:
    if not isinstance(projection, PresentationProjection):
        raise TypeError("PresentationProjection is required")
    data = {
        "audience": projection.audience.value,
        "source_revision": projection.source_revision,
        "attire": projection.attire.value,
        "outfit_id": projection.outfit_id,
        "item_ids": projection.item_ids,
        "hairstyle": projection.appearance.hairstyle,
        "hair_color": projection.appearance.hair_color,
        "tail_color": projection.appearance.tail_color,
        "style_tags": projection.appearance.style_tags,
        "private_fallback_used": projection.private_fallback_used,
        "reason": projection.reason,
    }
    rules = [
        "CURRENT AVATAR PRESENTATION (trusted AVATAR projection)",
        "This is the authoritative current presentation for the supplied audience.",
        "Use it when the user asks what Sofía is wearing or how she currently looks.",
        "It overrides static canonical clothing design as a CURRENT-WEAR fact; the canonical design remains an available wardrobe baseline.",
        "Do not claim a renderer displayed this state unless separate renderer evidence says so.",
        "Representational appearance is not biological or physical-world execution.",
        "Do not reveal or infer a private presentation from public fallback data.",
    ]
    if projection.attire is AttireMode.NUDE:
        rules.append(
            "The trusted private projection says attire is nude. Describe that fact only when directly relevant; do not sexualize it or infer consent, attraction, desire, arousal, or permission."
        )
    rules.append(json.dumps(data, ensure_ascii=False, sort_keys=True))
    return "\n".join(rules)
