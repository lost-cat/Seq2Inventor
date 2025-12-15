import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import torch
from torch.utils.data import Dataset


class FixedVectorDataset(Dataset):
    """
    Dataset for fixed-length instruction vectors saved as JSON lines or arrays.

    Expects input files where each sample is a list (sequence) of 28-dim vectors.
    - If a directory is provided, it will scan all *.json files under it (non-recursive by default).
    - Each JSON file may contain one of:
        * a top-level list (sequence) of 28-dim lists -> treated as one sample
        * a dict with a key "sequence" -> that value should be the list of vectors
        * a JSON lines file where each line is a list (sequence) -> many samples
    """

    def __init__(
        self,
        path: str | os.PathLike,
        recursive: bool = False,
        seq_len_limit: Optional[int] = None,
        dtype: torch.dtype = torch.float32,
    ) -> None:
        super().__init__()
        self.paths = self._collect_files(path, recursive)
        self.seq_len_limit = seq_len_limit
        self.dtype = dtype
        self.samples: List[Tuple[str, int]] = []  # (file_path, index_in_file) for multi-sample files
        self._index_files()

    def _collect_files(self, path: str | os.PathLike, recursive: bool) -> List[str]:
        p = Path(path)
        files: List[str] = []
        if p.is_dir():
            if recursive:
                files = [str(fp) for fp in p.rglob("*.json")]
            else:
                files = [str(fp) for fp in p.glob("*.json")]
        else:
            files = [str(p)]
        files.sort()
        return files

    def _index_files(self) -> None:
        for fp in self.paths:
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    first = f.read(2048)
                    f.seek(0)
                    # Heuristic: JSON Lines if multiple lines start with [ or { and separated by newlines
                    if "\n" in first:
                        # Try parse per line; if any line parses, treat as jsonl
                        idx = 0
                        ok_any = False
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                obj = json.loads(line)
                                ok_any = True
                                self.samples.append((fp, idx))
                                idx += 1
                            except Exception:
                                # Not JSONL, fallback to single JSON
                                ok_any = False
                                break
                        if ok_any:
                            continue
                        # else fall through to single JSON parse below
                    f.seek(0)
                    obj = json.load(f)
                    if isinstance(obj, list):
                        # one sample per file
                        self.samples.append((fp, -1))
                    elif isinstance(obj, dict) and "sequence" in obj:
                        self.samples.append((fp, -1))
                    else:
                        raise ValueError(f"Unsupported JSON structure in {fp}")
            except Exception as e:
                print(f"[warn] Skipping file due to parse error: {fp}: {e}")

    def __len__(self) -> int:
        return len(self.samples)

    def _load_from_file(self, fp: str, index: int) -> List[List[float]]:
        if index >= 0:
            # JSON Lines
            obj = None
            with open(fp, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    if i == index:
                        obj = json.loads(line)
                        break
            if obj is None:
                raise IndexError(f"Index {index} out of range for JSONL file {fp}")
            seq = obj if isinstance(obj, list) else obj.get("sequence")
        else:
            with open(fp, "r", encoding="utf-8") as f:
                obj = json.load(f)
            seq = obj if isinstance(obj, list) else obj.get("sequence")
        if not isinstance(seq, list):
            raise ValueError(f"Invalid sequence in {fp}")
        return seq

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        fp, index = self.samples[idx]
        seq = self._load_from_file(fp, index)
        # Enforce 28-dim vectors and optional truncation
        arr = np.asarray(seq, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[1] != 28:
            raise ValueError(f"Sample {fp}[{index}] not 2D with 28 dims: shape={arr.shape}")
        if self.seq_len_limit is not None and arr.shape[0] > self.seq_len_limit:
            arr = arr[: self.seq_len_limit]
        return {
            "x": torch.from_numpy(arr).to(self.dtype),  # [T, 28]
            "length": torch.tensor(arr.shape[0], dtype=torch.int32),
        }


class Padder:
    def __init__(self, pad_value: float = 0.0):
        self.pad_value = pad_value

    def __call__(self, batch: List[Dict[str, torch.Tensor]]) -> Dict[str, torch.Tensor]:
        lengths = torch.tensor([b["length"] for b in batch], dtype=torch.int64)
        T = int(lengths.max().item())
        B = len(batch)
        x = torch.full((B, T, 28), self.pad_value, dtype=batch[0]["x"].dtype)
        for i, b in enumerate(batch):
            t = int(b["length"].item())
            x[i, :t] = b["x"]
        attn_mask = torch.arange(T).unsqueeze(0) < lengths.unsqueeze(1)
        return {"x": x, "lengths": lengths, "attn_mask": attn_mask}


class StepByStepDataset(Dataset):

    def __init__(
        self,  json_dir: str | os.PathLike, step_brep_dir: str | os.PathLike):
        super().__init__()
        self.all_json_paths = self._collect_json_files(json_dir)
        self.step_brep_dir = str(step_brep_dir)
    
    def __len__(self) -> int:
        
        return len(self.all_json_paths)
    
    def __getitem__(self, idx: int):
        json_path = self.all_json_paths[idx]
        base_name = os.path.basename(json_path)
        name_no_ext, _ = os.path.splitext(base_name)
        step_brep_path = os.path.join(self.step_brep_dir, name_no_ext)
        return {
            "json_path": json_path,
            "step_brep_path": step_brep_path
        }
        
    
    def _collect_json_files(self, json_dir: str | os.PathLike) -> List[str]:
        p = Path(json_dir)
        files = [str(fp) for fp in p.glob("*.json")]
        files.sort()
        return files