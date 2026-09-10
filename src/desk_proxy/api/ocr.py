"""
OCR helpers via tesseract TSV output.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from desk_proxy.api.run import run_cmd
from desk_proxy.api.screenshot import screenshot
from desk_proxy.config import ocr_lang as default_ocr_lang
from desk_proxy.exceptions import DeskAPIError, DeskProxyError


def ocr_image(path: Path | str, lang: str | None = None) -> dict[str, Any]:
    """Run tesseract TSV OCR on an image and return text + word boxes.

    Args:
        path (Path | str): Image path (PNG/JPEG/…).
        lang (str | None): Tesseract languages (default from config, e.g.
            ``eng+fra``).

    Returns:
        dict[str, Any]: ``{"text": str, "lines": [{"text","x","y","w","h","conf"}, ...]}``.
        ``lines`` here are word-level boxes (tesseract level 5) for click targeting.

    Raises:
        DeskProxyError: When tesseract is missing or ``path`` does not exist.
        DeskAPIError: When tesseract exits non-zero.

    Examples:
        >>> from PIL import Image as PILImage, ImageDraw
        >>> p = Path("/tmp/desk-proxy-shots/_ocr.png")
        >>> img = PILImage.new("RGB", (200, 60), "white")
        >>> ImageDraw.Draw(img).text((10, 20), "Hello", fill="black")
        >>> img.save(p)
        >>> data = ocr_image(p, lang="eng")
        >>> "text" in data and "lines" in data
        True
        >>> isinstance(data["lines"], list)
        True
    """
    if not shutil.which("tesseract"):
        raise DeskProxyError(
            "tesseract not found. Install: sudo apt install tesseract-ocr "
            "tesseract-ocr-eng tesseract-ocr-fra"
        )
    img_path = Path(path)
    if not img_path.is_file():
        raise DeskProxyError(f"OCR image not found: {img_path}")

    lang_s = lang or default_ocr_lang()
    r = run_cmd(
        [
            "tesseract",
            str(img_path),
            "stdout",
            "-l",
            lang_s,
            "--psm",
            "6",
            "tsv",
        ],
        timeout=60,
    )
    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip()
        raise DeskAPIError(
            r.returncode or 1,
            f"tesseract failed on {img_path}"
            + (f" — {detail[:300]}" if detail else ""),
        )

    words: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for i, line in enumerate((r.stdout or "").splitlines()):
        if i == 0:
            continue  # header
        cols = line.split("\t")
        if len(cols) < 12:
            continue
        try:
            level = int(cols[0])
            left, top, width, height = (
                int(cols[6]),
                int(cols[7]),
                int(cols[8]),
                int(cols[9]),
            )
            conf_raw = cols[10]
            conf = float(conf_raw) if conf_raw not in ("", "-1") else -1.0
            word = cols[11]
        except (ValueError, IndexError):
            continue
        if level != 5 or not word.strip():
            continue
        words.append(
            {
                "text": word,
                "x": left,
                "y": top,
                "w": width,
                "h": height,
                "conf": conf,
            }
        )
        text_parts.append(word)

    # Prefer plain text reconstruction; also grab stdout text mode if empty
    text = " ".join(text_parts).strip()
    if not text:
        r2 = run_cmd(
            ["tesseract", str(img_path), "stdout", "-l", lang_s, "--psm", "6"],
            timeout=60,
        )
        text = (r2.stdout or "").strip()

    return {"text": text, "lines": words}


def find_text(
    query: str,
    path: Path | str | None = None,
    screenshot_first: bool = True,
    lang: str | None = None,
) -> list[dict[str, Any]]:
    """Find occurrences of ``query`` in an image (OCR) and return centers.

    Args:
        query (str): Case-insensitive substring to match against OCR words /
            concatenated neighbors.
        path (Path | str | None): Image to OCR. When None and
            ``screenshot_first`` is True, a fresh screenshot is taken.
        screenshot_first (bool): Take a screenshot when ``path`` is None.
        lang (str | None): Tesseract language override.

    Returns:
        list[dict[str, Any]]: Matches with ``text``, ``x``, ``y`` (center),
        ``w``, ``h``, ``conf``, and ``path`` of the OCR source image.

    Raises:
        DeskProxyError: When no image path is available.
        DeskAPIError: When screenshot / OCR fails.

    Examples:
        >>> find_text("xyzzy-unlikely", path="/tmp/desk-proxy-shots/_ocr.png", screenshot_first=False)
        []
        >>> matches = find_text("Hello", path="/tmp/desk-proxy-shots/_ocr.png", screenshot_first=False)  # doctest: +SKIP
        >>> matches[0]["x"] > 0 and matches[0]["y"] > 0
        True
    """
    if not query:
        raise DeskProxyError("find_text query must be non-empty")

    img: Path | None = Path(path) if path is not None else None
    if img is None:
        if not screenshot_first:
            raise DeskProxyError("find_text requires path when screenshot_first=False")
        shot = screenshot()
        img = Path(str(shot["path"]))

    data = ocr_image(img, lang=lang)
    needle = query.lower()
    matches: list[dict[str, Any]] = []

    # Word-level matches
    for word in data["lines"]:
        if needle in str(word["text"]).lower():
            matches.append(
                {
                    "text": word["text"],
                    "x": int(word["x"] + word["w"] / 2),
                    "y": int(word["y"] + word["h"] / 2),
                    "w": word["w"],
                    "h": word["h"],
                    "conf": word["conf"],
                    "path": str(img),
                }
            )

    # Phrase match across consecutive words on roughly the same baseline
    if not matches and " " in needle:
        words = data["lines"]
        for i in range(len(words)):
            acc = words[i]["text"]
            x0, y0 = words[i]["x"], words[i]["y"]
            x1 = words[i]["x"] + words[i]["w"]
            y1 = words[i]["y"] + words[i]["h"]
            confs = [words[i]["conf"]]
            for j in range(i + 1, min(i + 8, len(words))):
                # Same line heuristic: vertical centers within 20px
                cy_i = words[i]["y"] + words[i]["h"] / 2
                cy_j = words[j]["y"] + words[j]["h"] / 2
                if abs(cy_i - cy_j) > 20:
                    break
                acc = f"{acc} {words[j]['text']}"
                x1 = max(x1, words[j]["x"] + words[j]["w"])
                y0 = min(y0, words[j]["y"])
                y1 = max(y1, words[j]["y"] + words[j]["h"])
                confs.append(words[j]["conf"])
                if needle in acc.lower():
                    matches.append(
                        {
                            "text": acc,
                            "x": int((x0 + x1) / 2),
                            "y": int((y0 + y1) / 2),
                            "w": int(x1 - x0),
                            "h": int(y1 - y0),
                            "conf": sum(confs) / len(confs),
                            "path": str(img),
                        }
                    )
                    break

    return matches
