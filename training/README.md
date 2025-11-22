# Training: Transformer on 28‑dim Instruction Vectors

This folder contains a minimal PyTorch pipeline to train a causal Transformer that predicts the next 28‑dim vector in a sequence (teacher forcing). It works with the fixed‑length encoding designed earlier.

## Files

- `dataset.py` — Loads JSON sequences of 28‑dim vectors. Supports single JSON or JSONL. Provides a collate that pads and builds attention masks.
- `model.py` — A lightweight Transformer (encoder + causal mask) for continuous vectors. Input 28‑>d_model projection, sinusoidal positional encoding, regression head back to 28.
- `train_vectors.py` — Training script with MSE next‑step prediction, masking for pads, checkpointing, and an optional synthetic dataset for a quick smoke test.
- `requirements-training.txt` — Extra dependencies for the training part (install separately if you prefer to keep core project lean).

## Data format

Each sample is a sequence of 28‑dim vectors. The loader accepts:

- A JSON array: `[[v1...v28], [v1...v28], ...]`
- A JSON object with key `"sequence"` holding the array above
- JSON Lines where each line is one such array (many samples per file)

## Quick start

1) (Optional) Create a venv and install training dependencies:
   - pip install -r training/requirements-training.txt

2) Run a quick synthetic smoke test (no real data needed):
   - python training/train_vectors.py --synthetic 64,64 --epochs 1 --out training/out_synth

3) Train on your real vectorized sequences (directory or file):
   - python training/train_vectors.py --data data/output --epochs 5 --batch 16 --out training/out_real
   The loader scans `--data` recursively for `*.json`.

Notes:

- Loss is average MSE over valid (non‑pad) tokens for next‑step prediction: input tokens `x[:, :-1, :]` predict `x[:, 1:, :]`.
- For faster convergence, you may normalize each vector dimension offline (mean/std) or add a learnable LayerNorm on inputs.
- If CUDA is available, the script auto‑selects it (override with `--device cpu`).
