"""Barrier state calibration — offline analysis of event snapshots."""
from __future__ import annotations

import base64
import glob
import os
import pickle

import cv2
import numpy as np

from .motion_detector import compute_frame_diff
from .zones import crop_zone

# Fixed crop size for model features (width x height)
_FEAT_W, _FEAT_H = 16, 8
# Features: _FEAT_W*_FEAT_H raw pixels + _FEAT_H row-means + _FEAT_W col-means
_FEAT_N = _FEAT_W * _FEAT_H + _FEAT_H + _FEAT_W  # 128 + 8 + 16 = 152


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def find_snapshot_for_frame(frame_id: str, snapshot_dir: str) -> str | None:
    pattern = os.path.join(snapshot_dir, f"*_{frame_id}_*.jpg")
    matches = glob.glob(pattern)
    if not matches:
        return None
    matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return matches[0]


def load_zone_crop(image_path: str, zone: dict) -> np.ndarray | None:
    img = cv2.imread(image_path)
    if img is None:
        return None
    try:
        return crop_zone(img, zone)
    except Exception:  # noqa: BLE001
        return None


def crop_to_bytes(crop: np.ndarray, quality: int = 80) -> bytes | None:
    ok, encoded = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return encoded.tobytes() if ok else None


def crop_to_base64(crop: np.ndarray, quality: int = 80) -> str | None:
    data = crop_to_bytes(crop, quality)
    return base64.b64encode(data).decode() if data else None


def bytes_to_crop(data: bytes) -> np.ndarray | None:
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def compute_diff_vs_reference(
    crop: np.ndarray,
    reference: np.ndarray,
) -> float:
    ref = reference
    if crop.shape != ref.shape:
        ref = cv2.resize(ref, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_LINEAR)
    return float(compute_frame_diff(ref, crop))


# ---------------------------------------------------------------------------
# Feature extraction for the classifier
# ---------------------------------------------------------------------------

def extract_features(crop: np.ndarray) -> np.ndarray:
    """Convert a BGR barrier-zone crop into a fixed-length feature vector.

    Pipeline:
      1. Resize to _FEAT_W × _FEAT_H
      2. Grayscale
      3. Flatten + L2-normalise

    Returns float32 vector of length _FEAT_N.
    """
    resized = cv2.resize(crop, (_FEAT_W, _FEAT_H), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if len(resized.shape) == 3 else resized
    vec = gray.astype(np.float32).flatten() / 255.0
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 1e-9 else vec


# ---------------------------------------------------------------------------
# Logistic regression (pure numpy — no sklearn dependency)
# ---------------------------------------------------------------------------

def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -500.0, 500.0)))


def _train_logreg(
    X: np.ndarray,
    y: np.ndarray,
    lr: float = 0.5,
    n_iter: int = 800,
    lambda_: float = 0.5,
) -> tuple[np.ndarray, float]:
    """Train binary logistic regression with L2 regularisation using gradient descent.

    Args:
        X: (n_samples, n_features) float32 design matrix.
        y: (n_samples,) float32 labels — 1.0 = OPEN, 0.0 = CLOSED.
        lr: Learning rate.
        n_iter: Number of gradient descent steps.
        lambda_: L2 penalty strength (higher = more regularisation, better for small datasets).

    Returns:
        (weights, bias) — the fitted parameters.
    """
    n, d = X.shape
    W = np.zeros(d, dtype=np.float64)
    b = 0.0
    X64 = X.astype(np.float64)
    y64 = y.astype(np.float64)

    for _ in range(n_iter):
        z = X64 @ W + b
        p = _sigmoid(z)
        err = p - y64
        dW = (X64.T @ err) / n + lambda_ * W / n
        db = np.mean(err)
        W -= lr * dW
        b -= lr * db

    return W.astype(np.float32), float(b)


class BarrierModel:
    """Serialisable logistic regression classifier for barrier state.

    Predicts:
      - 1 / OPEN  when sigmoid(W·x + b) > threshold
      - 0 / CLOSED otherwise
    """

    def __init__(self, W: np.ndarray, b: float, decision_threshold: float = 0.5) -> None:
        self.W = W
        self.b = b
        self.decision_threshold = decision_threshold

    def predict_proba(self, crop: np.ndarray) -> float:
        """Return P(OPEN | crop) in [0, 1]."""
        x = extract_features(crop).astype(np.float64)
        return float(_sigmoid(np.dot(self.W.astype(np.float64), x) + self.b))

    def predict(self, crop: np.ndarray) -> str:
        from .barrier_state import CLOSED, OPEN  # avoid circular import at module level
        p = self.predict_proba(crop)
        return OPEN if p > self.decision_threshold else CLOSED

    # Serialisation
    def to_bytes(self) -> bytes:
        return pickle.dumps(self)

    @staticmethod
    def from_bytes(data: bytes) -> "BarrierModel":
        return pickle.loads(data)  # noqa: S301


# ---------------------------------------------------------------------------
# Training entry point
# ---------------------------------------------------------------------------

