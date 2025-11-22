import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split, TensorDataset
from tqdm import tqdm

# Support running both as a script and as a module
try:
    from dataset import FixedVectorDataset, Padder
    from model import TransformerConfig, VectorTransformer
except ImportError:  # pragma: no cover - fallback path modification
    import sys
    sys.path.append(str(Path(__file__).parent))
    from dataset import FixedVectorDataset, Padder
    from model import TransformerConfig, VectorTransformer


def make_synthetic_dataset(n_samples: int, seq_len: int, seed: int = 0) -> TensorDataset:
    rng = np.random.RandomState(seed)
    data = []
    for _ in range(n_samples):
        # A simple smooth random walk in 28-D as a toy signal
        x = rng.randn(seq_len, 28).astype(np.float32) * 0.05
        x = np.cumsum(x, axis=0)
        data.append(torch.from_numpy(x))
    # Pack as a TensorDataset of variable length by padding to max
    T = seq_len
    x = torch.stack([torch.nn.functional.pad(d, (0, 0, 0, T - d.shape[0])) for d in data], dim=0)
    lengths = torch.tensor([seq_len] * n_samples, dtype=torch.int64)
    return TensorDataset(x, lengths)


def save_checkpoint(path: str | os.PathLike, model: nn.Module, optim: optim.Optimizer, step: int, cfg: TransformerConfig):
    path = str(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save({
        "model_state": model.state_dict(),
        "optim_state": optim.state_dict(),
        "step": step,
        "config": asdict(cfg),
    }, path)


def compute_loss(pred: torch.Tensor, target: torch.Tensor, valid_mask: torch.Tensor) -> torch.Tensor:
    # pred/target: [B,T,28], valid_mask: [B,T]
    diff = (pred - target) ** 2  # [B,T,28]
    diff = diff.mean(dim=-1)  # [B,T]
    diff = diff * valid_mask
    denom = valid_mask.sum().clamp(min=1.0)
    return diff.sum() / denom


def train_one_epoch(model: VectorTransformer, loader: DataLoader, opt: optim.Optimizer, device: torch.device) -> float:
    model.train()
    total = 0.0
    n = 0
    for batch in tqdm(loader, desc="train", leave=False):
        if isinstance(batch, dict):
            x = batch["x"].to(device)  # [B,T,28]
            lengths = batch["lengths"].to(device)
            key_mask_valid = batch["attn_mask"].to(device)  # True where valid
        else:
            x, lengths = batch
            x = x.to(device)
            lengths = lengths.to(device)
            key_mask_valid = torch.arange(x.size(1), device=device).unsqueeze(0) < lengths.unsqueeze(1)
        # Teacher forcing next-step prediction: input[:-1] -> predict x[1:]
        x_in = x[:, :-1, :]
        y_tgt = x[:, 1:, :]
        valid_in = key_mask_valid[:, :-1]
        valid_tgt = key_mask_valid[:, 1:]
        key_padding_mask = ~valid_in  # True marks pads

        opt.zero_grad(set_to_none=True)
        y_pred = model(x_in, key_padding_mask=key_padding_mask)
        loss = compute_loss(y_pred, y_tgt, valid_tgt.float())
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        total += float(loss.item())
        n += 1
    return total / max(n, 1)


def evaluate(model: VectorTransformer, loader: DataLoader, device: torch.device) -> float:
    model.eval()
    total = 0.0
    n = 0
    with torch.no_grad():
        for batch in tqdm(loader, desc="valid", leave=False):
            if isinstance(batch, dict):
                x = batch["x"].to(device)
                lengths = batch["lengths"].to(device)
                key_mask_valid = batch["attn_mask"].to(device)
            else:
                x, lengths = batch
                x = x.to(device)
                lengths = lengths.to(device)
                key_mask_valid = torch.arange(x.size(1), device=device).unsqueeze(0) < lengths.unsqueeze(1)
            x_in = x[:, :-1, :]
            y_tgt = x[:, 1:, :]
            valid_in = key_mask_valid[:, :-1]
            valid_tgt = key_mask_valid[:, 1:]
            key_padding_mask = ~valid_in
            y_pred = model(x_in, key_padding_mask=key_padding_mask)
            loss = compute_loss(y_pred, y_tgt, valid_tgt.float())
            total += float(loss.item())
            n += 1
    return total / max(n, 1)


def build_loaders(
    data_path: Optional[str],
    batch_size: int,
    num_workers: int,
    seq_len_limit: Optional[int],
    synthetic: Optional[Tuple[int, int]] = None,
):
    if synthetic is not None:
        n, t = synthetic
        ds = make_synthetic_dataset(n, t)
        # Split 80/20
        n_train = int(0.8 * n)
        n_val = n - n_train
        train_ds, val_ds = random_split(ds, [n_train, n_val], generator=torch.Generator().manual_seed(0))
        collate = None  # already padded tensor dataset
    else:
        assert data_path is not None
        ds = FixedVectorDataset(data_path, recursive=True, seq_len_limit=seq_len_limit)
        n = len(ds)
        n_train = max(int(0.9 * n), 1)
        n_val = max(n - n_train, 1)
        train_ds, val_ds = random_split(ds, [n_train, n_val], generator=torch.Generator().manual_seed(0))
        collate = Padder()
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers, collate_fn=collate)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers, collate_fn=collate)
    return train_loader, val_loader


