import logging
from google import genai
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

client = None

if settings.gemini_api_key:
    client = genai.Client(api_key=settings.gemini_api_key)


def generate_story(
    outline: list,
    character_name: str = "",
    tone: str = "",
) -> str:

    if not outline:
        return ""

    # Prepare each panel separately
    formatted_outline = "\n\n".join(
        [
            f"""PANEL {i + 1}
TITLE: {item.get("panel_title", item.get("title", ""))}
SCENE: {item.get("scene_description", "")}
"""
            for i, item in enumerate(outline)
        ]
    )

    prompt = f"""
You are an expert comic-book writer.

Create an INTERESTING and CINEMATIC 5-PANEL COMIC STORY.

Character:
{character_name}

Tone:
{tone}

Panel outline:
{formatted_outline}

IMPORTANT STORY RULES:

1. Write EXACTLY one narration and one dialogue for EACH panel.
2. Every panel must have DIFFERENT narration.
3. Every panel must have DIFFERENT dialogue.
4. NEVER repeat a narration.
5. NEVER repeat a dialogue.
6. Do NOT use generic repeated sentences like:
   "The adventure continues."
   "Something strange is happening."
   "What will happen next?"
7. The narration must describe the ACTION happening specifically in that panel.
8. Dialogue must react to the action in that panel.
9. Make the story feel like a real comic, not a description of the input.
10. Panel 1 must introduce the situation.
11. Panel 2 must reveal or develop the main mystery/problem.
12. Panel 3 must increase tension or create a surprise.
13. Panel 4 must contain the biggest/climax moment.
14. Panel 5 must provide a satisfying ending or reveal.
15. Keep the same character throughout.
16. Keep the same location unless the supplied outline explicitly changes it.
17. Do not invent unrelated characters or locations.
18. Narration should be short: maximum 15 words.
19. Dialogue should be short and natural: maximum 12 words.
20. Dialogue should sound like something the character would actually say.
21. Avoid repeating the character's name in every dialogue.
22. Make the story mysterious, exciting and visually interesting.
23. Do not create audio.
24. Do not create video.
25. Do not add explanations outside the panels.

Return ONLY this format:

Panel 1
Narration: ...
Dialogue: ...

Panel 2
Narration: ...
Dialogue: ...

Panel 3
Narration: ...
Dialogue: ...

Panel 4
Narration: ...
Dialogue: ...

Panel 5
Narration: ...
Dialogue: ...
"""

    try:
        if client is None:
            logger.warning("Gemini API key is missing.")
            return generate_fallback_story(
                outline,
                character_name,
            )

        response = client.models.generate_content(
            model=settings.gemini_story_model,
            contents=prompt,
        )

        text = response.text.strip()

        if text:
            return text

        logger.warning("Gemini returned empty story.")

    except Exception as exc:
        logger.warning(
            "Gemini story generation failed: %s",
            exc,
        )

    return generate_fallback_story(
        outline,
        character_name,
    )


def generate_fallback_story(
    outline: list,
    character_name: str,
) -> str:

    fallback = [
        (
            f"{character_name} notices something unusual hidden nearby.",
            "Wait... what is that?"
        ),
        (
            f"{character_name} discovers a strange object glowing in the darkness.",
            "I've never seen anything like this."
        ),
        (
            f"The mysterious object suddenly reacts to {character_name}'s touch.",
            "Whoa! It reacted to me!"
        ),
        (
            f"A powerful burst of energy reveals the secret behind the mystery.",
            "So this was waiting for me..."
        ),
        (
            f"{character_name} understands the mystery and begins a new adventure.",
            "I think this is only the beginning."
        ),
    ]

    result = []

    for i, _ in enumerate(outline):

        if i < len(fallback):
            narration, dialogue = fallback[i]
        else:
            narration = f"{character_name} continues the mysterious adventure."
            dialogue = "There's still more to discover."

        result.append(
            f"Panel {i + 1}\n"
            f"Narration: {narration}\n"
            f"Dialogue: {dialogue}"
        )

    return "\n\n".join(result)