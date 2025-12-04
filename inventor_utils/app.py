from contextlib import contextmanager
import win32com.client
import pythoncom
import time
import threading
_COM_STATE = threading.local()


def init_com_apartment()->bool:
    """确保当前线程初始化为 STA。重复调用安全。"""
    if getattr(_COM_STATE, "initialized", False):
        return False

    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
    _COM_STATE.initialized = True
    return True

def uninit_com_apartment():
    """与 init_com_apartment 成对调用，仅在本线程初始化过时反初始化。"""
    if getattr(_COM_STATE, "initialized", False):
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        _COM_STATE.initialized = False

@contextmanager
def com_sta():
    """COM STA 上下文管理器，保证成对初始化/释放。"""
    inited = init_com_apartment()
    try:
        yield
    finally:
        # 注意：请在调用处先释放 Inventor 对象引用，再退出上下文
        if inited:
            uninit_com_apartment()
def pump_waiting_messages():
    """泵 COM/UI 消息，避免 Inventor 卡住。"""
    try:
        pythoncom.PumpWaitingMessages()
    except Exception:
        pass

def sleep_with_pump(seconds: float):
    """带消息泵的短睡眠。"""
    end = time.time() + seconds
    while time.time() < end:
        pump_waiting_messages()
        time.sleep(0.01)

def set_inventor_silent(app, enable: bool = True):
    """尽量关闭 UI 干扰（属性存在才设置）。"""
    try:
        uim = app.UserInterfaceManager
        uim.UserInteractionDisabled = bool(enable)
    except Exception:
        pass
    try:
        app.SilentOperation = bool(enable)
    except Exception:
        pass
    try:
        app.ScreenUpdating = not bool(enable)
    except Exception:
        pass

def doevents(app):
    """调用 Inventor 的 DoEvents（若可用），并泵消息。"""
    try:
        app.UserInterfaceManager.DoEvents()
    except Exception:
        pass
    pump_waiting_messages()


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
