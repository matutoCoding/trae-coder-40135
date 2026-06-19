import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QTabWidget, QStatusBar)
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtCore import Qt
import db
from ui_queue import QueueModule
from ui_skip import SkipModule
from ui_material import MaterialModule
from ui_flow import FlowRecallModule


APP_TITLE = "皮具护理修复管理系统"
APP_VERSION = "v1.0.0"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE}  {APP_VERSION}")
        self.resize(1280, 800)
        self._build_ui()
        self._apply_style()
        self.statusBar().showMessage("系统就绪")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 12, 20, 12)

        title_lbl = QLabel("🛠 皮具护理修复管理系统")
        title_lbl.setObjectName("headerTitle")
        title_lbl.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))

        sub_lbl = QLabel("Leather Care & Repair Management")
        sub_lbl.setObjectName("headerSub")
        sub_lbl.setFont(QFont("Microsoft YaHei", 9))

        hl.addWidget(title_lbl)
        hl.addSpacing(12)
        hl.addWidget(sub_lbl)
        hl.addStretch()

        self.waiting_count = QLabel("等候: 0")
        self.waiting_count.setObjectName("statBadge")
        self.material_count = QLabel("批次: 0")
        self.material_count.setObjectName("statBadge")

        hl.addWidget(self.waiting_count)
        hl.addWidget(self.material_count)
        root.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))

        self.queue_mod = QueueModule()
        self.skip_mod = SkipModule()
        self.material_mod = MaterialModule()
        self.flow_mod = FlowRecallModule()

        self.tabs.addTab(self.queue_mod, "  📋 排队叫号  ")
        self.tabs.addTab(self.skip_mod, "  ⏭ 过号处理  ")
        self.tabs.addTab(self.material_mod, "  🧴 材料批次  ")
        self.tabs.addTab(self.flow_mod, "  🔗 流向召回  ")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs, 1)

        self._refresh_stats()

    def _on_tab_changed(self, idx):
        if idx == 0:
            self.queue_mod.refresh()
        elif idx == 1:
            self.skip_mod.refresh()
        elif idx == 2:
            self.material_mod.refresh()
        elif idx == 3:
            self.flow_mod.refresh_orders()
            self.flow_mod.refresh_materials()
            self.flow_mod.refresh_flows()
        self._refresh_stats()

    def _refresh_stats(self):
        queue = db.get_active_queue()
        waiting = sum(1 for q in queue if q["status"] == "waiting")
        mats = db.get_materials()
        self.waiting_count.setText(f"等候: {waiting}")
        self.material_count.setText(f"批次: {len(mats)}")

    def _apply_style(self):
        self.setStyleSheet("""
        QMainWindow, QWidget { background:#fafbfc; }
        #header {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #1565c0, stop:1 #00838f);
        }
        #headerTitle { color:white; }
        #headerSub { color:#bbdefb; }
        #statBadge {
            color:white; background:rgba(255,255,255,18);
            padding:6px 14px; border-radius:16px;
            font-weight:bold; margin-left:8px;
        }
        #mainTabs::tab {
            background:#e3f2fd;
            padding:10px 20px;
            margin-right:2px;
            color:#455a64;
            border-top-left-radius:6px;
            border-top-right-radius:6px;
        }
        #mainTabs::tab:selected {
            background:white;
            border-top:3px solid #1976d2;
            border-left:1px solid #dde3ea;
            border-right:1px solid #dde3ea;
            border-bottom:none;
            color:#1565c0;
        }
        #mainTabs::pane {
            border:1px solid #dde3ea;
            background:white;
            top:-1px;
        }
        """)


def main():
    db.init_db()
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
