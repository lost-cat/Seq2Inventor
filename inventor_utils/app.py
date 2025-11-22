import win32com.client


def get_inventor_application():
    try:
        from win32com.client import gencache

        try:
            return gencache.EnsureDispatch("Inventor.Application")
        except Exception:
            return win32com.client.Dispatch("Inventor.Application")
    except Exception as e:
        print("Error: Unable to get Inventor.Application object.", e)
        return None


def add_part_document(app, name):
    from win32com.client import constants

    if app is None:
        app = get_inventor_application()
    if app is None:
        raise RuntimeError("Inventor application is not available")
    part = app.Documents.Add(constants.kPartDocumentObject, "", True)
    try:
        part = win32com.client.CastTo(part, "PartDocument")
    except Exception:
        pass
    part.DisplayName = name
    com_def = part.ComponentDefinition
    return part, com_def


def open_inventor_document(app, file_path):
    if app is None:
        app = get_inventor_application()
    if app is None:
        print("Error: Inventor application is not available.")
        return None
    try:
        part_doc = app.Documents.Open(file_path, True)
        try:
            part_doc = win32com.client.CastTo(part_doc, "PartDocument")
        except Exception:
            pass
        return part_doc
    except Exception as e:
        print(f"Error opening Inventor document: {e}")
        return None


def save__inventor_document(doc, file_path):
    doc.SaveAs(file_path, False)


def get_all_features(doc):
    com_def = doc.ComponentDefinition
    features = com_def.Features
    features_list = []
    for i in range(1, features.Count + 1):
        feature = features.Item(i)
        features_list.append(feature)
    return features_list
