def build_comic_layout(outline, story, images):
    panels = []
    for i, panel in enumerate(outline):
        image_url = panel.get("image_url") or (images[i] if i < len(images) else "")
        if not isinstance(image_url, str) or not image_url.startswith("/static/panels/"):
            raise ValueError(f"Panel {i + 1} must use a local static panel image")
        image_path = image_url.lstrip("/")
        panel_data = {
            "panel_number": panel.get("panel_number", i + 1),
            "stage": panel.get("stage", ""),
            "panel_title": panel.get("panel_title", f"Panel {i + 1}"),
            "visual": panel.get("visual", panel.get("scene_description", "")),
            "scene_description": panel.get("scene_description", ""),
            "character_action": panel.get("character_action", ""),
            "background": panel.get("background", ""),
            "character_appearance": panel.get("character_appearance", ""),
            "characters_present": panel.get("characters_present", ""),
            "facial_expression": panel.get("facial_expression", ""),
            "camera_angle": panel.get("camera_angle", ""),
            "composition": panel.get("composition", ""),
            "lighting": panel.get("lighting", ""),
            "important_objects": panel.get("important_objects", ""),
            "mood": panel.get("mood", ""),
            "dialogue": panel.get("dialogue", ""),
            "narration": panel.get("narration", ""),
            "sound_effect": panel.get("sound_effect", ""),
            "image_prompt": panel.get("image_prompt", ""),
            "image_url": image_url,
            "image_path": image_path,
        }
        panels.append(panel_data)

    return {
        "story": story,
        "panels": panels
    }