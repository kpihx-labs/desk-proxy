"""Pure unit tests for screenshot crop helpers (no live display required)."""

from pathlib import Path

from PIL import Image

from desk_proxy.api.screenshot import crop_image


def test_crop_image_writes_smaller_png(tmp_path: Path | None = None) -> None:
    """crop_image clamps and writes a cropped PNG from a tiny source."""
    base = Path("/tmp/desk-proxy-shots")
    base.mkdir(parents=True, exist_ok=True)
    src = base / "_unit_crop_src.png"
    dst = base / "_unit_crop_dst.png"
    Image.new("RGB", (100, 80), "red").save(src)

    out = crop_image(src, {"x": 10, "y": 10, "w": 40, "h": 30}, dst)
    assert out == dst.resolve()
    assert out.is_file()
    with Image.open(out) as img:
        assert img.size == (40, 30)


def test_crop_image_oob_returns_src() -> None:
    """Out-of-bounds crop that clamps to empty returns the source path."""
    base = Path("/tmp/desk-proxy-shots")
    base.mkdir(parents=True, exist_ok=True)
    src = base / "_unit_crop_oob_src.png"
    dst = base / "_unit_crop_oob_dst.png"
    Image.new("RGB", (50, 50), "blue").save(src)

    out = crop_image(src, {"x": 999, "y": 999, "w": 10, "h": 10}, dst)
    assert out == src
