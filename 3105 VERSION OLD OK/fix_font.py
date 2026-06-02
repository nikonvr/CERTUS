import sys

def fix():
    with open("CERTUS_HUB.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add WA_TransparentForMouseEvents to icon_bg
    target1 = 'self.icon_bg = QFrame(self)'
    repl1 = target1 + '\n        self.icon_bg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)'
    content = content.replace(target1, repl1)

    # 2. Fix the font size in icon_lbl
    target2 = 'self.icon_lbl.setStyleSheet("background: transparent; color: white;")\n        self.icon_lbl.setFont(CertusTheme.get_font(48))'
    repl2 = 'self.icon_lbl.setStyleSheet("background: transparent; color: white; font-size: 56px;")\n        self.icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)'
    content = content.replace(target2, repl2)

    # 3. Add WA_TransparentForMouseEvents to title_lbl
    target3 = 'self.title_lbl = QLabel(title, self)'
    repl3 = target3 + '\n        self.title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)'
    content = content.replace(target3, repl3)
    
    with open("CERTUS_HUB.py", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    fix()
