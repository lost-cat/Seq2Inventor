import win32com.client
from inventor_util import (
    get_inventor_application,
)

reference_key_content = None

if __name__ == "__main__":

    app = get_inventor_application()
    app.Visible = True
    part = app.ActiveDocument
    part_doc = win32com.client.CastTo(part, "PartDocument")
    print("Body Count",part_doc.ComponentDefinition.SurfaceBodies.Count)
    print("Face Count",part_doc.ComponentDefinition.SurfaceBodies.Item(1).Faces.Count)
    print('Edge Count',part_doc.ComponentDefinition.SurfaceBodies.Item(1).Edges.Count)
    #select all edges
    # edges = part_doc.ComponentDefinition.SurfaceBodies.Item(1).Edges
    # for edge in edges:
        