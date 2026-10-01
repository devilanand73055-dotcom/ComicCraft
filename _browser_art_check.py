from pathlib import Path
from unittest.mock import patch

import requests
from PIL import Image
from pydantic import SecretStr

from app.config import settings
from app.comic_script import PANEL_SCRIPT
from app.gemini_flash import get_fallback_panels
from app.image_generator import generate_image, get_file_sha256
from app.routes import get_valid_panel_image_path

story = (
    "A college student discovers a mysterious old camera inside an abandoned railway station. "
    "Every photo taken with the camera shows something that will happen a few minutes later. "
    "At first he thinks it is a coincidence, but when the camera shows his friend in danger, "
    "he must race through the station and change what is about to happen."
)
panels = get_fallback_panels(
    story,
    "Arjun",
    "Abandoned railway station",
    "Mysterious, adventurous, suspenseful, emotional",
    "Polished 2D cartoon comic",
)
quota_response = requests.Response()
quota_response.status_code = 402

def pollinations_quota_response(url, headers, params, timeout):
    assert url.startswith("https://gen.pollinations.ai/image/")
    assert headers["Authorization"] == "Bearer test-only-token"
    assert params["model"] == "black-forest-labs/flux.1-schnell"
    raise requests.HTTPError(response=quota_response)

with patch.object(settings, "pollinations_api_key", SecretStr("test-only-token")):
    with patch(
        "app.image_generator.requests.get",
        side_effect=pollinations_quota_response,
    ):
        urls = [
            generate_image(
                panel["image_prompt"],
                panel_number,
                dialogue=panel["dialogue"],
                narration=panel["narration"],
            )
            for panel_number, panel in enumerate(panels, start=1)
        ]
paths = [get_valid_panel_image_path(url) for url in urls]
hashes = []

assert len(panels) == 5
assert len(set(urls)) == 5
assert [panel["stage"] for panel in panels] == [
    "Beginning", "Development", "Turning Point", "Climax", "Ending"
]
assert all(panel["dialogues"] and panel["dialogue"] for panel in panels)
assert panels[4]["narration"] == "The mystery of the camera had only just begun..."
assert all(path is not None and path.parent == Path("static/panels").resolve() for path in paths)
for path in paths:
    assert path.stat().st_size > 5000
    with Image.open(path) as image:
        assert image.format in {"PNG", "JPEG"}
        image.load()
        assert image.width >= 600 and image.height >= 400
        scale = min(image.width / 600, image.height / 400)
        assert min(image.getpixel((image.width // 2, round(14 * scale)))) > 245
        if path == paths[4]:
            caption_color = image.getpixel((round(25 * scale), image.height - round(18 * scale)))
            assert caption_color[0] > 240 and caption_color[1] > 210
        dimensions = image.size
    hashes.append(get_file_sha256(path))
    print(f"PIL_OPEN={path.name}: OK ({dimensions})")
assert len(set(hashes)) == 5

print(f"PANEL_COUNT={len(panels)}")
print(f"VALID_IMAGES={sum(path is not None for path in paths)}")
print(f"UNIQUE_IMAGES={len(set(hashes))}")
print(f"FILES_IN_STATIC_PANELS={sum(path.parent == Path('static/panels').resolve() for path in paths)}")
