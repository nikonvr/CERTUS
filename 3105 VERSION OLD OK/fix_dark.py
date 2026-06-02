import sys

def fix():
    with open("CERTUS_HUB.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add objectName to title_lbl and remove the hardcoded color.
    target1 = 'self.title_lbl = QLabel(title, self)\n        self.title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)'
    repl1 = target1 + '\n        self.title_lbl.setObjectName("AppCardTitle")'
    content = content.replace(target1, repl1)

    target2 = 'color: {CertusTheme.TEXT_MAIN};'
    content = content.replace(target2, '', 1) # Note: we only want to replace the first occurrence in ApplicationCard, but wait!
    # A safer replace for the stylesheet:
    target2_full = 'QLabel {\n                color: {CertusTheme.TEXT_MAIN};\n                font-weight: {CertusTheme.FONT_WEIGHT_SEMIBOLD};'
    repl2_full = 'QLabel {\n                font-weight: {CertusTheme.FONT_WEIGHT_SEMIBOLD};'
    content = content.replace(target2_full, repl2_full)

    # 2. Add AppCardTitle styling to _apply_theme
    target3 = '#CertusHeaderTitle { color: {CertusTheme.TEXT_MAIN}; font-weight: bold; }'
    repl3 = target3 + '\n            #AppCardTitle { color: {CertusTheme.TEXT_MAIN}; }'
    content = content.replace(target3, repl3)
    
    with open("CERTUS_HUB.py", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    fix()
