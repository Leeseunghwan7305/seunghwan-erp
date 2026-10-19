"""CLIP 이미지 검색 — 이미지·텍스트를 같은 임베딩 공간(clip-ViT-B-32, 512d)에 넣어
텍스트 쿼리나 이미지 쿼리로 유사 이미지를 찾는다.

기존 RAG와 같은 패턴: 임베딩은 Postgres JSONB에 저장, numpy 코사인으로 검색.
차이는 모달리티 — bge-m3(텍스트 전용) 대신 CLIP(멀티모달)을 쓴다.

torch는 무거워서 선택적 의존성(requirements-ml.txt)이다. 모델은 lazy 로드하고,
미설치면 친절한 에러를 던진다(핵심 앱·CI는 영향 없음).
"""
import io
from pathlib import Path
from typing import Any

import numpy as np
from sqlmodel import Session, select

from ..database import engine
from ..models import ItemImage

IMAGES_DIR = Path(__file__).resolve().parents[2] / "uploads" / "images"
# 이미지 인코더(영어 CLIP)와 텍스트 인코더(다국어)를 분리한다. 다국어 텍스트 모델은
# 같은 이미지 공간(512d)에 정렬돼 있어, 한국어 쿼리도 영어 CLIP 이미지와 비교된다.
_img_model = None   # clip-ViT-B-32         : 이미지 임베딩
_txt_model = None   # ...-multilingual-v1   : 다국어 텍스트 임베딩(한국어 포함)


def _load(name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:  # noqa: BLE001
        raise RuntimeError(
            "CLIP 미설치 — `pip install -r backend/requirements-ml.txt` 후 사용하세요."
        ) from e
    return SentenceTransformer(name)


def _image_model():
    """이미지 인코더 lazy 싱글턴."""
    global _img_model
    if _img_model is None:
        _img_model = _load("clip-ViT-B-32")
    return _img_model


def _text_model():
    """다국어 텍스트 인코더 lazy 싱글턴(한국어 쿼리 지원)."""
    global _txt_model
    if _txt_model is None:
        _txt_model = _load("sentence-transformers/clip-ViT-B-32-multilingual-v1")
    return _txt_model


def encode_text(text: str) -> list[float]:
    return [float(x) for x in _text_model().encode(text)]


def encode_image_bytes(data: bytes) -> list[float]:
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGB")
    return [float(x) for x in _image_model().encode(img)]


def cosine_topk(query: list[float], matrix: list[list[float]], k: int) -> list[tuple[int, float]]:
    """정규화 내적으로 top-k (index, score)를 돌려주는 순수 함수(torch 불필요 — 테스트 대상)."""
    if not matrix:
        return []
    m = np.array(matrix, dtype=np.float32)
    q = np.array(query, dtype=np.float32)
    mn = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-8)
    qn = q / (np.linalg.norm(q) + 1e-8)
    scores = mn @ qn
    idx = np.argsort(scores)[::-1][:k]
    return [(int(i), float(scores[int(i)])) for i in idx]


def _all_images() -> list[ItemImage]:
    with Session(engine) as s:
        return list(s.exec(select(ItemImage)).all())


def _search(query_vec: list[float], top_k: int) -> list[dict[str, Any]]:
    imgs = [im for im in _all_images() if im.embedding]
    hits = cosine_topk(query_vec, [im.embedding for im in imgs], top_k)
    return [
        {
            "id": imgs[i].id,
            "filename": imgs[i].filename,
            "label": imgs[i].label,
            "is_sample": imgs[i].is_sample,
            "score": round(score, 4),
        }
        for i, score in hits
    ]


def search_by_text(text: str, top_k: int = 8) -> list[dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return []
    return _search(encode_text(text), top_k)


def search_by_image(data: bytes, top_k: int = 8) -> list[dict[str, Any]]:
    return _search(encode_image_bytes(data), top_k)


def add_image(data: bytes, label: str, is_sample: bool = False) -> ItemImage:
    """이미지 저장 + CLIP 임베딩 후 DB 등록. 파일명은 id 부여 전 임시→저장 후 확정."""
    from PIL import Image

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(data)).convert("RGB")
    vec = [float(x) for x in _image_model().encode(img)]
    with Session(engine) as s:
        row = ItemImage(filename="", label=label or "", is_sample=is_sample, embedding=vec)
        s.add(row)
        s.commit()
        s.refresh(row)
        fname = f"img_{row.id}.png"
        img.save(IMAGES_DIR / fname, format="PNG")
        row.filename = fname
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


# ---- 합성 샘플 생성 (외부 이미지 저작권 없이 self-contained 데모) -------------

_SAMPLES = [
    ("빨간 음료 캔", "can", (220, 50, 50)),
    ("파란 음료 캔", "can", (50, 90, 220)),
    ("주황 음료 캔", "can", (240, 140, 30)),
    ("녹색 유리병", "bottle", (40, 160, 70)),
    ("투명 생수병", "bottle", (180, 210, 230)),
    ("보라 유리병", "bottle", (150, 60, 180)),
    ("노란 종이상자", "box", (235, 200, 40)),
    ("갈색 종이상자", "box", (150, 100, 60)),
]


def _draw_product(shape: str, color: tuple[int, int, int]):
    """색·도형이 뚜렷한 제품 이미지를 PIL로 그린다. CLIP이 색·형태로 구분."""
    from PIL import Image, ImageDraw

    W = H = 224
    img = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(img)
    if shape == "can":
        d.rounded_rectangle([80, 50, 144, 185], radius=16, fill=color)
        d.ellipse([80, 40, 144, 62], fill=tuple(min(c + 40, 255) for c in color))
        d.ellipse([80, 174, 144, 196], fill=tuple(max(c - 40, 0) for c in color))
    elif shape == "bottle":
        d.rectangle([101, 35, 123, 70], fill=color)           # 목
        d.rounded_rectangle([86, 70, 138, 190], radius=18, fill=color)  # 몸통
        d.rectangle([99, 28, 125, 38], fill=(90, 90, 90))     # 뚜껑
    else:  # box
        d.polygon([(70, 80), (154, 80), (154, 175), (70, 175)], fill=color)
        d.polygon([(70, 80), (92, 58), (176, 58), (154, 80)],
                  fill=tuple(min(c + 30, 255) for c in color))
        d.polygon([(154, 80), (176, 58), (176, 153), (154, 175)],
                  fill=tuple(max(c - 30, 0) for c in color))
    return img


def ensure_samples() -> int:
    """샘플 이미지가 없으면 합성 이미지를 생성·임베딩·저장한다. 생성한 개수 반환."""
    with Session(engine) as s:
        existing = s.exec(select(ItemImage).where(ItemImage.is_sample == True)).first()  # noqa: E712
    if existing:
        return 0
    count = 0
    for label, shape, color in _SAMPLES:
        img = _draw_product(shape, color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        add_image(buf.getvalue(), label=label, is_sample=True)
        count += 1
    return count
