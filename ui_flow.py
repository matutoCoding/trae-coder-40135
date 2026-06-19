import os
import shutil
import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QFrame, QComboBox, QDoubleSpinBox, QFileDialog,
                               QTabWidget, QSplitter, QFormLayout, QDialog, QDialogButtonBox,
                               QListWidget, QListWidgetItem, QTextEdit, QAbstractItemView)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor, QPixmap
from PIL import Image
import db
from config import PHOTO_DIR, ensure_dirs


def save_photo(src_path):
    ensure_dirs()
    if not src_path or not os.path.isfile(src_path):
        return None
    ext = os.path.splitext(src_path)[1].lower() or ".jpg"
    new_name = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(PHOTO_DIR, new_name)
    try:
        img = Image.open(src_path)
        img.thumbnail((1280, 1280), Image.LANCZOS)
        img.save(dest, quality=85)
    except Exception:
        shutil.copy2(src_path, dest)
    return new_name


class FlowRecallModule(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh_orders()
        self.refresh_materials()
        self.refresh_flows()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("🔗 批次流向追踪与召回管理")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        root.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Microsoft YaHei", 10))
        root.addWidget(self.tabs, 1)

        self._build_order_tab()
        self._build_flow_tab()
        self._build_recall_tab()

    # ---------- 工单管理 Tab ----------
    def _build_order_tab(self):
        w = QWidget()
        lv = QVBoxLayout(w)
        lv.setSpacing(10)

        form = QFrame()
        form.setStyleSheet(FRAME_STYLE)
        fl = QHBoxLayout(form)
        fl.setSpacing(8)
        self.o_name = QLineEdit()
        self.o_name.setPlaceholderText("客户姓名")
        self.o_item = QLineEdit()
        self.o_item.setPlaceholderText("皮具物品描述")
        self.o_content = QLineEdit()
        self.o_content.setPlaceholderText("修复内容 (如:染色/补伤)")
        self.o_create_btn = QPushButton("➕ 新建工单")
        self.o_create_btn.setStyleSheet(BTN_PRIMARY)
        self.o_create_btn.clicked.connect(self.create_order)
        fl.addWidget(QLabel("姓名:"))
        fl.addWidget(self.o_name, 1)
        fl.addWidget(QLabel("物品:"))
        fl.addWidget(self.o_item, 2)
        fl.addWidget(QLabel("修复:"))
        fl.addWidget(self.o_content, 2)
        fl.addWidget(self.o_create_btn)
        lv.addWidget(form)

        split = QSplitter(Qt.Horizontal)
        lv.addWidget(split, 1)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("📋 修复工单列表"))
        self.order_table = QTableWidget()
        self.order_table.setColumnCount(6)
        self.order_table.setHorizontalHeaderLabels(["ID", "工单号", "客户", "物品", "修复内容", "创建时间"])
        self.order_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.order_table.verticalHeader().setVisible(False)
        self.order_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.order_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.order_table.setStyleSheet(TABLE_STYLE)
        self.order_table.itemSelectionChanged.connect(self.on_order_selected)
        ll.addWidget(self.order_table, 1)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("📷 修复前后留影"))

        photos = QFrame()
        photos.setStyleSheet("QFrame{background:#fafafa;border:1px solid #e0e0e0;border-radius:6px;padding:8px;}")
        pl = QHBoxLayout(photos)
        self.before_lbl = QLabel("修复前\n(点击上传)")
        self.before_lbl.setAlignment(Qt.AlignCenter)
        self.before_lbl.setMinimumSize(260, 200)
        self.before_lbl.setStyleSheet(PHOTO_LBL_STYLE)
        self.before_lbl.setCursor(Qt.PointingHandCursor)
        self.before_lbl.mousePressEvent = lambda e: self.upload_photo("before")

        self.after_lbl = QLabel("修复后\n(点击上传)")
        self.after_lbl.setAlignment(Qt.AlignCenter)
        self.after_lbl.setMinimumSize(260, 200)
        self.after_lbl.setStyleSheet(PHOTO_LBL_STYLE)
        self.after_lbl.setCursor(Qt.PointingHandCursor)
        self.after_lbl.mousePressEvent = lambda e: self.upload_photo("after")

        pl.addWidget(self.before_lbl)
        pl.addWidget(self.after_lbl)
        rl.addWidget(photos)

        mat_frame = QFrame()
        mat_frame.setStyleSheet(FRAME_STYLE)
        ml = QVBoxLayout(mat_frame)
        ml.addWidget(QLabel("🧴 登记本工单使用的材料批次"))

        mrow = QHBoxLayout()
        self.mat_combo = QComboBox()
        self.mat_combo.setMinimumHeight(32)
        self.mat_amt = QDoubleSpinBox()
        self.mat_amt.setRange(0, 99999)
        self.mat_amt.setDecimals(2)
        self.mat_amt.setSuffix(" ml/g")
        self.mat_amt.setValue(10)
        self.mat_add_btn = QPushButton("登记使用")
        self.mat_add_btn.setStyleSheet(BTN_PRIMARY)
        self.mat_add_btn.clicked.connect(self.add_material_usage)
        mrow.addWidget(QLabel("选择批次:"))
        mrow.addWidget(self.mat_combo, 2)
        mrow.addWidget(QLabel("用量:"))
        mrow.addWidget(self.mat_amt)
        mrow.addWidget(self.mat_add_btn)
        ml.addLayout(mrow)

        self.used_list = QListWidget()
        self.used_list.setStyleSheet("QListWidget{background:white;border:1px solid #dde3ea;border-radius:6px;padding:4px;}")
        ml.addWidget(self.used_list, 1)
        rl.addWidget(mat_frame, 1)

        split.addWidget(right)
        split.setSizes([500, 520])

        self.tabs.addTab(w, "📋 工单 & 留影")

    # ---------- 流向记录 Tab ----------
    def _build_flow_tab(self):
        w = QWidget()
        lv = QVBoxLayout(w)
        lv.setSpacing(10)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("筛选:"))
        self.flow_filter = QComboBox()
        self.flow_filter.addItems(["全部流向", "按工单", "按批次"])
        self.flow_filter.currentIndexChanged.connect(self.refresh_flows)
        bar.addWidget(self.flow_filter)
        self.flow_keyword = QLineEdit()
        self.flow_keyword.setPlaceholderText("输入工单号或批号过滤")
        self.flow_keyword.textChanged.connect(self.refresh_flows)
        bar.addWidget(self.flow_keyword, 1)
        refresh_btn = QPushButton("⟳ 刷新")
        refresh_btn.clicked.connect(self.refresh_flows)
        bar.addWidget(refresh_btn)
        lv.addLayout(bar)

        self.flow_table = QTableWidget()
        self.flow_table.setColumnCount(8)
        self.flow_table.setHorizontalHeaderLabels(
            ["ID", "批次号", "材料名称", "工单号", "客户姓名", "用量", "使用时间", "状态"]
        )
        self.flow_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.flow_table.verticalHeader().setVisible(False)
        self.flow_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.flow_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.flow_table.setStyleSheet(TABLE_STYLE)
        lv.addWidget(self.flow_table, 1)

        self.tabs.addTab(w, "📊 材料流向记录")

    # ---------- 召回查询 Tab ----------
    def _build_recall_tab(self):
        w = QWidget()
        lv = QVBoxLayout(w)
        lv.setSpacing(10)

        search = QFrame()
        search.setStyleSheet(FRAME_STYLE)
        sl = QHBoxLayout(search)
        sl.addWidget(QLabel("🔍 输入问题批号反查受影响客户:"))
        self.recall_batch = QLineEdit()
        self.recall_batch.setPlaceholderText("如 RL20250601-01")
        self.recall_batch.setMinimumHeight(36)
        self.recall_btn = QPushButton("查询召回名单")
        self.recall_btn.setStyleSheet(BTN_DANGER)
        self.recall_btn.setMinimumHeight(36)
        self.recall_btn.clicked.connect(self.do_recall_search)
        sl.addWidget(self.recall_batch, 2)
        sl.addWidget(self.recall_btn)
        lv.addWidget(search)

        self.recall_summary = QLabel("请输入批号并查询,将列出所有使用该批次的客户货品。")
        self.recall_summary.setStyleSheet("padding:10px;background:#fff3e0;color:#e65100;border-radius:6px;font-weight:bold;")
        self.recall_summary.hide()
        lv.addWidget(self.recall_summary)

        self.recall_table = QTableWidget()
        self.recall_table.setColumnCount(7)
        self.recall_table.setHorizontalHeaderLabels(
            ["工单号", "客户姓名", "物品描述", "修复内容", "批次用量", "使用时间", "联系信息"]
        )
        self.recall_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.recall_table.verticalHeader().setVisible(False)
        self.recall_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recall_table.setStyleSheet(TABLE_STYLE)
        lv.addWidget(self.recall_table, 1)

        self.tabs.addTab(w, "⚠ 批次召回查询")

    # ---------- 业务逻辑 ----------
    def create_order(self):
        name = self.o_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入客户姓名")
            return
        item = self.o_item.text().strip()
        content = self.o_content.text().strip()
        rid, ono = db.add_repair_order(None, name, item, content)
        self.o_name.clear()
        self.o_item.clear()
        self.o_content.clear()
        self.refresh_orders()
        QMessageBox.information(self, "成功", f"已创建工单: {ono}")

    def refresh_orders(self):
        prev_id = None
        row = self.order_table.currentRow()
        if row >= 0:
            it = self.order_table.item(row, 0)
            if it:
                prev_id = int(it.text())

        rows = db.get_repair_orders()
        self.order_table.setRowCount(len(rows))
        target_row = -1
        for i, r in enumerate(rows):
            self.order_table.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.order_table.setItem(i, 1, QTableWidgetItem(r["order_no"]))
            self.order_table.setItem(i, 2, QTableWidgetItem(r["customer_name"] or ""))
            self.order_table.setItem(i, 3, QTableWidgetItem(r.get("item_desc") or ""))
            self.order_table.setItem(i, 4, QTableWidgetItem(r.get("repair_content") or ""))
            self.order_table.setItem(i, 5, QTableWidgetItem(r.get("created_at") or ""))
            if prev_id is not None and r["id"] == prev_id:
                target_row = i

        if target_row >= 0:
            self.order_table.selectRow(target_row)
        elif self.order_table.rowCount() > 0 and row < 0:
            self.order_table.selectRow(0)

    def refresh_materials(self):
        mats = db.get_materials()
        self.mat_combo.clear()
        for m in mats:
            label = f"{m['batch_no']} | {m['material_name']} ({m.get('material_type') or '-'})"
            self.mat_combo.addItem(label, m)

    def on_order_selected(self):
        self._current_order = self._selected_order()
        if not self._current_order:
            return
        self._show_photos(self._current_order.get("before_photo"), self._current_order.get("after_photo"))
        self._load_used_materials(self._current_order["id"])

    def _selected_order(self):
        row = self.order_table.currentRow()
        if row < 0:
            return None
        rid = int(self.order_table.item(row, 0).text())
        for o in db.get_repair_orders():
            if o["id"] == rid:
                return o
        return None

    def _show_photos(self, before, after):
        for lbl, name in [(self.before_lbl, before), (self.after_lbl, after)]:
            if name:
                path = os.path.join(PHOTO_DIR, name)
                if os.path.isfile(path):
                    pix = QPixmap(path)
                    lbl.setPixmap(pix.scaled(lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    continue
            lbl.setText(("修复前\n(点击上传)" if lbl is self.before_lbl else "修复后\n(点击上传)"))
            lbl.setStyleSheet(PHOTO_LBL_STYLE)

    def upload_photo(self, which):
        order = self._selected_order()
        if not order:
            QMessageBox.information(self, "提示", "请先选择一个工单")
            return
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "图片文件 (*.jpg *.jpeg *.png *.bmp)")
        if not path:
            return
        saved = save_photo(path)
        if not saved:
            QMessageBox.warning(self, "失败", "图片保存失败")
            return
        if which == "before":
            db.update_repair_photos(order["id"], before_photo=saved)
        else:
            db.update_repair_photos(order["id"], after_photo=saved)
        self.refresh_orders()
        self.on_order_selected()

    def add_material_usage(self):
        order = self._selected_order()
        if not order:
            QMessageBox.information(self, "提示", "请先选择一个工单")
            return
        data = self.mat_combo.currentData()
        if not data:
            QMessageBox.information(self, "提示", "请先在「材料批次」中登记批次")
            return
        amount = self.mat_amt.value()
        db.add_material_flow(
            material_id=data["id"],
            batch_no=data["batch_no"],
            repair_order_id=order["id"],
            order_no=order["order_no"],
            customer_id=order.get("customer_id"),
            customer_name=order["customer_name"],
            usage_amount=amount,
        )
        self._load_used_materials(order["id"])
        self.refresh_flows()
        QMessageBox.information(self, "成功", f"已登记使用批次 {data['batch_no']}")

    def _load_used_materials(self, order_id):
        self.used_list.clear()
        flows = db.get_flow_by_repair_order_id(order_id)
        mats = {m["id"]: m for m in db.get_materials()}
        if not flows:
            tip = QListWidgetItem("(此工单尚未登记使用的材料)", self.used_list)
            tip.setForeground(QColor("#90a4ae"))
            return
        for f in flows:
            m = mats.get(f["material_id"], {})
            mat_name = m.get("material_name", "")
            mat_type = m.get("material_type") or ""
            name_str = f"{mat_name}"
            if mat_type:
                name_str += f" [{mat_type}]"
            amt = f.get("usage_amount", 0)
            used_at = f.get("used_at") or ""
            text = (
                f"📦 批号: {f['batch_no']}\n"
                f"   名称: {name_str}\n"
                f"   用量: {amt} ml/g        时间: {used_at}"
            )
            item = QListWidgetItem(text, self.used_list)
            item.setForeground(QColor("#263238"))

    def refresh_flows(self):
        mode = self.flow_filter.currentIndex()
        kw = self.flow_keyword.text().strip()
        flows = []
        if mode == 1 and kw:
            flows = db.get_flow_by_order(kw)
        elif mode == 2 and kw:
            flows = db.get_flow_by_material(batch_no=kw)
        else:
            flows = db.get_flow_by_material()
        mats = {m["id"]: m for m in db.get_materials()}
        self.flow_table.setRowCount(len(flows))
        for i, f in enumerate(flows):
            m = mats.get(f["material_id"], {})
            self.flow_table.setItem(i, 0, QTableWidgetItem(str(f["id"])))
            self.flow_table.setItem(i, 1, QTableWidgetItem(f["batch_no"]))
            self.flow_table.setItem(i, 2, QTableWidgetItem(m.get("material_name", "")))
            self.flow_table.setItem(i, 3, QTableWidgetItem(f["order_no"]))
            self.flow_table.setItem(i, 4, QTableWidgetItem(f.get("customer_name") or ""))
            self.flow_table.setItem(i, 5, QTableWidgetItem(str(f.get("usage_amount") or 0)))
            self.flow_table.setItem(i, 6, QTableWidgetItem(f.get("used_at") or ""))

            status, color = "正常", "#2e7d32"
            if m.get("status") == "expired":
                status, color = "材料已过期", "#c62828"
            elif m.get("status") == "recall":
                status, color = "召回中", "#ef6c00"
            item = QTableWidgetItem(status)
            item.setForeground(QColor(color))
            f = item.font()
            f.setBold(True)
            item.setFont(f)
            self.flow_table.setItem(i, 7, item)

    def do_recall_search(self):
        batch = self.recall_batch.text().strip()
        if not batch:
            QMessageBox.warning(self, "提示", "请输入批号")
            return
        flows = db.get_flow_by_material(batch_no=batch)
        if not flows:
            self.recall_summary.setText(f"未找到批号「{batch}」的使用记录。")
            self.recall_summary.show()
            self.recall_table.setRowCount(0)
            return
        orders = {o["id"]: o for o in db.get_repair_orders()}
        self.recall_table.setRowCount(len(flows))
        affected_customers = set()
        for i, f in enumerate(flows):
            o = orders.get(f["repair_order_id"], {})
            self.recall_table.setItem(i, 0, QTableWidgetItem(f["order_no"]))
            self.recall_table.setItem(i, 1, QTableWidgetItem(f.get("customer_name") or o.get("customer_name") or ""))
            self.recall_table.setItem(i, 2, QTableWidgetItem(o.get("item_desc") or ""))
            self.recall_table.setItem(i, 3, QTableWidgetItem(o.get("repair_content") or ""))
            self.recall_table.setItem(i, 4, QTableWidgetItem(str(f.get("usage_amount") or 0)))
            self.recall_table.setItem(i, 5, QTableWidgetItem(f.get("used_at") or ""))
            customers = db.get_customers()
            contact = ""
            for c in customers:
                if c["name"] == (f.get("customer_name") or o.get("customer_name")):
                    contact = c.get("phone") or ""
                    break
            self.recall_table.setItem(i, 6, QTableWidgetItem(contact))
            if f.get("customer_name"):
                affected_customers.add(f["customer_name"])

        self.recall_summary.setText(
            f"⚠ 批号「{batch}」共影响 {len(flows)} 单 / {len(affected_customers)} 位客户,请尽快通知召回!"
        )
        self.recall_summary.show()


FRAME_STYLE = """
QFrame { background:#f5f7fa; border:1px solid #dde3ea; border-radius:8px; padding:10px; }
QLabel { color:#37474f; }
QLineEdit, QComboBox, QDoubleSpinBox {
    background:white; border:1px solid #cfd8dc; border-radius:6px; padding:4px 8px;
}
"""
BTN_PRIMARY = """
QPushButton { background:#1976d2; color:white; border:none; border-radius:6px; padding:6px 16px; }
QPushButton:hover { background:#1565c0; }
"""
BTN_DANGER = """
QPushButton { background:#c62828; color:white; border:none; border-radius:6px; padding:6px 20px; font-weight:bold; }
QPushButton:hover { background:#b71c1c; }
"""
TABLE_STYLE = """
QTableWidget { background:white; border:1px solid #dde3ea; border-radius:6px; gridline-color:#eceff1; }
QHeaderView::section { background:#eceff1; padding:8px; border:none; border-bottom:2px solid #cfd8dc; font-weight:bold; }
QTableWidget::item { padding:6px; }
"""
PHOTO_LBL_STYLE = """
QLabel {
    background:#eceff1; border:2px dashed #90a4ae; border-radius:8px;
    color:#546e7a; font-size:14px;
}
"""
