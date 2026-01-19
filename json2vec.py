import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from feature_encoder import FeatureEncoder

__all__ = ["FeatureEncoder", "encode_file", "decode_payload"]


def encode_file(inp: str | Path, outp: str | Path, pretty: bool = False) -> Dict[str, List]:
    """Encode a feature JSON file into the vector payload and write it to disk.

    Also writes a decoded JSON beside it for quick round-trip inspection.
    """
    in_path = Path(inp)
    out_path = Path(outp)

    with in_path.open("r", encoding="utf-8") as f:
        features: List[Dict[str, Any]] = json.load(f)

    encoder = FeatureEncoder()
    payload = encoder.encode(features)
    decoded = encoder.decode(payload)

    indent = 2 if pretty else None
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=indent)

    decoded_path = out_path.with_name(out_path.stem + "_decoded.json")
    with decoded_path.open("w", encoding="utf-8") as f:
        json.dump(decoded, f, ensure_ascii=False, indent=indent)

    return payload


def decode_payload(payload: Dict[str, List]) -> List[Dict[str, Any]]:
    """Decode an in-memory payload back to feature JSON."""
    encoder = FeatureEncoder()
    return encoder.decode(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Encode feature JSON to vector payload")
    parser.add_argument("--in", dest="inp", required=True, help="Input feature JSON")
    parser.add_argument("--out", dest="outp", required=True, help="Output vector JSON")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON outputs")
    args = parser.parse_args()

    payload = encode_file(args.inp, args.outp, pretty=args.pretty)
    print(f"Wrote KV sequence to {args.outp} (len={len(payload.get('key_ids', []))})")


if __name__ == "__main__":
    main()
