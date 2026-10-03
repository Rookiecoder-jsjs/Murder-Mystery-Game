"""Resize the approved logo for Web and Android without changing its artwork."""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/brand/logo-casefile-source.png"
RES = ROOT / "frontend/android/app/src/main/res"
BACKGROUND = "#b3382c"


def build() -> None:
    """Produce density-specific launcher assets and small Web images."""
    with Image.open(SOURCE) as original:
        source = original.convert("RGBA")
    web = ROOT / "frontend/public/brand"
    web.mkdir(parents=True, exist_ok=True)
    for name, size in (("logo-casefile-v2.png", 512), ("favicon-v2.png", 48)):
        source.resize((size, size), Image.Resampling.LANCZOS).save(web / name)
    for density, scale in (("mdpi", 1), ("hdpi", 1.5), ("xhdpi", 2),
                           ("xxhdpi", 3), ("xxxhdpi", 4)):
        directory = RES / f"mipmap-{density}"
        directory.mkdir(parents=True, exist_ok=True)
        # Adaptive icons use a 108dp viewport and a central 66dp safe circle.
        # Inset the complete approved image to 72dp; retain its paper/red design.
        size, artwork_size = round(108 * scale), round(72 * scale)
        foreground = Image.new("RGBA", (size, size), BACKGROUND)
        offset = (size - artwork_size) // 2
        artwork = source.resize((artwork_size, artwork_size), Image.Resampling.LANCZOS)
        # Extend edge pixels into the overscan area so textured red meets the
        # original image seamlessly instead of showing a square on a flat tile.
        positions = (0, offset, offset + artwork_size, size)
        slices = (0, 1, artwork_size - 1, artwork_size)
        for row in range(3):
            for column in range(3):
                if row == column == 1:
                    piece = artwork
                else:
                    piece = artwork.crop((slices[column], slices[row],
                                          slices[column + 1], slices[row + 1]))
                width = positions[column + 1] - positions[column]
                height = positions[row + 1] - positions[row]
                foreground.alpha_composite(piece.resize((width, height), Image.Resampling.NEAREST),
                                           (positions[column], positions[row]))
        foreground.save(directory / "ic_launcher_foreground.png")
        legacy_size = round(48 * scale)
        # Apply the same visual scale as the adaptive icon's visible 72dp area.
        foreground.resize((round(72 * scale), round(72 * scale)),
                          Image.Resampling.LANCZOS).crop(
            (round(12 * scale), round(12 * scale), round(60 * scale), round(60 * scale))
        ).resize((legacy_size, legacy_size), Image.Resampling.LANCZOS).save(
            directory / "ic_launcher.png")
        with Image.open(directory / "ic_launcher.png") as legacy:
            rounded = legacy.convert("RGBA")
        mask = Image.new("L", rounded.size)
        ImageDraw.Draw(mask).ellipse((0, 0, legacy_size - 1, legacy_size - 1), fill=255)
        rounded.putalpha(mask)
        rounded.save(directory / "ic_launcher_round.png")
    # Existing splash drawables are opaque bitmaps; keep screen paper-colored.
    # Preserve their dimensions to avoid changing startup layout or scaling.
    for path in sorted(RES.glob("drawable*/splash.png")):
        with Image.open(path) as old:
            width, height = old.size
        splash = Image.new("RGBA", (width, height), "#f4f1ea")
        mark_size = round(min(width, height) * 0.22)
        splash.alpha_composite(source.resize((mark_size, mark_size), Image.Resampling.LANCZOS),
                               ((width - mark_size) // 2, (height - mark_size) // 2))
        splash.save(path)
    print("Brand assets generated from the approved A logo.")


if __name__ == "__main__":
    build()
