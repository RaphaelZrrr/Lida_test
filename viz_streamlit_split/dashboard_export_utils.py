import io
from PIL import Image, ImageDraw

from export_utils import png_bytes_to_jpeg_bytes, png_bytes_to_pdf_bytes


def _resize_to_width(img: Image.Image, target_width: int) -> Image.Image:
    if img.width == target_width:
        return img
    ratio = target_width / img.width
    new_height = int(img.height * ratio)
    return img.resize((target_width, new_height))


def build_dashboard_png_bytes(title: str, chart_png_list: list[bytes], layout: str = "vertical") -> bytes:
    images = [Image.open(io.BytesIO(b)).convert("RGB") for b in chart_png_list if b]

    if not images:
        raise ValueError("Aucune image à assembler.")

    title_height = 90
    margin = 20
    spacing = 20

    if layout == "2_columns" and len(images) >= 2:
        col_width = max(img.width for img in images) // 2 if max(img.width for img in images) > 1200 else 600
        resized = [_resize_to_width(img, col_width) for img in images]

        rows = []
        for i in range(0, len(resized), 2):
            left = resized[i]
            right = resized[i + 1] if i + 1 < len(resized) else None
            row_height = max(left.height, right.height if right else 0)
            rows.append((left, right, row_height))

        total_width = margin * 2 + col_width * 2 + spacing
        total_height = title_height + margin
        for _, _, row_height in rows:
            total_height += row_height + spacing
        total_height += margin

        canvas = Image.new("RGB", (total_width, total_height), "white")
        draw = ImageDraw.Draw(canvas)
        draw.text((margin, 25), title, fill="black")

        y = title_height
        for left, right, row_height in rows:
            canvas.paste(left, (margin, y))
            if right:
                canvas.paste(right, (margin + col_width + spacing, y))
            y += row_height + spacing

    else:
        width = max(img.width for img in images)
        resized = [_resize_to_width(img, width) for img in images]
        total_height = title_height + margin + sum(img.height for img in resized) + spacing * (len(resized) - 1) + margin
        total_width = width + margin * 2

        canvas = Image.new("RGB", (total_width, total_height), "white")
        draw = ImageDraw.Draw(canvas)
        draw.text((margin, 25), title, fill="black")

        y = title_height
        for img in resized:
            canvas.paste(img, (margin, y))
            y += img.height + spacing

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    out.seek(0)
    return out.read()


def build_dashboard_exports(title: str, chart_png_list: list[bytes], layout: str = "vertical"):
    dashboard_png = build_dashboard_png_bytes(title, chart_png_list, layout)
    dashboard_jpeg = png_bytes_to_jpeg_bytes(dashboard_png)
    dashboard_pdf = png_bytes_to_pdf_bytes(dashboard_png)
    return dashboard_png, dashboard_jpeg, dashboard_pdf