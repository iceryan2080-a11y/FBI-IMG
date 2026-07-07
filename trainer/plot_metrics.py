"""Gráficas del entrenamiento 'proto' a partir de models/proto/results.csv.

Ultralytics ya genera sus propias imágenes (results.png, confusion_matrix.png,
PR_curve.png, F1_curve.png, labels.jpg). Este script hace un resumen limpio en
una sola figura: pérdidas (train/val) y métricas (precision, recall, mAP).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

RUN = Path("/workspace/models/proto")


def col(df, name):
    for c in df.columns:
        if c.strip() == name:
            return df[c]
    return None


def main():
    csv = RUN / "results.csv"
    if not csv.exists():
        raise SystemExit(f"no existe {csv} — ¿entrenaste ya?")
    df = pd.read_csv(csv)
    df.columns = [c.strip() for c in df.columns]
    e = df["epoch"]

    fig, ax = plt.subplots(1, 2, figsize=(14, 5))

    # --- pérdidas ---
    for name, lbl in [("train/box_loss", "box (train)"),
                      ("train/cls_loss", "cls (train)"),
                      ("train/dfl_loss", "dfl (train)"),
                      ("val/box_loss", "box (val)"),
                      ("val/cls_loss", "cls (val)")]:
        c = col(df, name)
        if c is not None:
            ax[0].plot(e, c, label=lbl,
                       ls="--" if "val" in name else "-")
    ax[0].set_title("Pérdidas por época")
    ax[0].set_xlabel("época"); ax[0].set_ylabel("loss")
    ax[0].legend(); ax[0].grid(alpha=.3)

    # --- métricas ---
    for name, lbl in [("metrics/precision(B)", "precision"),
                      ("metrics/recall(B)", "recall"),
                      ("metrics/mAP50(B)", "mAP@50"),
                      ("metrics/mAP50-95(B)", "mAP@50-95")]:
        c = col(df, name)
        if c is not None:
            ax[1].plot(e, c, label=lbl, marker=".")
    ax[1].set_title("Métricas de validación")
    ax[1].set_xlabel("época"); ax[1].set_ylabel("valor")
    ax[1].set_ylim(0, 1.02); ax[1].legend(); ax[1].grid(alpha=.3)

    fig.suptitle("Entrenamiento modelo 'proto' — FBI-IMG", fontweight="bold")
    fig.tight_layout()
    out = RUN / "resumen_entrenamiento.png"
    fig.savefig(out, dpi=130)
    print(f"✅ gráfica guardada: {out}")

    # resumen final por consola
    last = df.iloc[-1]
    print("\n== métricas época final ==")
    for name in ["metrics/precision(B)", "metrics/recall(B)",
                 "metrics/mAP50(B)", "metrics/mAP50-95(B)"]:
        c = col(df, name)
        if c is not None:
            print(f"  {name:24s} = {float(last[name]):.4f}")


if __name__ == "__main__":
    main()