def train_barrier_model(
    labeled_crops: list[tuple[np.ndarray, str]],
) -> tuple[BarrierModel, float] | None:
    """Train a logistic regression model from labeled crops.

    Args:
        labeled_crops: List of (BGR crop ndarray, label) where label is "open" or "closed".

    Returns:
        (model, train_accuracy) or None if insufficient samples.
    """
    open_crops = [(c, 1.0) for c, lbl in labeled_crops if lbl == "open"]
    closed_crops = [(c, 0.0) for c, lbl in labeled_crops if lbl == "closed"]

    if not open_crops or not closed_crops:
        return None

    all_samples = open_crops + closed_crops
    X = np.stack([extract_features(c) for c, _ in all_samples])
    y = np.array([lbl for _, lbl in all_samples], dtype=np.float32)

    W, b = _train_logreg(X, y)

    # Calibrate decision threshold using Youden's J on training data
    probs = _sigmoid(X.astype(np.float64) @ W.astype(np.float64) + b)
    best_thr, best_j = 0.5, -1.0
    for thr in np.arange(0.1, 0.91, 0.05):
        preds = (probs > thr).astype(float)
        tp = np.sum((preds == 1) & (y == 1))
        tn = np.sum((preds == 0) & (y == 0))
        fp = np.sum((preds == 1) & (y == 0))
        fn = np.sum((preds == 0) & (y == 1))
        sens = tp / (tp + fn + 1e-9)
        spec = tn / (tn + fp + 1e-9)
        j = sens + spec - 1
        if j > best_j:
            best_j, best_thr = j, float(thr)

    model = BarrierModel(W, b, decision_threshold=best_thr)

    preds = np.array([model.predict_proba(c) > best_thr for c, _ in all_samples])
    accuracy = float(np.mean(preds == (y > 0.5)))

    return model, accuracy


# ---------------------------------------------------------------------------
# Calibration sample building
# ---------------------------------------------------------------------------

def build_calibration_samples(
    events: list[dict],
    check_zone: dict,
    reference_crop: np.ndarray | None,
    threshold: float,
    existing_labels: dict[int, str],
    snapshot_dir: str,
    max_samples: int = 60,
    model: BarrierModel | None = None,
) -> list[dict]:
    """Load event snapshots, crop barrier zone, compute predictions.

    When model is provided, uses model predictions (probability) in addition to diff score.
    diff > threshold → predicted OPEN (closed-reference convention).
    """
    samples: list[dict] = []
    for event in events:
        if len(samples) >= max_samples:
            break
        event_id = int(event["id"])
        frame_id = event.get("frame_id")
        if not frame_id:
            continue
        image_path = find_snapshot_for_frame(str(frame_id), snapshot_dir)
        if not image_path:
            continue
        crop = load_zone_crop(image_path, check_zone)
        if crop is None:
            continue

        diff_score: float | None = None
        predicted_label: str | None = None
        model_prob: float | None = None

        if model is not None:
            model_prob = model.predict_proba(crop)
            predicted_label = "open" if model_prob > model.decision_threshold else "closed"
        elif reference_crop is not None:
            diff_score = compute_diff_vs_reference(crop, reference_crop)
            predicted_label = "open" if diff_score > threshold else "closed"

        if reference_crop is not None and diff_score is None:
            diff_score = compute_diff_vs_reference(crop, reference_crop)

        samples.append({
            "event_id": event_id,
            "occurred_at": event.get("occurred_at"),
            "image_url": f"/api/events/{event_id}/image",
            "crop_b64": crop_to_base64(crop),
            "diff_score": diff_score,
            "model_prob": model_prob,
            "predicted_label": predicted_label,
            "user_label": existing_labels.get(event_id),
        })

    return samples


# ---------------------------------------------------------------------------
# Threshold / accuracy helpers
# ---------------------------------------------------------------------------

def compute_optimal_threshold(samples: list[dict]) -> float | None:
    """Midpoint between max(closed diffs) and min(open diffs). Overlap → mean of means."""
    closed_diffs = [
        s["diff_score"] for s in samples
        if s.get("user_label") == "closed" and s.get("diff_score") is not None
    ]
    open_diffs = [
        s["diff_score"] for s in samples
        if s.get("user_label") == "open" and s.get("diff_score") is not None
    ]
    if not closed_diffs or not open_diffs:
        return None

    max_closed = max(closed_diffs)
    min_open = min(open_diffs)
    if min_open > max_closed:
        return round((max_closed + min_open) / 2, 4)
    mean_closed = sum(closed_diffs) / len(closed_diffs)
    mean_open = sum(open_diffs) / len(open_diffs)
    return round((mean_closed + mean_open) / 2, 4)


def compute_accuracy(samples: list[dict], threshold: float) -> float | None:
    labeled = [s for s in samples if s.get("user_label") and s.get("diff_score") is not None]
    if not labeled:
        return None
    correct = sum(
        1 for s in labeled
        if (s["diff_score"] > threshold) == (s["user_label"] == "open")
    )
    return round(correct / len(labeled), 3)
