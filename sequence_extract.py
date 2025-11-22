"""Feature extraction runner using object-oriented wrappers."""

from feature_wrappers import dump_features_as_json
from inventor_utils.app import (
    get_all_features,
    get_inventor_application,
    open_inventor_document,
)


# def print_features(features, doc=None):
#     for feature in features:
#         wrapper = wrap_feature(feature, doc=doc)
#         wrapper.pretty_print()


def main():
    app = get_inventor_application()
    if app is None:
        raise SystemExit("Inventor application not available.")
    app.Visible = True
    part_doc = open_inventor_document(
        app,
        "E:\\Python\\PyProjects\\Seq2Inventor\\data\\race-car-tubular-chassis\\Formula\\sus_front_upper_right.ipt",
    )
    if part_doc is None:
        print("Failed to open document.")
        raise SystemExit(1)
    count = part_doc.ComponentDefinition.SurfaceBodies.Count
    features = get_all_features(part_doc)
    print("SurfaceBodies Count:", count)
    # print_features(features, doc=part_doc)
    dump_features_as_json(
        features,
        path="E:\\Python\\PyProjects\\Seq2Inventor\\data\\race-car-tubular-chassis\\Formula_output\\sus_front_upper_right.json",
        doc=part_doc,
    )


if __name__ == "__main__":
    main()