def main():
    p = argparse.ArgumentParser(description="Train a causal Transformer on 28-dim instruction vectors")
    p.add_argument("--data", type=str, default=None, help="Path to directory or file with JSON sequences (recursive)")
    p.add_argument("--out", type=str, default="training/out", help="Output directory for checkpoints")
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--workers", type=int, default=0)
    p.add_argument("--seq-len", type=int, default=None, help="Optional sequence length cap")
    p.add_argument("--d-model", type=int, default=256)
    p.add_argument("--heads", type=int, default=8)
    p.add_argument("--layers", type=int, default=6)
    p.add_argument("--ffn", type=int, default=1024)
    p.add_argument("--dropout", type=float, default=0.1)
    p.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--synthetic", type=str, default=None, help="Optional synthetic dataset as N,T (e.g., 100,64)")

    args = p.parse_args()

    synthetic = None
    if args.synthetic:
        try:
            n, t = args.synthetic.split(",")
            synthetic = (int(n), int(t))
        except Exception:
            raise SystemExit("--synthetic format must be N,T e.g. 100,64")
        if args.data is None:
            print("[info] Using synthetic dataset; --data is ignored")

    cfg = TransformerConfig(
        d_model=args.d_model,
        nhead=args.heads,
        num_layers=args.layers,
        dim_feedforward=args.ffn,
        dropout=args.dropout,
    )

    device = torch.device(args.device)
    model = VectorTransformer(cfg).to(device)
    opt = optim.AdamW(model.parameters(), lr=args.lr)

    train_loader, val_loader = build_loaders(
        data_path=args.data,
        batch_size=args.batch,
        num_workers=args.workers,
        seq_len_limit=args.seq_len,
        synthetic=synthetic,
    )

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"model": asdict(cfg), "args": vars(args)}, f, indent=2)

    best = float("inf")
    global_step = 0
    for epoch in range(1, args.epochs + 1):
        tr = train_one_epoch(model, train_loader, opt, device)
        va = evaluate(model, val_loader, device)
        print(f"epoch {epoch}: train {tr:.4f}  valid {va:.4f}")
        ckpt_path = os.path.join(args.out, f"ckpt_epoch_{epoch:03d}.pt")
        save_checkpoint(ckpt_path, model, opt, step=global_step, cfg=cfg)
        if va < best:
            best = va
            save_checkpoint(os.path.join(args.out, "ckpt_best.pt"), model, opt, step=global_step, cfg=cfg)
        global_step += len(train_loader)



if __name__ == "__main__":
    main()
