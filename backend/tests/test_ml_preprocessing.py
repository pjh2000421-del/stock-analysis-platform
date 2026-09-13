"""ML 전처리 파이프라인 테스트 (요구사항 68, 73: dummy dataset으로 실행 확인)."""
import numpy as np
import pandas as pd

from app.ml.lag_features import add_lag_features
from app.ml.preprocessing import build_price_feature_frame, compute_log_return, fit_scaler_on_train_only


def _dummy_ohlcv(n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame(
        {
            "open": close + rng.normal(0, 0.5, n),
            "high": close + abs(rng.normal(0, 1, n)),
            "low": close - abs(rng.normal(0, 1, n)),
            "close": close,
            "volume": rng.integers(1000, 5000, n),
        }
    )


def test_compute_log_return_first_value_is_nan():
    df = _dummy_ohlcv(10)
    log_ret = compute_log_return(df["close"])
    assert pd.isna(log_ret.iloc[0])
    assert log_ret.iloc[1:].notna().all()


def test_build_price_feature_frame_adds_expected_columns():
    df = _dummy_ohlcv(60)
    out = build_price_feature_frame(df)
    for col in ["log_return", "ma5", "ma20", "volatility_20d"]:
        assert col in out.columns


def test_fit_scaler_on_train_only_range():
    df = _dummy_ohlcv(60)
    feature_df = build_price_feature_frame(df).dropna()
    split = int(len(feature_df) * 0.8)
    train_df, test_df = feature_df.iloc[:split], feature_df.iloc[split:]

    result = fit_scaler_on_train_only(train_df, test_df, ["close", "volume"])

    assert result.train_scaled.min() >= 0.0 - 1e-9
    assert result.train_scaled.max() <= 1.0 + 1e-9
    # Test 데이터는 Train 분포를 벗어날 수 있으므로 0~1 범위를 반드시 만족하지는 않는다.
    assert result.test_scaled.shape[1] == 2


def test_add_lag_features():
    df = pd.DataFrame({"sentiment": [0.1, 0.2, 0.3, 0.4, 0.5]})
    out = add_lag_features(df, "sentiment", lags=[0, 1, 2])
    assert "sentiment_lag1" in out.columns
    assert "sentiment_lag2" in out.columns
    assert out["sentiment_lag1"].iloc[1] == 0.1
