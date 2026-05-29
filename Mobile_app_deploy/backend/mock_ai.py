import asyncio
import random

DAMAGE_TYPES = ["Burnt", "Bent Pin", "Missing Pad", "Corrosion"]


async def simulate_yolo(image_path: str) -> list[dict]:
    await asyncio.sleep(1)

    return [
        {"label": "IC", "x_coord": 320, "y_coord": 240, "width": 140, "height": 90},
        {"label": "Capacitor", "x_coord": 640, "y_coord": 300, "width": 80, "height": 60},
        {"label": "Resistor", "x_coord": 520, "y_coord": 520, "width": 110, "height": 40},
        {"label": "Connector", "x_coord": 820, "y_coord": 420, "width": 160, "height": 70},
    ]


def simulate_mobilenet(component_list: list[dict]) -> list[dict]:
    updated = []
    for component in component_list:
        is_defective = random.choice([True, False, False])
        damage_type = random.choice(DAMAGE_TYPES) if is_defective else None

        item = dict(component)
        item["is_defective"] = is_defective
        item["damage_type"] = damage_type
        updated.append(item)

    return updated
