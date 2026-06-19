from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QFrame, QDateEdit, QComboBox, QDoubleSpinBox,
                               QTextEdit)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor
import db
from config import MATERIAL_STATUS_ACTIVE, MATERIAL_STATUS_EXPIRED, MATERIAL_STATUS_RECALL
from datetime import date


class MaterialModule(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("🧴 染料油膏批次管理")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        root.addWidget(title)

        form = QFrame()
        form.setStyleSheet(FRAME_STYLE)
        fl = QVBoxLayout(form)
        fl.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.batch_edit = QLineEdit()
        self.batch_edit.setPlaceholderText("批号 (如 RL20250601-01)")
        self.batch_edit.setFixedHeight(32)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("材料名称 (如 苯胺黑染料)")
        self.name_edit.setFixedHeight(32)
        self.type_edit = QLineEdit()
        self.type_edit.setPlaceholderText("类型 (染料/油膏/护理剂)")
        self.type_edit.setFixedHeight(32)
        row1.addWidget(QLabel("批号:"))
        row1.addWidget(self.batch_edit, 2)
        row1.addWidget(QLabel("名称:"))
        row1.addWidget(self.name_edit, 2)
        row1.addWidget(QLabel("类型:"))
        row1.addWidget(self.type_edit, 1)
        fl.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        self.expiry_edit = QDateEdit()
        self.expiry_edit.setCalendarPopup(True)
        self.expiry_edit.setDisplayFormat("yyyy-MM-dd")
        self.expiry_edit.setDate(QDate.currentDate().addYears(1))
        self.expiry_edit.setFixedHeight(32)

        self.qty_edit = QDoubleSpinBox()
        self.qty_edit.setRange(0, 99999)
        self.qty_edit.setDecimals(2)
        self.qty_edit.setSuffix(" ml/g")
        self.qty_edit.setValue(1000)
        self.qty_edit.setFixedHeight(32)

        self.remark_edit = QLineEdit()
        self.remark_edit.setPlaceholderText("备注")
        self.remark_edit.setFixedHeight(32)

        row2.addWidget(QLabel("有效期至:"))
        row2.addWidget(self.expiry_edit)
        row2.addWidget(QLabel("数量:"))
        row2.addWidget(self.qty_edit)
        row2.addWidget(QLabel("备注:"))
        row2.addWidget(self.remark_edit, 1)
        fl.addLayout(row2)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("➕ 登记入库")
        self.add_btn.setStyleSheet(BTN_PRIMARY)
        self.add_btn.setFixedHeight(36)
        self.add_btn.clicked.connect(self.add_material)
        btn_row.addStretch()
        btn_row.addWidget(self.add_btn)
        fl.addLayout(btn_row)
        root.addWidget(form)

        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("筛选:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "有效库存", "已过期", "已召回"])
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        filter_bar.addWidget(self.filter_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索批号/名称/类型")
        self.search_edit.setFixedHeight(32)
        self.search_edit.textChanged.connect(self.refresh)
        filter_bar.addWidget(self.search_edit, 1)

        self.recall_btn = QPushButton("⚠ 标记召回")
        self.recall_btn.setStyleSheet(BTN_WARN)
        self.recall_btn.setFixedHeight(36)
        self.recall_btn.clicked.connect(self.mark_recall)

        self.check_expiry_btn = QPushButton("🔍 检查过期")
        self.check_expiry_btn.setStyleSheet(BTN_INFO)
        self.check_expiry_btn.setFixedHeight(36)
        self.check_expiry_btn.clicked.connect(self.check_expiry)

        self.refresh_btn = QPushButton("⟳ 刷新")
        self.refresh_btn.setFixedHeight(36)
        self.refresh_btn.clicked.connect(self.refresh)

        filter_bar.addWidget(self.recall_btn)
        filter_bar.addWidget(self.check_expiry_btn)
        filter_bar.addWidget(self.refresh_btn)
        root.addLayout(filter_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            ["ID", "批号", "名称", "类型", "有效期至", "剩余数量", "状态", "备注", "入库时间"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setStyleSheet(TABLE_STYLE)
        root.addWidget(self.table, 1)

        self.expiry_label = QLabel("")
        self.expiry_label.setStyleSheet("background:#ffebee;color:#c62828;padding:10px;border-radius:6px;")
        self.expiry_label.hide()
        root.addWidget(self.expiry_label)

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条记录")
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        return int(item.text())

    def add_material(self):
        batch = self.batch_edit.text().strip()
        name = self.name_edit.text().strip()
        if not batch or not name:
            QMessageBox.warning(self, "提示", "批号和名称为必填项")
            return
        mat_type = self.type_edit.text().strip()
        expiry = self.expiry_edit.date().toString("yyyy-MM-dd")
        qty = self.qty_edit.value()
        remark = self.remark_edit.text().strip()
        mid = db.add_material(batch, name, mat_type, expiry, qty, remark)
        if mid is None:
            QMessageBox.warning(self, "提示", f"批号 {batch} 已存在!")
            return
        self.batch_edit.clear()
        self.name_edit.clear()
        self.type_edit.clear()
        self.remark_edit.clear()
        self.qty_edit.setValue(1000)
        self.refresh()
        QMessageBox.information(self, "成功", f"批次 {batch} 登记成功")

    def mark_recall(self):
        mid = self._selected_id()
        if mid is None:
            return
        ret = QMessageBox.question(self, "确认", "确认标记此批次为召回状态?")
        if ret != QMessageBox.Yes:
            return
        db.update_material_status(mid, MATERIAL_STATUS_RECALL)
        self.refresh()

    def check_expiry(self):
        expired = db.check_expired_materials()
        if not expired:
            QMessageBox.information(self, "检查结果", "当前无即将/已经过期的批次")
            return
        for m in expired:
            db.update_material_status(m["id"], MATERIAL_STATUS_EXPIRED)
        self.expiry_label.setText(f"⚠ 已自动标记 {len(expired)} 个过期批次,请及时处理!")
        self.expiry_label.show()
        self.refresh()

    def refresh(self):
        self.expiry_label.hide()
        rows = db.get_materials()
        mode = self.filter_combo.currentIndex()
        keyword = self.search_edit.text().strip().lower()

        filtered = []
        for r in rows:
            if mode == 1 and r["status"] != MATERIAL_STATUS_ACTIVE:
                continue
            if mode == 2 and r["status"] != MATERIAL_STATUS_EXPIRED:
                continue
            if mode == 3 and r["status"] != MATERIAL_STATUS_RECALL:
                continue
            if keyword:
                text = f"{r.get('batch_no','')} {r.get('material_name','')} {r.get('material_type','')}".lower()
                if keyword not in text:
                    continue
            filtered.append(r)

        self.table.setRowCount(len(filtered))
        today = date.today().isoformat()
        for i, r in enumerate(filtered):
            self.table.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(r["batch_no"]))
            self.table.setItem(i, 2, QTableWidgetItem(r["material_name"]))
            self.table.setItem(i, 3, QTableWidgetItem(r.get("material_type") or ""))

            expiry = r.get("expiry_date") or ""
            exp_item = QTableWidgetItem(expiry)
            if expiry and expiry <= today:
                exp_item.setForeground(QColor("#c62828"))
                exp_item.setFont(QFont("", -1, QFont.Bold))
            self.table.setItem(i, 4, exp_item)

            self.table.setItem(i, 5, QTableWidgetItem(str(r.get("quantity", 0))))

            status_text, color = self._status_style(r["status"])
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(color))
            f = status_item.font()
            f.setBold(True)
            status_item.setFont(f)
            self.table.setItem(i, 6, status_item)

            self.table.setItem(i, 7, QTableWidgetItem(r.get("remark") or ""))
            self.table.setItem(i, 8, QTableWidgetItem(r.get("created_at") or ""))

    def _status_style(self, s):
        return {
            MATERIAL_STATUS_ACTIVE: ("库存正常", "#2e7d32"),
            MATERIAL_STATUS_EXPIRED: ("已过期", "#c62828"),
            MATERIAL_STATUS_RECALL: ("召回中", "#ef6c00"),
        }.get(s, (s, "#333"))


FRAME_STYLE = """
QFrame { background:#f5f7fa; border:1px solid #dde3ea; border-radius:8px; padding:12px; }
QLabel { color:#37474f; }
QLineEdit, QDateEdit, QDoubleSpinBox, QComboBox {
    background:white; border:1px solid #cfd8dc; border-radius:6px; padding:4px 8px;
}
"""
BTN_PRIMARY = """
QPushButton { background:#1976d2; color:white; border:none; border-radius:6px; padding:6px 20px; font-weight:bold; }
QPushButton:hover { background:#1565c0; }
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
