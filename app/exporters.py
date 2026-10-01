import os
from datetime import datetime
from pathlib import Path
from fpdf import FPDF

def _pdf_text(value: str) -> str:
    return str(value).encode("latin-1", "replace").decode("latin-1")

def save_pdf(layout, title: str = "Comic") -> str:
    panels = layout.get("panels", []) if isinstance(layout, dict) else layout
    if not panels:
        raise ValueError("Cannot export a comic without panels")

    project_dir = Path(__file__).resolve().parent.parent
    export_dir = project_dir / "static" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_title(_pdf_text(title))
    
    for index, panel in enumerate(panels):
        panel_number = panel.get("panel_number", panel.get("panel", index + 1))
        panel_title = panel.get("panel_title", panel.get("title", "Action Scene"))
        pdf.add_page()
        stage = panel.get("stage") or panel_title
        pdf.set_fill_color(255, 216, 77)
        pdf.set_draw_color(24, 33, 43)
        pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 12, _pdf_text(f"PANEL {panel_number} - {stage}"), ln=True, align="C", fill=True, border=1)
        
        image_path = panel.get("image_path", "")
        local_img = Path(image_path.lstrip("/"))
        if not local_img.is_absolute():
            local_img = project_dir / local_img
        if not local_img.is_file():
            raise FileNotFoundError(f"Image for panel {panel_number} was not found: {local_img}")
        pdf.image(str(local_img), x=25, y=32, w=160, h=120)
        
    filename = f"comic_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    pdf_path = export_dir / filename
    pdf_bytes = bytes(pdf.output())
    if not pdf_bytes.startswith(b"%PDF-") or b"%%EOF" not in pdf_bytes[-1024:]:
        raise ValueError("FPDF did not produce a valid PDF document")
    pdf_path.write_bytes(pdf_bytes)
    return str(pdf_path.resolve())