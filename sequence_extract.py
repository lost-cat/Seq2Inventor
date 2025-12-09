"""Feature extraction runner using object-oriented wrappers."""

import gc
from feature_wrappers import dump_features_as_json
from inventor_utils.app import (
    com_sta,
    get_all_features,
    get_inventor_application,
    open_inventor_document,
    set_inventor_silent,
)


# def print_features(features, doc=None):
#     for feature in features:
#         wrapper = wrap_feature(feature, doc=doc)
#         wrapper.pretty_print()


def main():
    with com_sta():
        app = get_inventor_application()
        # set_inventor_silent(app, True)
        try:
            if app is None:
                raise SystemExit("Inventor application not available.")
            app.Visible = True
            part_doc = open_inventor_document(
                app,
                r"E:\Python\PyProjects\Seq2Inventor\test_inventor_1.ipt",
            )
            if part_doc is None:
                print("Failed to open document.")
                raise SystemExit(1)
            count = part_doc.ComponentDefinition.SurfaceBodies.Count
            features = get_all_features(part_doc)
            if len(features) == 0:
                print("No features found in the document.")
                raise SystemExit(1)
            print("SurfaceBodies Count:", count)
            # print_features(features, doc=part_doc)
            dump_features_as_json(
                features,
                path=r"E:\Python\PyProjects\Seq2Inventor\test_inventor_1_features.json",
                doc=part_doc,
            )
        finally:
            set_inventor_silent(app, False)
            app = None
            gc.collect()


if __name__ == "__main__":
    main()
