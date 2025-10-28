# Seq2Inventor utilities

This repo contains helpers to inspect Inventor part features and to reconstruct simple parts from a JSON dump.

## Dump features to JSON

- Use the wrappers to enumerate features and export to JSON:
  - In code, call dump_features_as_json(features, path). See sequence_extract.py for examples.

## Reconstruct from JSON (experimental)

- Run the script to rebuild a new Part from a dumped JSON file:

  PowerShell

```powershell
python reconstruct_from_json.py .\data\wished.json
```

## Notes and limitations

- Currently only ExtrudeFeature with Distance extents is supported.
- Profile geometry supported: LineSegment, Circle, CircularArc.
- Operations: Join by default if missing in JSON; directions default to Positive.
- If your JSON lacks fields, extend feature_wrappers.BaseFeatureWrapper.to_dict (and specific wrappers) to include the necessary data.
