"""全局外观：Fluent 亮色 + 品牌色。"""
from qfluentwidgets import Theme, setTheme, setThemeColor

BRAND = "#206bc4"


def apply_theme():
    setTheme(Theme.LIGHT)
    setThemeColor(BRAND)
