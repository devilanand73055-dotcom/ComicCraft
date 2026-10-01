import json
import logging
from pathlib import Path
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from PIL import Image

from app.config import settings
from app.gemini_flash import get_fallback_panels
from app.image_generator import (
    generate_fallback_image,
    generate_image,
    get_file_sha256,
    is_usable_image,
)
from app.layout_builder import build_comic_layout
from app.exporters import save_pdf

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=str(settings.templates_dir))


def get_valid_panel_image_path(image_url):
    if not isinstance(image_url, str) or not image_url.startswith("/static/panels/"):
        return None
    filename = Path(image_url).name
    if not filename or filename in {".", ".."}:
        return None
    image_path = settings.static_dir / "panels" / filename
    try:
        if not image_path.is_file() or image_path.stat().st_size <= 5000:
            return None
        with Image.open(image_path) as image:
            if image.format not in {"PNG", "JPEG"}:
                return None
            image.load()
            if not is_usable_image(image):
                return None
    except Exception:
        return None
    return image_path


def validate_panel_images(panels):
    if len(panels) != 5:
        raise ValueError(f"Expected exactly five comic panels, got {len(panels)}")
    expected_numbers = [1, 2, 3, 4, 5]
    panel_numbers = [panel.get("panel_number") for panel in panels]
    if panel_numbers != expected_numbers:
        raise ValueError(f"Comic panels must be numbered 1 through 5, got {panel_numbers}")
    image_urls = [panel.get("image_url") for panel in panels]
    if any(not url for url in image_urls) or len(set(image_urls)) != 5:
        raise ValueError("Each comic panel must have a unique, non-empty image URL")
    for panel in panels:
        if get_valid_panel_image_path(panel["image_url"]) is None:
            raise ValueError(
                f"Panel {panel['panel_number']} has no valid, saved image"
            )


def render_template(template_name: str, context: dict):
    # Compatible with both old and new FastAPI/Starlette versions
    try:
        return templates.TemplateResponse(request=context["request"], name=template_name, context=context)
    except TypeError:
        return templates.TemplateResponse(template_name, context)


def prepare_panels(raw_outline, idea, character, location, tone, art_style):
    if isinstance(raw_outline, str):
        try:
            raw_outline = json.loads(raw_outline)
        except (TypeError, ValueError):
            raw_outline = None

    if not (
        isinstance(raw_outline, list)
        and len(raw_outline) == 5
        and all(isinstance(panel, dict) for panel in raw_outline)
    ):
        raw_outline = get_fallback_panels(
            idea, character, location, tone, art_style
        )

    fallback_panels = get_fallback_panels(
        idea, character, location, tone, art_style
    )
    stages = ["Beginning", "Development", "Turning Point", "Climax", "Ending"]
    shared_appearance = (
        "Arjun, a college student with an oval face, short black hair, warm brown skin, large brown eyes, clear brows, "
        "and a consistent cartoon body. He wears the same blue hoodie, dark jeans, and black backpack in every panel, "
        "with matching face shape, black hairstyle, brown eyes, blue hoodie, dark denim, backpack, and body proportions."
    )

    panels = []
    for index, (panel, fallback, stage) in enumerate(
        zip(raw_outline, fallback_panels, stages), start=1
    ):
        visual = str(
            panel.get("visual") or panel.get("scene_description") or fallback["visual"]
        ).strip()
        character_action = str(
            panel.get("character_action") or visual or fallback["character_action"]
        ).strip()
        background = str(panel.get("background") or fallback["background"]).strip()
        facial_expression = str(
            panel.get("facial_expression") or fallback["facial_expression"]
        ).strip()
        camera_angle = str(
            panel.get("camera_angle") or fallback["camera_angle"]
        ).strip()
        composition = str(
            panel.get("composition") or fallback["composition"]
        ).strip()
        lighting = str(panel.get("lighting") or fallback["lighting"]).strip()
        important_objects = str(
            panel.get("important_objects") or fallback["important_objects"]
        ).strip()
        mood = str(panel.get("mood") or tone).strip()
        characters_present = str(
            panel.get("characters_present") or panel.get("characters") or character
        ).strip()
        dialogues = panel.get("dialogues") or fallback["dialogues"]
        if not isinstance(dialogues, (list, tuple)):
            dialogues = [str(dialogues)]
        dialogues = [str(line).strip() for line in dialogues if str(line).strip()]
        dialogue = "\n".join(dialogues)
        narration = str(panel.get("narration") or fallback["narration"]).strip()
        image_prompt = (
            f"Panel {index} of 5. Polished 2D cartoon comic-book style. {shared_appearance} "
            f"Story: {visual}. Action: {character_action}. Expression: {facial_expression}. "
            f"Composition: {composition}. Background: {background}. "
            "Kavin has short curly black hair and a green shirt whenever shown. "
            "Use bold clean ink outlines, expressive faces, colorful natural school-life comic-book colors, "
            "detailed understandable backgrounds, and consistent character design. "
            "All named speakers are visibly speaking with expressive open mouths. "
            "Keep characters and important props in the middle and lower area; reserve the top quarter "
            "for speech balloons and a bottom strip for narration if needed. Do not generate any lettering: "
            "the exact dialogue and narration will be typeset clearly into the finished artwork. "
            "No random text, signs, logos, watermarks, or photorealism."
        )
        panels.append(
            {
                "panel_number": index,
                "stage": stage,
                "panel_title": str(panel.get("panel_title") or stage).strip(),
                "visual": visual,
                "scene_description": str(panel.get("scene_description") or visual).strip(),
                "character_action": character_action,
                "background": background,
                "character_appearance": shared_appearance,
                "characters_present": characters_present,
                "facial_expression": facial_expression,
                "camera_angle": camera_angle,
                "composition": composition,
                "lighting": lighting,
                "important_objects": important_objects,
                "mood": mood,
                "dialogues": dialogues,
                "dialogue": dialogue,
                "narration": narration,
                "sound_effect": str(panel.get("sound_effect") or "").strip(),
                "image_prompt": image_prompt,
            }
        )
    return panels

