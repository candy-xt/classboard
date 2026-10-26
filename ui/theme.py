"""全局外观：Fluent 亮色 + 品牌色。"""
from qfluentwidgets import Theme, setTheme, setThemeColor

BRAND = "#206bc4"

# 细滚动条：默认的 QScrollBar 在 Windows/Linux 上都是带箭头的粗条，很难看
SCROLLBAR_QSS = """
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(0, 0, 0, 0.16);
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(0, 0, 0, 0.30);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: rgba(0, 0, 0, 0.16);
    border-radius: 4px;
    min-width: 28px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(0, 0, 0, 0.30);
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    background: transparent;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
"""


def apply_theme():
    setTheme(Theme.LIGHT)
    setThemeColor(BRAND)
