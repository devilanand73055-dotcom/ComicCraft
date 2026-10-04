import re
import urllib.parse
import random
import logging
import hashlib
import requests
import uuid
from io import BytesIO
from pathlib import Path
from PIL import Image
from PIL import ImageDraw
from PIL import ImageStat
from huggingface_hub import InferenceClient

from app.config import settings
from app.lettering import apply_comic_lettering

logger = logging.getLogger(__name__)

def is_usable_image(image: Image.Image) -> bool:
    if image.width < 64 or image.height < 64:
        return False
    variance = ImageStat.Stat(image.convert("RGB")).var
    return sum(variance) / len(variance) > 12


def is_valid_image_file(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size <= 5000:
            return False
        with Image.open(path) as image:
            if image.format not in {"PNG", "JPEG"}:
                return False
            image.load()
            return is_usable_image(image)
    except Exception:
        return False


def sanitize_filename(prompt: str) -> str:
    clean = re.sub(r'[^a-zA-Z0-9]', '_', prompt[:15])
    return f"{clean}.png"


def get_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _save_generated_image(
    image: Image.Image,
    local_path: Path,
    web_path: str,
    panel_number: int,
    dialogue=None,
    narration=None,
) -> str:
    if not isinstance(image, Image.Image):
        raise RuntimeError("Image provider returned a non-image response")
    image = image.convert("RGB")
    if not is_usable_image(image):
        raise RuntimeError("Image provider returned a blank or unusable image")
    image = apply_comic_lettering(image, panel_number, dialogue, narration)
    image.save(local_path, format="PNG")
    if not is_valid_image_file(local_path):
        local_path.unlink(missing_ok=True)
        raise RuntimeError("Generated image failed local validation")
    logger.info(
        "PANEL %s GENERATED IMAGE | URL: %s | FILE: %s | SIZE: %s | HASH: %s",
        panel_number,
        web_path,
        local_path,
        local_path.stat().st_size,
        get_file_sha256(local_path),
    )
    return web_path


def _huggingface_error_message(error: Exception) -> str:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    error_type = type(error).__name__.lower()

    if "timeout" in error_type:
        return "Hugging Face image generation timed out."
    if status_code in {401, 403}:
        return f"Hugging Face authentication failed (HTTP {status_code}); check HF_API_KEY permissions."
    if status_code in {402, 429}:
        return f"Hugging Face image generation is unavailable due to account limits (HTTP {status_code})."
    if status_code in {404, 410}:
        return f"Hugging Face model is unavailable (HTTP {status_code}); check HF_IMAGE_MODEL."
    if status_code is not None:
        return f"Hugging Face image generation failed (HTTP {status_code})."
    return f"Hugging Face image generation failed ({type(error).__name__})."


def generate_fallback_image(
    prompt: str,
    panel_number: int,
    dialogue=None,
    narration=None,
) -> str:
    panel_number = int(panel_number)
    project_dir = Path(__file__).resolve().parent.parent
    panel_dir = project_dir / "static" / "panels"
    panel_dir.mkdir(parents=True, exist_ok=True)
    filename = f"panel_{panel_number}_{uuid.uuid4().hex[:12]}_{sanitize_filename(prompt)}"
    local_path = panel_dir / filename

    width, height = 600, 400
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    palette = {
        "sky_dark": (11, 18, 28),
        "sky_mid": (31, 45, 69),
        "sky_light": (92, 132, 160),
        "station": (68, 74, 79),
        "platform": (111, 100, 88),
        "metal": (117, 128, 138),
        "wall": (25, 33, 42),
        "grass": (31, 51, 40),
        "track": (52, 59, 67),
        "blue_hoodie": (27, 58, 111),
        "blue_hoodie_light": (63, 112, 180),
        "jeans": (25, 31, 39),
        "skin": (207, 152, 111),
        "hair": (25, 22, 24),
        "eye_white": (244, 241, 234),
        "eye_brown": (56, 42, 32),
        "camera_body": (53, 56, 60),
        "camera_lens": (18, 33, 42),
        "photo_border": (229, 209, 170),
        "photo_fill": (72, 89, 106),
        "friend_top": (136, 92, 74),
        "friend_clothes": (43, 97, 104),
        "warm_light": (245, 196, 112),
        "shadow": (0, 0, 0),
    }

    def draw_station_architecture(vanishing_x, roof_y, light_color=(243, 190, 112), daylight=False):
        wall_top = (87, 104, 116) if daylight else (31, 42, 54)
        wall_bottom = (48, 58, 67) if daylight else (16, 24, 34)
        draw.polygon([(0, 0), (width, 0), (width, roof_y), (vanishing_x, roof_y + 24), (0, roof_y + 7)], fill=wall_top)
        draw.polygon([(0, 0), (width, 0), (vanishing_x, roof_y), (0, roof_y + 7)], fill=wall_bottom)
        for offset in range(5):
            y = 24 + offset * 31
            left_x = int(vanishing_x * (y / max(roof_y, 1)))
            right_x = width - int((width - vanishing_x) * (y / max(roof_y, 1)))
            draw.line((left_x, y, right_x, y), fill=(104, 116, 123), width=2)
        for x in (34, 142, 465, 566):
            foot_x = int(vanishing_x + (x - vanishing_x) * 0.57)
            top_x = int(vanishing_x + (x - vanishing_x) * 0.94)
            draw.polygon([(top_x - 10, 24), (top_x + 10, 24), (foot_x + 20, roof_y + 18), (foot_x - 20, roof_y + 18)], fill=(70, 80, 87), outline=(23, 29, 35))
            draw.line((top_x, 25, foot_x, roof_y + 18), fill=(145, 151, 151), width=3)
            draw.line((top_x - 8, 25, foot_x - 17, roof_y + 18), fill=(35, 45, 52), width=2)
        for x in (105, 300, 496):
            lamp_y = 92 if x == 300 else 128
            draw.line((x, 0, x, lamp_y - 8), fill=(31, 36, 42), width=3)
            draw.rounded_rectangle((x - 17, lamp_y - 6, x + 17, lamp_y + 5), radius=4, fill=light_color, outline=(40, 40, 39), width=2)
            draw.ellipse((x - 32, lamp_y + 2, x + 32, lamp_y + 16), fill=light_color)
        sign_color = (40, 86, 91) if daylight else (34, 65, 77)
        draw.rounded_rectangle((225, 38, 374, 77), radius=5, fill=sign_color, outline=(197, 183, 145), width=3)
        draw.rectangle((238, 48, 361, 52), fill=(218, 218, 198))
        draw.rectangle((257, 60, 342, 64), fill=(218, 218, 198))
        draw.line((0, roof_y + 23, vanishing_x, roof_y), fill=(147, 151, 147), width=2)
        draw.line((width, roof_y + 23, vanishing_x, roof_y), fill=(147, 151, 147), width=2)

    def draw_bench(x, y, scale=1.0):
        draw.rounded_rectangle((x, y, x + 150 * scale, y + 12 * scale), radius=3, fill=(105, 70, 48), outline=(29, 25, 23), width=3)
        draw.line((x + 7 * scale, y + 5 * scale, x + 143 * scale, y + 5 * scale), fill=(172, 123, 75), width=2)
        draw.line((x + 18 * scale, y + 12 * scale, x + 12 * scale, y + 49 * scale), fill=(45, 48, 51), width=5)
        draw.line((x + 132 * scale, y + 12 * scale, x + 139 * scale, y + 49 * scale), fill=(45, 48, 51), width=5)
        draw.line((x + 8 * scale, y + 29 * scale, x + 143 * scale, y + 29 * scale), fill=(78, 82, 83), width=3)

    def gradient_background(top, middle, bottom):
        for y in range(height):
            if y < 180:
                color = tuple(int(top[i] + (middle[i] - top[i]) * (y / 180)) for i in range(3))
            else:
                color = tuple(int(middle[i] + (bottom[i] - middle[i]) * ((y - 180) / 220)) for i in range(3))
            draw.line((0, y, width, y), fill=color)

    def draw_station_tracks():
        draw.rectangle((0, 260, width, height), fill=palette["platform"])
        draw.polygon([(250, 276), (350, 276), (600, 400), (0, 400)], fill=(40, 45, 51))
        for step in range(8):
            y = 286 + step * 17
            spread = 12 + step * 18
            draw.polygon([(300 - spread, y), (300 + spread, y), (300 + spread + 14, y + 6), (300 - spread - 14, y + 6)], fill=(91, 87, 81), outline=(39, 40, 41))
        draw.line((258, 278, 120, 400), fill=(177, 181, 180), width=5)
        draw.line((342, 278, 480, 400), fill=(177, 181, 180), width=5)
        draw.line((255, 278, 117, 400), fill=(42, 47, 52), width=2)
        draw.line((345, 278, 483, 400), fill=(42, 47, 52), width=2)
        draw.line((0, 273, 600, 273), fill=(211, 177, 107), width=4)
        draw.line((0, 280, 600, 280), fill=(59, 59, 57), width=3)
        for x in range(0, width, 85):
            draw.line((x, 289, x + 30, 400), fill=(88, 93, 98), width=2)
        for y in range(300, 405, 24):
            draw.line((0, y, 600, y - 3), fill=(89, 91, 94), width=2)

    def draw_camera(cx, cy, scale=1.0):
        body = (cx - 46 * scale, cy - 22 * scale, cx + 46 * scale, cy + 24 * scale)
        draw.rounded_rectangle((body[0] + 4, body[1] + 6, body[2] + 5, body[3] + 8), radius=10, fill=(14, 17, 21))
        draw.rounded_rectangle(body, radius=8, fill=palette["camera_body"], outline=(18, 21, 25), width=3)
        draw.line((cx - 36 * scale, cy - 14 * scale, cx + 35 * scale, cy - 14 * scale), fill=(113, 119, 121), width=2)
        draw.rectangle((cx - 20 * scale, cy - 24 * scale, cx + 8 * scale, cy - 12 * scale), fill=(80, 83, 88), outline=(18, 21, 25), width=2)
        lens = (cx - 24 * scale, cy - 16 * scale, cx + 24 * scale, cy + 16 * scale)
        draw.ellipse(lens, fill=palette["camera_lens"], outline=(245, 201, 110), width=4)
        draw.ellipse((cx - 10 * scale, cy - 10 * scale, cx + 10 * scale, cy + 10 * scale), fill=(110, 188, 220))
        draw.ellipse((cx - 5 * scale, cy - 7 * scale, cx + 1 * scale, cy - 1 * scale), fill=(230, 245, 235))
        draw.rounded_rectangle((cx + 29 * scale, cy - 13 * scale, cx + 37 * scale, cy - 5 * scale), radius=2, fill=(250, 195, 91))
        draw.line((cx - 34 * scale, cy + 16 * scale, cx + 34 * scale, cy + 16 * scale), fill=(24, 27, 31), width=2)

    def draw_photo_frame(x1, y1, x2, y2, scene_kind):
        draw.rectangle((x1, y1, x2, y2), fill=palette["photo_border"], outline=(30, 27, 24), width=4)
        draw.rectangle((x1 + 7, y1 + 7, x2 - 7, y2 - 7), fill=(177, 205, 213))
        horizon = y1 + int((y2 - y1) * 0.55)
        draw.rectangle((x1 + 8, horizon, x2 - 8, y2 - 8), fill=(164, 151, 132))
        draw.line((x1 + 18, y2 - 14, x1 + 67, horizon), fill=(65, 70, 73), width=3)
        draw.line((x2 - 18, y2 - 14, x2 - 67, horizon), fill=(65, 70, 73), width=3)
        draw.line((x1 + 35, y2 - 14, x1 + 77, horizon), fill=(65, 70, 73), width=2)
        draw.line((x2 - 35, y2 - 14, x2 - 77, horizon), fill=(65, 70, 73), width=2)
        if scene_kind == "danger":
            train_left = x2 - 69
            draw.rectangle((train_left, y1 + 38, x2 - 20, y1 + 70), fill=(75, 91, 105), outline=(34, 42, 48), width=2)
            draw.rectangle((train_left + 6, y1 + 43, x2 - 27, y1 + 53), fill=(205, 218, 218))
            draw.ellipse((train_left + 5, y1 + 65, train_left + 16, y1 + 76), fill=(39, 44, 48))
            draw.ellipse((x2 - 36, y1 + 65, x2 - 25, y1 + 76), fill=(39, 44, 48))
        draw_friend((x1 + x2) / 2, y2 - 55, 0.48)

    def draw_arjun(cx, cy, scale=1.0, expression='curious', pose='stand', facing=1, speaking=False):
        skin = palette["skin"]
        hair = palette["hair"]
        hoodie = palette["blue_hoodie"]
        hoodie_light = palette["blue_hoodie_light"]
        jeans = palette["jeans"]
        eye_white = palette["eye_white"]
        eye_brown = palette["eye_brown"]

        draw.ellipse((cx - 45 * scale, cy + 82 * scale, cx + 45 * scale, cy + 101 * scale), fill=(21, 23, 26))
        face_w = 38 * scale
        face_h = 52 * scale
        face_left = cx - face_w / 2
        face_top = cy - 86 * scale
        draw.ellipse((face_left, face_top, face_left + face_w, face_top + face_h), fill=skin, outline=(21, 21, 21), width=3)

        hair_top = face_top - 8 * scale
        hair_left = cx - 25 * scale
        hair_right = cx + 25 * scale
        draw.polygon([
            (hair_left, hair_top + 10 * scale),
            (cx, hair_top - 18 * scale),
            (hair_right, hair_top + 10 * scale),
            (hair_right + 4 * scale, face_top + 14 * scale),
            (hair_left - 4 * scale, face_top + 14 * scale),
        ], fill=hair)
        draw.rectangle((cx - 20 * scale, face_top + 10 * scale, cx + 20 * scale, face_top + 30 * scale), fill=hair)

        eye_y = face_top + 18 * scale
        for eye_x in (cx - 10 * scale, cx + 10 * scale):
            brow_y = eye_y - 8 * scale
            brow_raise = 3 * scale if expression in {"surprised", "worried"} else 0
            draw.line((eye_x - 6 * scale, brow_y, eye_x + 5 * scale, brow_y - brow_raise), fill=(29, 23, 22), width=max(2, int(3 * scale)))
            draw.ellipse((eye_x - 6 * scale, eye_y - 5 * scale, eye_x + 6 * scale, eye_y + 5 * scale), fill=eye_white)
            draw.ellipse((eye_x - 2 * scale, eye_y - 2 * scale, eye_x + 2 * scale, eye_y + 2 * scale), fill=eye_brown)

        if speaking:
            draw.ellipse(
                (cx - 5 * scale, face_top + 35 * scale, cx + 5 * scale, face_top + 46 * scale),
                fill=(116, 48, 50),
                outline=(57, 30, 30),
                width=max(1, int(2 * scale)),
            )
        elif expression == 'surprised':
            draw.ellipse((cx - 7 * scale, face_top + 30 * scale, cx + 7 * scale, face_top + 40 * scale), fill=(170, 90, 91))
            draw.arc((cx - 14 * scale, face_top + 35 * scale, cx + 14 * scale, face_top + 52 * scale), 205, 335, fill=(101, 52, 54), width=3)
        elif expression == 'worried':
            draw.arc((cx - 12 * scale, face_top + 36 * scale, cx + 12 * scale, face_top + 49 * scale), 180, 360, fill=(109, 47, 53), width=3)
        else:
            draw.arc((cx - 14 * scale, face_top + 36 * scale, cx + 14 * scale, face_top + 50 * scale), 15, 165, fill=(115, 61, 63), width=3)

        nose_y = face_top + 30 * scale
        draw.line((cx, face_top + 20 * scale, cx + 2 * scale, nose_y), fill=(166, 112, 87), width=2)
        draw.line((cx - 20 * scale, face_top + 29 * scale, cx - 17 * scale, face_top + 34 * scale), fill=(226, 172, 132), width=2)

        torso_top = cy + 5 * scale
        torso_bottom = cy + 75 * scale
        torso_left = cx - 22 * scale
        torso_right = cx + 22 * scale
        draw.polygon([
            (torso_left, torso_top),
            (torso_right, torso_top),
            (cx + 32 * scale, torso_bottom),
            (cx - 32 * scale, torso_bottom),
        ], fill=hoodie, outline=(18, 19, 22), width=3)
        draw.rectangle((cx - 5 * scale, torso_top + 6 * scale, cx + 5 * scale, torso_bottom - 12 * scale), fill=hoodie_light)
        draw.arc((cx - 24 * scale, cy - 13 * scale, cx + 24 * scale, cy + 30 * scale), 190, 350, fill=(93, 128, 174), width=max(2, int(3 * scale)))
        draw.line((cx - 19 * scale, torso_top + 27 * scale, cx - 7 * scale, torso_top + 38 * scale), fill=(82, 125, 180), width=max(2, int(3 * scale)))
        draw.line((cx + 19 * scale, torso_top + 27 * scale, cx + 7 * scale, torso_top + 38 * scale), fill=(82, 125, 180), width=max(2, int(3 * scale)))
        draw.rounded_rectangle((cx - 20 * scale, torso_top + 39 * scale, cx + 20 * scale, torso_top + 58 * scale), radius=5, fill=(21, 48, 91), outline=(75, 112, 162), width=2)
        draw.line((cx - 16 * scale, torso_top + 42 * scale, cx - 10 * scale, torso_top + 54 * scale), fill=(93, 129, 170), width=2)
        draw.rectangle((cx - 9 * scale, torso_bottom, cx + 9 * scale, cy + 95 * scale), fill=jeans)

        backpack = (cx - 28 * scale, cy + 6 * scale, cx - 12 * scale, cy + 42 * scale)
        if facing > 0:
            draw.rectangle((cx - 30 * scale, cy + 5 * scale, cx - 8 * scale, cy + 38 * scale), fill=(34, 43, 52), outline=(17, 23, 29), width=2)
            draw.line((cx - 20 * scale, cy + 12 * scale, cx - 20 * scale, cy + 30 * scale), fill=(57, 71, 83), width=2)
        else:
            draw.rectangle((cx + 8 * scale, cy + 5 * scale, cx + 30 * scale, cy + 38 * scale), fill=(34, 43, 52), outline=(17, 23, 29), width=2)

        if pose == 'run':
            draw.line((cx - 18 * scale, torso_top + 8 * scale, cx - 55 * scale, cy + 30 * scale), fill=hoodie, width=12)
            draw.line((cx + 18 * scale, torso_top + 8 * scale, cx + 52 * scale, cy + 35 * scale), fill=hoodie, width=12)
            draw.line((cx - 12 * scale, torso_bottom, cx - 46 * scale, cy + 110 * scale), fill=(12, 17, 22), width=10)
            draw.line((cx + 14 * scale, torso_bottom, cx + 42 * scale, cy + 100 * scale), fill=(12, 17, 22), width=10)
        elif pose == 'reach':
            draw.line((cx + 18 * scale, torso_top + 10 * scale, cx + 54 * scale, cy + 54 * scale), fill=hoodie, width=11)
            draw.ellipse((cx + 49 * scale, cy + 49 * scale, cx + 62 * scale, cy + 62 * scale), fill=skin, outline=(25, 25, 25), width=2)
            draw.line((cx - 18 * scale, torso_top + 10 * scale, cx - 42 * scale, cy + 42 * scale), fill=hoodie, width=10)
            draw.line((cx - 14 * scale, torso_bottom, cx - 26 * scale, cy + 90 * scale), fill=(12, 17, 22), width=8)
            draw.line((cx + 16 * scale, torso_bottom, cx + 28 * scale, cy + 90 * scale), fill=(12, 17, 22), width=8)
        elif pose == 'holding':
            draw.line((cx + 18 * scale, torso_top + 10 * scale, cx + 55 * scale, cy + 8 * scale), fill=hoodie, width=10)
            draw.line((cx + 46 * scale, cy + 8 * scale, cx + 70 * scale, cy - 10 * scale), fill=hoodie, width=9)
            draw.line((cx - 12 * scale, torso_bottom, cx - 22 * scale, cy + 80 * scale), fill=(12, 17, 22), width=10)
            draw.line((cx + 15 * scale, torso_bottom, cx + 28 * scale, cy + 80 * scale), fill=(12, 17, 22), width=10)
        else:
            draw.line((cx - 18 * scale, torso_top + 10 * scale, cx - 42 * scale, cy + 45 * scale), fill=hoodie, width=10)
            draw.line((cx + 18 * scale, torso_top + 10 * scale, cx + 50 * scale, cy + 35 * scale), fill=hoodie, width=10)
            draw.line((cx - 14 * scale, torso_bottom, cx - 26 * scale, cy + 90 * scale), fill=(12, 17, 22), width=8)
            draw.line((cx + 16 * scale, torso_bottom, cx + 28 * scale, cy + 90 * scale), fill=(12, 17, 22), width=8)

    def draw_friend(cx, cy, scale=1.0, pose='standing', speaking=False):
        skin = (179, 122, 94)
        shirt = (76, 139, 91)
        draw.ellipse((cx - 35 * scale, cy + 43 * scale, cx + 35 * scale, cy + 58 * scale), fill=(21, 23, 26))
        draw.ellipse((cx - 16 * scale, cy - 70 * scale, cx + 16 * scale, cy - 20 * scale), fill=skin, outline=(24, 27, 31), width=2)
        draw.ellipse((cx - 18 * scale, cy - 77 * scale, cx + 18 * scale, cy - 45 * scale), fill=(36, 30, 27), outline=(24, 27, 31), width=2)
        draw.ellipse((cx - 18 * scale, cy - 62 * scale, cx - 8 * scale, cy - 48 * scale), fill=(36, 30, 27))
        draw.ellipse((cx + 8 * scale, cy - 62 * scale, cx + 18 * scale, cy - 48 * scale), fill=(36, 30, 27))
        draw.polygon([
            (cx - 20 * scale, cy - 18 * scale),
            (cx + 20 * scale, cy - 18 * scale),
            (cx + 26 * scale, cy + 50 * scale),
            (cx - 26 * scale, cy + 50 * scale),
        ], fill=shirt, outline=(24, 27, 31), width=2)
        draw.line((cx - 14 * scale, cy - 18 * scale, cx - 24 * scale, cy + 44 * scale), fill=(24, 27, 31), width=5)
        draw.line((cx + 14 * scale, cy - 18 * scale, cx + 22 * scale, cy + 44 * scale), fill=(24, 27, 31), width=5)
        draw.ellipse((cx - 5 * scale, cy - 47 * scale, cx - 2 * scale, cy - 43 * scale), fill=(246, 240, 232))
        draw.ellipse((cx + 2 * scale, cy - 47 * scale, cx + 5 * scale, cy - 43 * scale), fill=(246, 240, 232))
        draw.ellipse((cx - 2 * scale, cy - 45 * scale, cx + 2 * scale, cy - 42 * scale), fill=(34, 25, 24))
        if speaking:
            draw.ellipse(
                (cx - 5 * scale, cy - 42 * scale, cx + 5 * scale, cy - 33 * scale),
                fill=(116, 48, 50),
                outline=(57, 30, 30),
                width=max(1, int(2 * scale)),
            )
        else:
            draw.arc((cx - 9 * scale, cy - 40 * scale, cx + 9 * scale, cy - 28 * scale), 15, 165, fill=(95, 43, 40), width=2)

    if panel_number == 1:
        image.paste((177, 196, 199), (0, 0, width, height))
        draw.rectangle((0, 260, width, height), fill=(174, 155, 128))
        draw.rectangle((40, 54, 560, 258), fill=(143, 163, 168), outline=(42, 51, 55), width=5)
        draw.rectangle((67, 78, 533, 235), fill=(190, 207, 207))
        draw_bench(185, 285, 0.82)
        draw_arjun(174, 217, 1.0, expression='curious', pose='reach', facing=1, speaking=True)
        draw_camera(258, 274, 0.68)
    elif panel_number == 2:
        image.paste((194, 212, 214), (0, 0, width, height))
        draw.rectangle((0, 290, width, height), fill=(164, 157, 145))
        draw_photo_frame(42, 49, 260, 238, "danger")
        draw_arjun(430, 286, 1.18, expression='surprised', pose='holding', facing=-1, speaking=True)
        draw_camera(300, 282, 1.0)
    elif panel_number == 3:
        image.paste((177, 193, 200), (0, 0, width, height))
        draw.rectangle((0, 278, width, height), fill=(157, 147, 133))
        draw_arjun(167, 293, 1.2, expression='worried', pose='holding', facing=1, speaking=True)
        draw_camera(296, 275, 0.82)
        draw_photo_frame(372, 49, 561, 236, "danger")
    elif panel_number == 4:
        image.paste((197, 213, 218), (0, 0, width, height))
        draw.rectangle((0, 286, width, height), fill=(169, 155, 134))
        draw.rectangle((42, 80, 110, 286), fill=(151, 171, 176))
        draw.rectangle((491, 80, 558, 286), fill=(151, 171, 176))
        draw.line((340, 286, 236, 400), fill=(65, 70, 73), width=4)
        draw.line((405, 286, 510, 400), fill=(65, 70, 73), width=4)
        draw.line((359, 286, 279, 400), fill=(65, 70, 73), width=3)
        draw.line((386, 286, 451, 400), fill=(65, 70, 73), width=3)
        draw.rounded_rectangle((300, 110, 590, 218), radius=12, fill=(69, 83, 96), outline=(31, 38, 44), width=4)
        draw.rectangle((320, 128, 566, 168), fill=(194, 215, 219), outline=(35, 42, 47), width=3)
        for window_x in (327, 390, 453, 516):
            draw.line((window_x, 130, window_x, 166), fill=(68, 82, 91), width=3)
        draw.ellipse((320, 192, 346, 218), fill=(244, 205, 106), outline=(35, 39, 42), width=3)
        draw.ellipse((550, 192, 576, 218), fill=(244, 205, 106), outline=(35, 39, 42), width=3)
        draw_arjun(216, 291, 1.12, expression='determined', pose='run', facing=1, speaking=True)
        draw_friend(468, 306, 0.82, speaking=True)
    elif panel_number == 5:
        image.paste((145, 195, 218), (0, 0, width, height))
        draw.rectangle((0, 290, width, height), fill=(105, 163, 105))
        draw.rectangle((62, 92, 538, 290), fill=(151, 164, 157), outline=(42, 51, 55), width=5)
        draw.rectangle((309, 147, 449, 290), fill=(83, 112, 119), outline=(42, 51, 55), width=4)
        draw_arjun(222, 294, 1.0, expression='relieved', pose='stand', facing=1, speaking=True)
        draw_friend(386, 303, 0.9, speaking=True)
        draw_camera(293, 337, 0.55)

    image = image.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
    top_strip_height = max(32, round(30 * min(image.width / 600, image.height / 400)))
    ImageDraw.Draw(image).rectangle((0, 0, image.width, top_strip_height), fill=(255, 255, 255))
    image = apply_comic_lettering(image, panel_number, dialogue, narration)

    image.save(local_path, format="PNG", compress_level=6)
    if not is_valid_image_file(local_path):
        raise RuntimeError(f"Fallback image for panel {panel_number} failed validation")
    logger.warning("Panel %s fallback artwork saved to %s", panel_number, local_path)
    logger.info(
        "PANEL %s FALLBACK SCENE | URL: %s | FILE: %s | SIZE: %s | HASH: %s",
        panel_number,
        f"/static/panels/{filename}",
        local_path,
        local_path.stat().st_size,
        get_file_sha256(local_path),
    )
    return f"/static/panels/{filename}"


def generate_image(
    prompt: str,
    panel_number: int = 1,
    dialogue: str = "",
    narration=None,
) -> str:
    panel_number = int(panel_number)
    backend = settings.image_backend.strip().lower()
    project_dir = Path(__file__).resolve().parent.parent
    panel_dir = project_dir / "static" / "panels"
    panel_dir.mkdir(parents=True, exist_ok=True)
    filename = f"panel_{panel_number}_{uuid.uuid4().hex[:12]}_{sanitize_filename(prompt)}"
    local_path = panel_dir / filename
    web_path = f"/static/panels/{filename}"

    clean_prompt = (
        f"{prompt} Polished 2D cartoon comic-book style, clean bold outlines, expressive faces, "
        "colorful but natural colors, detailed but understandable backgrounds, and consistent character design. "
        "Arjun is a college student with short black hair and brown eyes, wearing the same blue hoodie, "
        "dark jeans, and black backpack in every panel. Reserve clear space for speech balloons. "
        "Do not render lettering; exact text is typeset into the finished artwork. No random text, "
        "photorealism, "
        "logos, or watermarks."
    )

    if backend in {"local", "placeholder"}:
        return generate_fallback_image(prompt, panel_number, dialogue, narration)

    if backend == "huggingface":
        try:
            api_key = settings.image_api_key.get_secret_value().strip()
            if not api_key or api_key.lower() in {
                "your_huggingface_api_key_here",
                "your_real_key_here",
            }:
                raise RuntimeError("Hugging Face API key is missing.")
            if not settings.image_model.strip():
                raise RuntimeError("Hugging Face model is missing.")
            client = InferenceClient(
                model=settings.image_model.strip(),
                provider="auto",
                token=api_key,
                timeout=90,
            )
            generated_image = client.text_to_image(clean_prompt)
            return _save_generated_image(
                generated_image,
                local_path,
                web_path,
                panel_number,
                dialogue,
                narration,
            )
        except Exception as exc:
            local_path.unlink(missing_ok=True)
            logger.warning(
                "Hugging Face image generation failed for panel %s (%s); using local artwork",
                panel_number,
                _huggingface_error_message(exc),
            )
            return generate_fallback_image(prompt, panel_number, dialogue, narration)

    if backend != "pollinations":
        raise RuntimeError(
            f"Unsupported IMAGE_BACKEND '{backend}'. Use huggingface, pollinations, or local."
        )

    api_key = settings.pollinations_api_key.get_secret_value().strip()
    if not api_key or api_key.lower() in {
        "your_pollinations_secret_key",
        "your_real_key_here",
    }:
        logger.warning(
            "Pollinations API key is missing for panel %s; using local artwork",
            panel_number,
        )
        return generate_fallback_image(prompt, panel_number, dialogue, narration)

    headers = {"Authorization": f"Bearer {api_key}"}

    for attempt in range(1, 3):
        try:
            seed = random.randint(1000, 999999)
            encoded = urllib.parse.quote(clean_prompt, safe="")
            url = f"https://gen.pollinations.ai/image/{encoded}"
            resp = requests.get(
                url,
                headers=headers,
                params={
                    "model": "black-forest-labs/flux.1-schnell",
                    "width": 600,
                    "height": 400,
                    "seed": seed,
                    "nologo": "true",
                },
                timeout=(10, 90),
            )
            resp.raise_for_status()
            if len(resp.content) <= 5000:
                raise ValueError("Image response was empty or too small")
            with Image.open(BytesIO(resp.content)) as source_image:
                source_image.load()
                img = source_image.convert("RGB")
            if not is_usable_image(img):
                raise ValueError("Image response was blank, too small, or visually unusable")
            return _save_generated_image(
                img,
                local_path,
                web_path,
                panel_number,
                dialogue,
                narration,
            )
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            error_kind = "timeout" if "timeout" in type(exc).__name__.lower() else type(exc).__name__
            logger.warning(
                "Pollinations image generation failed for panel %s (attempt %s/2; %s%s)",
                panel_number,
                attempt,
                error_kind,
                f", HTTP {status_code}" if status_code is not None else "",
            )

    logger.warning(
        "Using fallback artwork for panel %s after the remote request failed",
        panel_number,
    )
    try:
        return generate_fallback_image(prompt, panel_number, dialogue, narration)
    except Exception as exc:
        raise RuntimeError(f"Could not create artwork or fallback for panel {panel_number}: {exc}") from exc