@router.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return render_template("index.html", {"request": request})

@router.get("/generate")
async def redirect_generate():
    return RedirectResponse(url="/")

@router.get("/download/{filename}")
async def download_comic_pdf(filename: str):
    if Path(filename).name != filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=404, detail="PDF not found")
    pdf_path = settings.static_dir / "exports" / filename
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="PDF not found")
    with pdf_path.open("rb") as pdf_file:
        if pdf_file.read(5) != b"%PDF-":
            raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="comiccraft_comic.pdf",
    )

@router.post("/comic", response_class=HTMLResponse)
@router.post("/generate", response_class=HTMLResponse)
async def create_comic(
    request: Request,
    idea: str = Form(...),
    character: str = Form("Hero"),
    location: str = Form("City"),
    tone: str = Form("Action"),
    art_style: str = Form("Comic Book")
):
    try:
        safe_panels = prepare_panels(
            None, idea, character, location, tone, art_style
        )

        images = []
        failed_panel_numbers = []
        for panel in safe_panels:
            panel_number = panel["panel_number"]
            logger.info("PANEL %s PROMPT: %s", panel_number, panel["image_prompt"])
            try:
                img_url = generate_image(
                    prompt=panel["image_prompt"],
                    panel_number=panel_number,
                    dialogue=panel["dialogue"],
                    narration=panel["narration"],
                )
            except Exception:
                logger.exception(
                    "Image generation failed for panel %s; continuing",
                    panel_number,
                )
                img_url = None

            local_image_path = get_valid_panel_image_path(img_url)
            fallback_attempt = 0
            while (
                local_image_path is None or img_url in images
            ) and fallback_attempt < 2:
                fallback_attempt += 1
                try:
                    img_url = generate_fallback_image(
                        panel["image_prompt"],
                        panel_number,
                        dialogue=panel["dialogue"],
                        narration=panel["narration"],
                    )
                    local_image_path = get_valid_panel_image_path(img_url)
                    if img_url in images:
                        local_image_path = None
                except Exception:
                    logger.exception(
                        "Fallback artwork attempt %s failed for panel %s",
                        fallback_attempt,
                        panel_number,
                    )
                    img_url = None

            if local_image_path is None or img_url in images:
                failed_panel_numbers.append(panel_number)
            else:
                panel["image_url"] = img_url
                images.append(img_url)
            logger.info("PANEL %s URL: %s | FILE: %s", panel_number, img_url, local_image_path)
            if local_image_path is not None:
                logger.info(
                    "PANEL %s FILE SIZE: %s | HASH: %s",
                    panel_number,
                    local_image_path.stat().st_size,
                    get_file_sha256(local_image_path),
                )

        if failed_panel_numbers:
            raise RuntimeError(
                "Could not create valid artwork for panels: "
                + ", ".join(str(number) for number in failed_panel_numbers)
            )

        validate_panel_images(safe_panels)
        layout = build_comic_layout(safe_panels, idea, images)
        validate_panel_images(layout["panels"])
        pdf_path = save_pdf(layout, title=idea)
        pdf_url = f"/download/{Path(pdf_path).name}"
        return render_template("comic_preview.html", {
            "request": request,
            "layout": layout,
            "pdf_url": pdf_url,
        })

    except Exception as e:
        return render_template("index.html", {"request": request, "error": str(e)})