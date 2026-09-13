"""
금융 시계열 검증 (요구사항 36).

Random Split을 사용하지 않고, 반드시 시간 순서를 유지하는 TimeSeriesSplit /
Walk-Forward Validation을 지원한다.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.model_selection import TimeSeriesSplit


@dataclass
class FoldIndices:
    train_idx: np.ndarray
    test_idx: np.ndarray


def time_series_split(n_samples: int, n_splits: int = 5) -> list[FoldIndices]:
    """sklearn TimeSeriesSplit 래퍼: 항상 과거 -> 미래 순서로 분할한다."""
    if n_samples < n_splits + 1:
        n_splits = max(1, n_samples - 1)

    tscv = TimeSeriesSplit(n_splits=n_splits)
    folds = []
    for train_idx, test_idx in tscv.split(np.arange(n_samples)):
        folds.append(FoldIndices(train_idx=train_idx, test_idx=test_idx))
    return folds


def walk_forward_split(n_samples: int, initial_train_size: int, step: int = 1) -> list[FoldIndices]:
    """
    Walk-Forward Validation: 예) 2018~2022 Train -> 2023 Test -> 2018~2023 Train -> 2024 Test ...
    initial_train_size 이후부터 step 크기만큼씩 Test 구간을 이동시키며 Train 구간을 누적 확장한다.
    """
    folds = []
    train_end = initial_train_size
    while train_end + step <= n_samples:
        train_idx = np.arange(0, train_end)
        test_idx = np.arange(train_end, min(train_end + step, n_samples))
        folds.append(FoldIndices(train_idx=train_idx, test_idx=test_idx))
        train_end += step
    return folds
