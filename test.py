import os
import win32com.client
from inventor_util import (
    get_inventor_application,
)
from inventor_utils.utils import export_to_step

reference_key_content = None

if __name__ == "__main__":

    app = get_inventor_application()
    app.Visible = True
    part = app.ActiveDocument
    part_doc = win32com.client.CastTo(part, "PartDocument")
    print("Body Count",part_doc.ComponentDefinition.SurfaceBodies.Count)
    print("Face Count",part_doc.ComponentDefinition.SurfaceBodies.Item(1).Faces.Count)
    print('Edge Count',part_doc.ComponentDefinition.SurfaceBodies.Item(1).Edges.Count)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    export_to_step(part_doc, os.path.join(current_dir, "test_output.step"))
    #select all edges
    # edges = part_doc.ComponentDefinition.SurfaceBodies.Item(1).Edges
    # for edge in edges:
        