"""Feature quality audit: classifies every feature as A/B/C/D/E per the review request."""
import pandas as pd


def audit_features(df, id_cols, label_cols):
    feat_cols = [c for c in df.columns if c not in id_cols + label_cols]
    rows = []
    for c in feat_cols:
        s = df[c]
        missing_pct = round(s.isna().mean() * 100, 2)
        nunique = int(s.nunique(dropna=True))
        is_numeric = pd.api.types.is_numeric_dtype(s)
        variance = float(s.var()) if is_numeric and nunique > 1 else 0.0
        vmin = s.min() if is_numeric and nunique > 0 else None
        vmax = s.max() if is_numeric and nunique > 0 else None
        rows.append({
            "feature": c, "missing_pct": missing_pct, "nunique": nunique,
            "dtype": str(s.dtype), "variance": variance, "min": vmin, "max": vmax,
            "constant": nunique <= 1,
        })
    return pd.DataFrame(rows)


def find_exact_duplicates(df, cols):
    """Returns list of (dup_col, original_col) where dup_col is byte-identical to original_col."""
    seen = {}
    dupes = []
    for c in cols:
        key = tuple(df[c].fillna("__NA__").astype(str))
        if key in seen:
            dupes.append((c, seen[key]))
        else:
            seen[key] = c
    return dupes
