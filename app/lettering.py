from PIL import Image, ImageDraw, ImageFont

from app.comic_script import get_panel_lettering


def _font(size):
    for path in (
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _wrap_text(text, font, draw, max_width):
    lines = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def apply_comic_lettering(image, panel_number, dialogue=None, narration=None):
    default_dialogues, default_narration = get_panel_lettering(panel_number)
    if isinstance(dialogue, str):
        dialogue = [line.strip() for line in dialogue.splitlines() if line.strip()]
    if not dialogue:
        dialogue = default_dialogues
    if narration is None:
        narration = default_narration

    image = image.convert("RGB")
    draw = ImageDraw.Draw(image)
    scale = min(image.width / 600, image.height / 400)
    speech_font = _font(max(14, round(14 * scale)))
    caption_font = _font(max(13, round(13 * scale)))
    outline = max(2, round(2 * scale))
    inset = round(14 * scale)
    bubble_x = round(12 * scale)
    max_bubble_width = round(image.width * 0.88)
    top = round(10 * scale)
    gap = round(6 * scale)
    tail_height = round(10 * scale)
    line_height = round(18 * scale)

    for index, speech in enumerate(dialogue):
        speaker, separator, words = str(speech).partition(":")
        if not separator:
            words = speaker
            speaker = ""
        words = words.strip().strip('"')
        lines = _wrap_text(
            words,
            speech_font,
            draw,
            max_bubble_width - 2 * inset,
        )
        text_width = max(
            draw.textbbox((0, 0), line, font=speech_font)[2]
            - draw.textbbox((0, 0), line, font=speech_font)[0]
            for line in lines
        )
        bubble_width = min(max_bubble_width, text_width + 2 * inset)
        speaker_name = speaker.strip().lower()
        right_side = speaker_name == "kavin" or (
            speaker_name == "arjun" and int(panel_number) == 2
        )
        if not speaker_name:
            right_side = index % 2 == 1
        left = image.width - bubble_x - bubble_width if right_side else bubble_x
        bubble_height = max(
            round(38 * scale),
            len(lines) * line_height + round(2 * inset * 0.65),
        )
        tail_x = left + round(bubble_width * (0.76 if right_side else 0.24))
        draw.polygon(
            [
                (tail_x - round(9 * scale), top + bubble_height - outline),
                (tail_x + round(9 * scale), top + bubble_height - outline),
                (tail_x, top + bubble_height + tail_height),
            ],
            fill=(255, 255, 255),
            outline=(25, 30, 35),
        )
        draw.rounded_rectangle(
            (left, top, left + bubble_width, top + bubble_height),
            radius=round(13 * scale),
            fill=(255, 255, 255),
            outline=(25, 30, 35),
            width=outline,
        )
        text_y = top + (bubble_height - len(lines) * line_height) // 2
        for line in lines:
            bounds = draw.textbbox((0, 0), line, font=speech_font)
            text_width = bounds[2] - bounds[0]
            draw.text(
                (left + bubble_width // 2 - text_width // 2, text_y - bounds[1]),
                line,
                font=speech_font,
                fill=(24, 30, 36),
            )
            text_y += line_height
        top += bubble_height + tail_height + gap

    if narration:
        caption_line_height = round(17 * scale)
        caption_width = image.width - 2 * bubble_x
        caption_text_width = caption_width - 2 * inset
        captions = []
        for caption in str(narration).strip().split("\n\n"):
            caption_lines = []
            for text_line in caption.splitlines():
                caption_lines.extend(
                    _wrap_text(text_line, caption_font, draw, caption_text_width)
                )
            if caption_lines:
                caption_height = len(caption_lines) * caption_line_height + inset
                captions.append((caption_lines, caption_height))

        caption_y = image.height - round(10 * scale)
        for caption_lines, caption_height in reversed(captions):
            caption_y -= caption_height
            draw.rounded_rectangle(
                (
                    bubble_x,
                    caption_y,
                    bubble_x + caption_width,
                    caption_y + caption_height,
                ),
                radius=round(4 * scale),
                fill=(255, 235, 165),
                outline=(25, 30, 35),
                width=outline,
            )
            text_y = caption_y + inset // 2
            for line in caption_lines:
                bounds = draw.textbbox((0, 0), line, font=caption_font)
                draw.text(
                    (bubble_x + inset, text_y - bounds[1]),
                    line,
                    font=caption_font,
                    fill=(35, 39, 40),
                )
                text_y += caption_line_height
            caption_y -= gap

    return image