from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QInputDialog, QFrame)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
import db
from config import MAX_SKIP_COUNT


class QueueModule(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(2000)
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("📋 排队叫号系统")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        root.addWidget(title)

        form = QFrame()
        form.setStyleSheet(FRAME_STYLE)
        fl = QHBoxLayout(form)
        fl.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("客户姓名")
        self.name_edit.setFixedHeight(36)
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("联系电话")
        self.phone_edit.setFixedHeight(36)
        self.item_edit = QLineEdit()
        self.item_edit.setPlaceholderText("皮具类型 / 描述")
        self.item_edit.setFixedHeight(36)

        self.take_btn = QPushButton("取号排队")
        self.take_btn.setFixedHeight(36)
        self.take_btn.setStyleSheet(BTN_PRIMARY)
        self.take_btn.clicked.connect(self.take_ticket)

        fl.addWidget(QLabel("姓名:"))
        fl.addWidget(self.name_edit, 1)
        fl.addWidget(QLabel("电话:"))
        fl.addWidget(self.phone_edit, 1)
        fl.addWidget(QLabel("物品:"))
        fl.addWidget(self.item_edit, 2)
        fl.addWidget(self.take_btn)
        root.addWidget(form)

        action_bar = QHBoxLayout()
        action_bar.setSpacing(10)

        self.call_btn = QPushButton("🔔 叫下一位")
        self.call_btn.setStyleSheet(BTN_CALL)
        self.call_btn.setFixedHeight(40)
        self.call_btn.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self.call_btn.clicked.connect(self.call_next_ticket)

        self.serve_btn = QPushButton("✔ 已到店(开始服务)")
        self.serve_btn.setStyleSheet(BTN_SUCCESS)
        self.serve_btn.setFixedHeight(40)
        self.serve_btn.clicked.connect(self.mark_as_serving)

        self.skip_btn = QPushButton(f"⏭ 过号(重排/最多{MAX_SKIP_COUNT}次)")
        self.skip_btn.setStyleSheet(BTN_WARN)
        self.skip_btn.setFixedHeight(40)
        self.skip_btn.clicked.connect(self.mark_as_skipped)

        self.done_btn = QPushButton("✓ 服务完成")
        self.done_btn.setStyleSheet(BTN_INFO)
        self.done_btn.setFixedHeight(40)
        self.done_btn.clicked.connect(self.mark_as_done)

        self.refresh_btn = QPushButton("⟳ 刷新")
        self.refresh_btn.setFixedHeight(40)
        self.refresh_btn.clicked.connect(self.refresh)

        action_bar.addWidget(self.call_btn)
        action_bar.addWidget(self.serve_btn)
        action_bar.addWidget(self.skip_btn)
        action_bar.addWidget(self.done_btn)
        action_bar.addStretch()
        action_bar.addWidget(self.refresh_btn)
        root.addLayout(action_bar)

        self.current_label = QLabel("当前叫号: —")
        self.current_label.setFont(QFont("Microsoft YaHei", 22, QFont.Bold))
        self.current_label.setAlignment(Qt.AlignCenter)
        self.current_label.setStyleSheet(
            "background:#e3f2fd;color:#1565c0;padding:16px;border-radius:8px;border:2px solid #90caf9;"
        )
        root.addWidget(self.current_label)

        dashboard = QFrame()
        dashboard.setStyleSheet(
            "QFrame{background:#f5f7fa;border:1px solid #dde3ea;border-radius:8px;padding:10px;}"
        )
        dl = QHBoxLayout(dashboard)
        dl.setSpacing(8)
        self._stat_labels = {}
        for key, label, color in [
            ("waiting", "等候中", "#1976d2"),
            ("calling", "叫号中", "#d84315"),
            ("serving", "服务中", "#2e7d32"),
            ("done", "已完成", "#455a64"),
            ("invalid", "已作废", "#b71c1c"),
            ("avg_wait", "平均等待", "#6a1b9a"),
        ]:
            box = QFrame()
            box.setStyleSheet(
                f"QFrame{{background:white;border:1px solid #e0e0e0;border-radius:6px;padding:6px;}}"
            )
            bl = QVBoxLayout(box)
            bl.setSpacing(4)
            bl.setContentsMargins(8, 6, 8, 6)
            title = QLabel(label)
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet(f"color:{color};font-size:12px;font-weight:bold;")
            val = QLabel("0")
            val.setAlignment(Qt.AlignCenter)
            val.setStyleSheet(f"color:{color};font-size:20px;font-weight:bold;")
            bl.addWidget(title)
            bl.addWidget(val)
            self._stat_labels[key] = val
            dl.addWidget(box, 1)
        root.addWidget(dashboard)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["排队号", "客户姓名", "物品描述", "状态", "过号次数", "叫号时间", "取号时间"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setStyleSheet(TABLE_STYLE)
        root.addWidget(self.table, 1)

    def take_ticket(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入客户姓名")
            return
        phone = self.phone_edit.text().strip()
        item = self.item_edit.text().strip()
        cid = db.add_customer(name, phone, item_desc=item)
        qid, ticket = db.add_queue(cid, name, item)
        self.name_edit.clear()
        self.phone_edit.clear()
        self.item_edit.clear()
        QMessageBox.information(self, "取号成功", f"排队号: {ticket}\n请在休息区等候叫号")
        self.refresh()

    def _selected_row_id(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条队列记录")
            return None, row
        item = self.table.item(row, 0)
        if not item:
            return None, row
        return int(item.data(Qt.UserRole)), row

    def call_next_ticket(self):
        row_data = db.call_next()
        if not row_data:
            QMessageBox.information(self, "提示", "当前没有等候中的客户")
        else:
            self.current_label.setText(f"当前叫号: {row_data['ticket_no']}  {row_data['customer_name']}")
        self.refresh()

    def mark_as_serving(self):
        qid, row_idx = self._selected_row_id()
        if qid is None:
            return
        status_item = self.table.item(row_idx, 3)
        raw = status_item.text() if status_item else ""
        if not raw.startswith("叫号中"):
            QMessageBox.warning(self, "提示",
                                "只有「叫号中」的号码才能开始服务。\n请先点击「叫下一位」叫号。")
            return
        db.mark_serving(qid)
        self.refresh()

    def mark_as_done(self):
        qid, _ = self._selected_row_id()
        if qid is None:
            return
        db.mark_done(qid)
        self.refresh()

    def mark_as_skipped(self):
        qid, row_idx = self._selected_row_id()
        if qid is None:
            return
        status_item = self.table.item(row_idx, 3)
        current_status_raw = status_item.text() if status_item else ""
        status_map = {
            "等候中": "waiting",
            "叫号中": "calling",
            "服务中": "serving",
            "已过号": "skipped",
            "已完成": "done",
            "已作废": "invalid",
        }
        status = ""
        for k, v in status_map.items():
            if current_status_raw.startswith(k):
                status = v
                break

        if status != "calling":
            tip = {
                "waiting": "此号码还在等候中,尚未被叫到号,不能过号。",
                "serving": "此客户正在服务中,不能过号。",
                "done": "此号码已完成服务,不能过号。",
                "invalid": "此号码已作废,不能再过号。",
                "skipped": "此号码已过号,请等再次叫到后再处理。",
            }.get(status, "当前状态不允许执行过号操作。")
            QMessageBox.warning(self, "无法过号", tip + "\n\n只有「叫号中」的号码才能执行过号操作。")
            return

        ret = QMessageBox.question(self, "确认过号",
                                   "确认该客户未到店,执行过号?\n(将累计过号次数,达到上限后自动作废)")
        if ret != QMessageBox.Yes:
            return

        result = db.mark_skipped(qid, MAX_SKIP_COUNT)
        if result == "invalid":
            QMessageBox.warning(self, "已作废", "连续过号达到上限,该号已自动作废")
        elif result == "requeued":
            QMessageBox.information(self, "已重排", "客户未到,已重排至队尾")
        self.refresh()

    def refresh(self):
        stats = db.get_today_queue_stats()
        rows = db.get_active_queue()
        self.table.setRowCount(len(rows))
        current_ticket = None
        for i, r in enumerate(rows):
            id_item = QTableWidgetItem(r["ticket_no"])
            id_item.setData(Qt.UserRole, r["id"])
            self.table.setItem(i, 0, id_item)
            self.table.setItem(i, 1, QTableWidgetItem(r["customer_name"] or ""))
            self.table.setItem(i, 2, QTableWidgetItem(r["item_desc"] or ""))

            status_text, color = self._status_style(r["status"])
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(color))
            f = status_item.font()
            f.setBold(True)
            status_item.setFont(f)
            self.table.setItem(i, 3, status_item)

            self.table.setItem(i, 4, QTableWidgetItem(str(r["skip_count"] or 0)))
            self.table.setItem(i, 5, QTableWidgetItem(r["called_at"] or ""))
            self.table.setItem(i, 6, QTableWidgetItem(r["created_at"] or ""))

            if r["status"] == "calling":
                current_ticket = f"{r['ticket_no']}  {r['customer_name']}"

        if current_ticket:
            self.current_label.setText(f"当前叫号: {current_ticket}")
        elif stats["current_calling"]:
            cc = stats["current_calling"]
            self.current_label.setText(f"当前叫号: {cc['ticket_no']}  {cc['customer_name']}")
        else:
            if "—" not in self.current_label.text():
                pass

        self._stat_labels["waiting"].setText(str(stats["waiting"]))
        self._stat_labels["calling"].setText(str(stats["calling"]))
        self._stat_labels["serving"].setText(str(stats["serving"]))
        self._stat_labels["done"].setText(str(stats["done"]))
        self._stat_labels["invalid"].setText(str(stats["invalid"]))

        sec = stats["avg_wait_sec"]
        if sec > 60:
            m, s = divmod(sec, 60)
            self._stat_labels["avg_wait"].setText(f"{m}分{s}秒")
        elif sec > 0:
            self._stat_labels["avg_wait"].setText(f"{sec}秒")
        else:
            self._stat_labels["avg_wait"].setText("—")

    def _status_style(self, s):
        return {
            "waiting": ("等候中", "#1976d2"),
            "calling": ("叫号中", "#d84315"),
            "serving": ("服务中", "#2e7d32"),
            "skipped": ("已过号", "#ef6c00"),
            "done": ("已完成", "#455a64"),
            "invalid": ("已作废", "#b71c1c"),
        }.get(s, (s, "#333"))


FRAME_STYLE = """
QFrame { background:#f5f7fa; border:1px solid #dde3ea; border-radius:8px; padding:8px; }
QLabel { color:#37474f; }
QLineEdit { background:white; border:1px solid #cfd8dc; border-radius:6px; padding:4px 8px; }
"""
BTN_PRIMARY = """
QPushButton { background:#1976d2; color:white; border:none; border-radius:6px; padding:6px 16px; }
QPushButton:hover { background:#1565c0; }
"""
BTN_CALL = """
QPushButton { background:#d84315; color:white; border:none; border-radius:6px; padding:6px 16px; }
QPushButton:hover { background:#bf360c; }
"""
BTN_SUCCESS = """
QPushButton { background:#2e7d32; color:white; border:none; border-radius:6px; padding:6px 16px; }
QPushButton:hover { background:#1b5e20; }
"""
BTN_WARN = """
QPushButton { background:#ef6c00; color:white; border:none; border-radius:6px; padding:6px 16px; }
QPushButton:hover { background:#e65100; }
"""
BTN_INFO = """
QPushButton { background:#00838f; color:white; border:none; border-radius:6px; padding:6px 16px; }
QPushButton:hover { background:#006064; }
"""
TABLE_STYLE = """
QTableWidget { background:white; border:1px solid #dde3ea; border-radius:6px; gridline-color:#eceff1; }
QHeaderView::section { background:#eceff1; padding:8px; border:none; border-bottom:2px solid #cfd8dc; font-weight:bold; }
QTableWidget::item { padding:6px; }
"""
