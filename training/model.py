from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, dropout: float = 0.0, max_len: int = 10000):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(1)  # [T,1,D]
        self.register_buffer("pe", pe, persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [T, B, D]
        x = x + self.pe[: x.size(0)]
        return self.dropout(x)


@dataclass
class TransformerConfig:
    d_model: int = 256
    nhead: int = 8
    num_layers: int = 6
    dim_feedforward: int = 1024
    dropout: float = 0.1


class VectorTransformer(nn.Module):
    """
    Causal Transformer for continuous 28-dim vectors.
    - Projects 28 -> d_model, adds positional encoding
    - Uses TransformerEncoder with a causal mask (no future lookahead)
    - Predicts next vector via regression head  d_model -> 28
    """

    def __init__(self, cfg: TransformerConfig):
        super().__init__()
        self.cfg = cfg
        self.inp = nn.Linear(28, cfg.d_model)
        enc_layer = nn.TransformerEncoderLayer(
            d_model=cfg.d_model,
            nhead=cfg.nhead,
            dim_feedforward=cfg.dim_feedforward,
            dropout=cfg.dropout,
            batch_first=False,  # we use [T,B,D]
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(enc_layer, num_layers=cfg.num_layers)
        self.pos = PositionalEncoding(cfg.d_model, dropout=cfg.dropout)
        self.out_ln = nn.LayerNorm(cfg.d_model)
        self.head = nn.Linear(cfg.d_model, 28)

    @staticmethod
    def generate_subsequent_mask(sz: int, device: torch.device) -> torch.Tensor:
        # [T, T] with -inf above diagonal, 0 elsewhere
        mask = torch.full((sz, sz), torch.finfo(torch.float32).min, device=device, dtype=torch.float32)
        mask = torch.triu(mask, diagonal=1)
        return mask

    def forward(
        self,
        x: torch.Tensor,
        key_padding_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        x: [B, T, 28]
        key_padding_mask: [B, T] with True for pads (will be ignored)
        Returns: predictions for next vector at each step [B, T, 28]
        """
        B, T, _ = x.shape
        device = x.device
        x = self.inp(x)  # [B,T,D]
        x = x.transpose(0, 1)  # [T,B,D]
        x = self.pos(x)  # [T,B,D]
        # causal mask
        src_mask = self.generate_subsequent_mask(T, device=device)  # [T,T]
        # Transformer expects key_padding_mask with True at PAD positions
        out = self.encoder(x, mask=src_mask, src_key_padding_mask=key_padding_mask)  # [T,B,D]
        out = out.transpose(0, 1)  # [B,T,D]
        out = self.out_ln(out)
        y = self.head(out)  # [B,T,28]
        return y
