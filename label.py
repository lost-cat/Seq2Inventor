# ...existing code...
import win32com.client
from inventor_util import stable_sorted_bodies, stable_sorted_faces


def add_face_index_labels(doc=None, owner_id: str = "FaceIndexLabels", color_rgb=(255, 0, 0), text_height: float = 0.5, stable: bool = True) -> int:
    """
    在当前 Part 文档中为每个面添加一个可见的序号标注（ClientGraphics）。
    返回创建的标注数量。
    - owner_id: 本次标注的 ClientGraphics 标识，用于后续清除
    - color_rgb: 文本颜色 (R,G,B)
    - text_height: 文本高度（模型单位）
    - stable: True 时按稳定顺序编号（依赖 stable_sorted_bodies/stable_sorted_faces）
    """
    try:
        from math import isnan
    except Exception:
        pass

    # 取文档
    if doc is None:
        try:
            from win32com.client import Dispatch
            app = Dispatch("Inventor.Application")
            doc = app.ActiveDocument
        except Exception:
            return 0
    app = doc.Parent if hasattr(doc, "Parent") else doc.Application
    tg = app.TransientGeometry
    tobj = app.TransientObjects
    doc = win32com.client.CastTo(doc, "PartDocument")
    com_def = doc.ComponentDefinition
    cg_col = com_def.ClientGraphicsCollection

    # 新建一组 ClientGraphics
    try:
        cg = cg_col.Add(owner_id)
    except Exception:
        # 某些版本 Add 需要唯一 id；若冲突，附加计数
        cg = cg_col.Add(f"{owner_id}_{cg_col.Count+1}")

    # 颜色
    try:
        col = tobj.CreateColor(int(color_rgb[0]), int(color_rgb[1]), int(color_rgb[2]))
    except Exception:
        col = None

    # 取 Body 列表
    try:
        bodies = (getattr(com_def, "SurfaceBodies", None)
                  or getattr(com_def, "Bodies", None))
        body_list = [bodies.Item(i) for i in range(1, getattr(bodies, "Count", 0) + 1)]
    except Exception:
        body_list = []


    node_id = 0
    count = 0
    face_idx_global = 1
    for body in body_list:
        # 获取面集合
        faces = getattr(body, "Faces", None)
        if not faces or faces.Count == 0:
            continue
        # 稳定排序（若提供）
        try:
            if stable and 'stable_sorted_faces' in globals():
                face_list = stable_sorted_faces(body)
            else:
                face_list = [faces.Item(i) for i in range(1, faces.Count + 1)]
        except Exception:
            face_list = [faces.Item(i) for i in range(1, faces.Count + 1)]

        for face in face_list:
            try:
                # 选择标注位置：优先 PointOnFace，退化到范围盒中心
                try:
                    p = face.PointOnFace
                except Exception:
                    rb = face.Evaluator.RangeBox
                    lo = rb.MinPoint; hi = rb.MaxPoint
                    p = tg.CreatePoint((lo.X+hi.X)/2.0, (lo.Y+hi.Y)/2.0, (lo.Z+hi.Z)/2.0)

                # 创建文本图元
                node = cg.AddNode(node_id)
                node_id += 1
                txt = node.AddTextGraphics()
                # 文本内容：全局序号（也可用 per-body 序号）
                txt.Text = str(face_idx_global)
                # 锚点
                try:
                    txt.Anchor = p
                except Exception:
                    # 某些版本为 Position
                    try:
                        txt.Position = p
                    except Exception:
                        pass
                # 大小/颜色/朝向（尽力设置，属性名可能因版本不同）
                for attr, val in (("TextHeight", float(text_height)),
                                  ("Font", "Arial"),
                                  ("Bold", True),
                                  ("Color", col),
                                  ("Billboard", True)):  # Billboard=True 使文字朝向相机
                    try:
                        setattr(txt, attr, val)
                    except Exception:
                        pass

                face_idx_global += 1
                count += 1
            except Exception as e:
                print(f"Error adding label to face {face_idx_global}: {e}")
                continue

    try:
        doc.Update()
    except Exception as e:
        pass
    return count


def clear_face_index_labels(doc=None, owner_id: str = "FaceIndexLabels") -> int:
    """
    删除指定 owner_id 的 ClientGraphics 标注。返回删除数量。
    """
    if doc is None:
        try:
            from win32com.client import Dispatch
            app = Dispatch("Inventor.Application")
            doc = app.ActiveDocument
        except Exception:
            return 0

    com_def = doc.ComponentDefinition
    cg_col = com_def.ClientGraphicsCollection
    removed = 0
    # 遍历删除匹配的 ClientGraphics
    # 注意：API 没有直接按 ID 获取项，逐个判断可行的属性
    for i in range(cg_col.Count, 0, -1):  # 倒序删除
        try:
            cg = cg_col.Item(i)
            # 尝试用常见属性识别 id：ClientId/Name/Label
            ident = None
            for name in ("ClientId", "Name", "Label"):
                if hasattr(cg, name):
                    try:
                        ident = getattr(cg, name)
                        break
                    except Exception:
                        pass
            if ident is None:
                ident = ""
            if str(ident).startswith(owner_id):
                cg.Delete()
                removed += 1
        except Exception:
            continue
    try:
        doc.Update()
    except Exception:
        pass
    return removed

if __name__ == "__main__":
    # 测试用例
    from win32com.client import Dispatch
    app = Dispatch("Inventor.Application")
    doc = app.ActiveDocument

    n_added = add_face_index_labels(doc, owner_id="TestFaceLabels", color_rgb=(0, 0, 255), text_height=1.0, stable=True)
    print(f"Added {n_added} face index labels.")

    # n_removed = clear_face_index_labels(doc, owner_id="TestFaceLabels")
    # print(f"Removed {n_removed} face index labels.")