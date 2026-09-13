"""시계열 검증 분할 테스트 (요구사항 68: TimeSeriesSplit, 요구사항 36)."""
from app.ml.validation import time_series_split, walk_forward_split


def test_time_series_split_preserves_order():
    folds = time_series_split(n_samples=100, n_splits=4)
    for fold in folds:
        assert max(fold.train_idx) < min(fold.test_idx), "Train은 항상 Test보다 과거여야 한다"


def test_time_series_split_count():
    folds = time_series_split(n_samples=100, n_splits=4)
    assert len(folds) == 4


def test_walk_forward_split_expanding_window():
    folds = walk_forward_split(n_samples=10, initial_train_size=5, step=1)
    assert len(folds) == 5
    # Train 구간이 갈수록 확장되어야 한다 (Walk-Forward)
    sizes = [len(f.train_idx) for f in folds]
    assert sizes == sorted(sizes)
    for fold in folds:
        assert max(fold.train_idx) < min(fold.test_idx)
