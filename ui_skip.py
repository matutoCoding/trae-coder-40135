from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QFrame, QComboBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
import db
from config import MAX_SKIP_COUNT, QUEUE_STATUS_WAITING


class SkipModule(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(f"⏭ 过号处理中心(连续过号 {MAX_SKIP_COUNT} 次自动作废)")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        root.addWidget(title)

        stats = QFrame()
        stats.setStyleSheet("QFrame{background:#fff8e1;border:1px solid #ffe082;border-radius:8px;padding:12px;}")
        sl = QHBoxLayout(stats)
        self.stat_skip = QLabel("累计过号: 0")
        self.stat_invalid = QLabel("已作废: 0")
        self.stat_today = QLabel("今日处理: 0")
        for lab in (self.stat_skip, self.stat_invalid, self.stat_today):
            lab.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
            lab.setStyleSheet("color:#e65100;")
        sl.addWidget(self.stat_skip)
        sl.addStretch()
        sl.addWidget(self.stat_invalid)
        sl.addStretch()
        sl.addWidget(self.stat_today)
        root.addWidget(stats)

        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("筛选:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(
            ["全部记录", "有过号记录(含重排/作废)", "今日记录"]
        )
        self.filter_combo.setCurrentIndex(1)
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        filter_bar.addWidget(self.filter_combo)
        filter_bar.addStretch()

        self.requeue_btn = QPushButton("↩ 重新排到队尾")
        self.requeue_btn.setStyleSheet(BTN_WARN)
        self.requeue_btn.setFixedHeight(36)
        self.requeue_btn.clicked.connect(self.requeue_selected)

        self.invalidate_btn = QPushButton("✕ 强制作废")
        self.invalidate_btn.setStyleSheet(BTN_DANGER)
        self.invalidate_btn.setFixedHeight(36)
        self.invalidate_btn.clicked.connect(self.invalidate_selected)

        self.refresh_btn = QPushButton("⟳ 刷新")
        self.refresh_btn.setFixedHeight(36)
        self.refresh_btn.clicked.connect(self.refresh)

        filter_bar.addWidget(self.requeue_btn)
        filter_bar.addWidget(self.invalidate_btn)
        filter_bar.addWidget(self.refresh_btn)
        root.addLayout(filter_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["排队号", "客户姓名", "物品描述", "状态", "过号次数", "叫号时间", "取号时间", "ID"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setStyleSheet(TABLE_STYLE)
        root.addWidget(self.table, 1)

        tip = QLabel("💡 提示: 叫到号后客户未到可点击「过号」,系统自动将号码重排至队尾并累计过号次数;达到上限自动作废。")
        tip.setStyleSheet("color:#546e7a;padding:8px;background:#eceff1;border-radius:6px;")
        root.addWidget(tip)

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条记录")
            return None
        item = self.table.item(row, 7)
        if not item:
            return None
        return int(item.text())

    def requeue_selected(self):
        qid = self._selected_id()
        if qid is None:
            return
        ret = QMessageBox.question(self, "确认", "确认将此客户重新排到队尾?")
        if ret != QMessageBox.Yes:
            return
        db.mark_skipped(qid, 9999)
        self.refresh()

    def invalidate_selected(self):
        qid = self._selected_id()
        if qid is None:
            return
        ret = QMessageBox.question(self, "确认", "确认作废此排队号?作废后不可恢复!")
        if ret != QMessageBox.Yes:
            return
        db.mark_skipped(qid, 1)
        self.refresh()

    def refresh(self):
        all_rows = db.get_queue_history(limit=500)
        mode = self.filter_combo.currentIndex()
        rows = []
        from datetime import date
        today_str = date.today().isoformat()

        # ---------- 统计：调用专用函数，按 last_skipped_at 真实操作时间计算 ----------
        stat = db.get_today_skip_stats()
        total_skip_times = stat["total_skip"]
        invalid_cnt = stat["total_invalid"]
        today_process = stat["today_processed"]

        # ---------- 筛选表格数据 ----------
        for r in all_rows:
            sc = r["skip_count"] or 0
            if mode == 1 and sc == 0 and r["status"] != "invalid":
                continue
            if mode == 2:
                last_skipped_today = r.get("last_skipped_at") and r["last_skipped_at"].startswith(today_str)
                created_today = r["created_at"] and r["created_at"].startswith(today_str)
                if not last_skipped_today and not created_today:
                    continue
            rows.append(r)

        self.table.setRowCount(len(rows))

        for i, r in enumerate(rows):
            sc = r["skip_count"] or 0
            status = r["status"]

            id_item = QTableWidgetItem(r["ticket_no"])
            id_item.setData(Qt.UserRole, r["id"])
            self.table.setItem(i, 0, id_item)
            self.table.setItem(i, 1, QTableWidgetItem(r["customer_name"] or ""))
            self.table.setItem(i, 2, QTableWidgetItem(r["item_desc"] or ""))

            is_invalid = status == "invalid"
            status_text, color = self._status_style(status)
            if sc > 0 and not is_invalid:
                status_text += f" (已过{sc}次)"
            if is_invalid:
                status_text += f" (过{sc}次,作废)"
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(color))
            f = status_item.font()
            f.setBold(True)
            status_item.setFont(f)
            self.table.setItem(i, 3, status_item)

            count_text = f"{sc} / {MAX_SKIP_COUNT}"
            count_item = QTableWidgetItem(count_text)
            if sc >= MAX_SKIP_COUNT or is_invalid:
                count_item.setForeground(QColor("#b71c1c"))
                count_item.setFont(f)
            elif sc > 0:
                count_item.setForeground(QColor("#ef6c00"))
            self.table.setItem(i, 4, count_item)
            self.table.setItem(i, 5, QTableWidgetItem(r["called_at"] or ""))
            self.table.setItem(i, 6, QTableWidgetItem(r["created_at"] or ""))
            self.table.setItem(i, 7, QTableWidgetItem(str(r["id"])))

        self.stat_skip.setText(f"累计过号次数: {total_skip_times}")
        self.stat_invalid.setText(f"已作废单号数: {invalid_cnt}")
        self.stat_today.setText(f"今日过号/作废处理: {today_process}")

    def _status_style(self, s):
        return {
            "waiting": ("等候中", "#1976d2"),
            "calling": ("叫号中", "#d84315"),
            "serving": ("服务中", "#2e7d32"),
            "skipped": ("已过号(重排)", "#ef6c00"),
            "done": ("已完成", "#455a64"),
            "invalid": ("已作废", "#b71c1c"),
        }.get(s, (s, "#333"))


BTN_WARN = """
QPushButton { background:#ef6c00; color:white; border:none; border-radius:6px; padding:6px 16px; }
QPushButton:hover { background:#e65100; }
"""
BTN_DANGER = """
QPushButton { background:#c62828; color:white; border:none; border-radius:6px; padding:6px 16px; }
QPushButton:hover { background:#b71c1c; }
"""
TABLE_STYLE = """
QTableWidget { background:white; border:1px solid #dde3ea; border-radius:6px; gridline-color:#eceff1; }
QHeaderView::section { background:#eceff1; padding:8px; border:none; border-bottom:2px solid #cfd8dc; font-weight:bold; }
QTableWidget::item { padding:6px; }
"""
