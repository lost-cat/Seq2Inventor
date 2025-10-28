"""Feature extraction runner using object-oriented wrappers."""

from inventor_util import (
    get_inventor_application,
    open_inventor_document,
    get_all_features,
)
from feature_wrappers import dump_features_as_json, dump_features_pretty, wrap_feature


def print_features(features, doc=None):
    for feature in features:
        wrapper = wrap_feature(feature, doc=doc)
        wrapper.pretty_print()


def main():
    app = get_inventor_application()
    if app is None:
        raise SystemExit("Inventor application not available.")
    app.Visible = True
    part_doc = open_inventor_document(
        app, r"E:\Python\PyProjects\Seq2Inventor\test_inventor_0.ipt"
    )
    if part_doc is None:
        print("Failed to open document.")
        raise SystemExit(1)
    features = get_all_features(part_doc)
    # print_features(features, doc=part_doc)
    dump_features_as_json(
        features, path=r"E:\Python\PyProjects\Seq2Inventor\features_test_inventor_0.json", doc=part_doc
    )


if __name__ == "__main__":
    main()
