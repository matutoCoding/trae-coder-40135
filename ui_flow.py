import os
import shutil
import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QFrame, QComboBox, QDoubleSpinBox, QFileDialog,
                               QTabWidget, QSplitter, QFormLayout, QDialog, QDialogButtonBox,
                               QListWidget, QListWidgetItem, QTextEdit, QAbstractItemView,
                               QInputDialog)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor, QPixmap
from PIL import Image
import db
from config import (PHOTO_DIR, ensure_dirs, RECALL_STATUS_LABELS, RECALL_STATUS_COLORS,
                    RECALL_STATUS_PENDING, RECALL_STATUS_NOTIFIED, RECALL_STATUS_IN_STORE,
                    RECALL_STATUS_CLOSED)


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


class PhoneEditDialog(QDialog):
    def __init__(self, missing_rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量补录联系电话")
        self.resize(640, 480)
        self._rows = missing_rows
        self._edits = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.addWidget(QLabel("以下客户缺少联系电话,请补录(可留空表示跳过该客户):"))

        self.phone_table = QTableWidget()
        self.phone_table.setColumnCount(4)
        self.phone_table.setHorizontalHeaderLabels(["流水号", "工单号", "客户姓名", "联系电话"])
        self.phone_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.phone_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.phone_table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            fid = r["id"]
            self.phone_table.setItem(i, 0, QTableWidgetItem(str(fid)))
            self.phone_table.setItem(i, 1, QTableWidgetItem(r.get("order_no", "")))
            self.phone_table.setItem(i, 2, QTableWidgetItem(r.get("customer_name", "")))
            edit = QLineEdit()
            edit.setPlaceholderText("请输入联系电话")
            self._edits[fid] = edit
            self.phone_table.setCellWidget(i, 3, edit)
        root.addWidget(self.phone_table, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def get_phone_updates(self):
        updates = {}
        for fid, edit in self._edits.items():
            v = edit.text().strip()
            if v:
                updates[fid] = v
        return updates


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
        self._build_customer_tab()

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
        self.o_phone = QLineEdit()
        self.o_phone.setPlaceholderText("联系电话")
        self.o_item = QLineEdit()
        self.o_item.setPlaceholderText("皮具物品描述")
        self.o_content = QLineEdit()
        self.o_content.setPlaceholderText("修复内容 (如:染色/补伤)")
        self.o_create_btn = QPushButton("➕ 新建工单")
        self.o_create_btn.setStyleSheet(BTN_PRIMARY)
        self.o_create_btn.clicked.connect(self.create_order)
        self.o_name.editingFinished.connect(self._autofill_phone)
        fl.addWidget(QLabel("姓名:"))
        fl.addWidget(self.o_name, 1)
        fl.addWidget(QLabel("电话:"))
        fl.addWidget(self.o_phone, 1)
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
        self.order_table.setColumnCount(7)
        self.order_table.setHorizontalHeaderLabels(["ID", "工单号", "客户", "电话", "物品", "修复内容", "创建时间"])
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
        self.flow_table.setColumnCount(10)
        self.flow_table.setHorizontalHeaderLabels(
            ["ID", "批次号", "材料名称", "工单号", "客户姓名", "电话", "用量", "使用时间", "召回状态", "状态"]
        )
        self.flow_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.flow_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
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
        sl = QVBoxLayout(search)
        sl.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.recall_name = QLineEdit()
        self.recall_name.setPlaceholderText("客户姓名 (模糊匹配)")
        self.recall_name.setFixedHeight(32)
        self.recall_order = QLineEdit()
        self.recall_order.setPlaceholderText("工单号 (模糊匹配)")
        self.recall_order.setFixedHeight(32)
        self.recall_batch = QLineEdit()
        self.recall_batch.setPlaceholderText("材料批号 (模糊匹配)")
        self.recall_batch.setFixedHeight(32)
        self.recall_mat = QLineEdit()
        self.recall_mat.setPlaceholderText("材料名称 (模糊匹配)")
        self.recall_mat.setFixedHeight(32)
        row1.addWidget(QLabel("姓名:"))
        row1.addWidget(self.recall_name, 1)
        row1.addWidget(QLabel("工单号:"))
        row1.addWidget(self.recall_order, 1)
        row1.addWidget(QLabel("批号:"))
        row1.addWidget(self.recall_batch, 1)
        row1.addWidget(QLabel("材料名:"))
        row1.addWidget(self.recall_mat, 1)
        sl.addLayout(row1)

        row2 = QHBoxLayout()
        self.recall_search_btn = QPushButton("🔍 查询")
        self.recall_search_btn.setStyleSheet(BTN_PRIMARY)
        self.recall_search_btn.setFixedHeight(36)
        self.recall_search_btn.clicked.connect(self.do_recall_search)

        self.recall_edit_phone_btn = QPushButton("📞 批量补录电话")
        self.recall_edit_phone_btn.setStyleSheet(BTN_WARN)
        self.recall_edit_phone_btn.setFixedHeight(36)
        self.recall_edit_phone_btn.clicked.connect(self.batch_edit_phones)

        self.recall_export_btn = QPushButton("📤 导出召回名单(CSV)")
        self.recall_export_btn.setStyleSheet(BTN_SUCCESS)
        self.recall_export_btn.setFixedHeight(36)
        self.recall_export_btn.clicked.connect(self.export_recall_list)

        self.recall_clear_btn = QPushButton("清空条件")
        self.recall_clear_btn.setFixedHeight(36)
        self.recall_clear_btn.clicked.connect(self.clear_recall_filters)

        row2.addStretch()
        row2.addWidget(self.recall_clear_btn)
        row2.addWidget(self.recall_edit_phone_btn)
        row2.addWidget(self.recall_search_btn)
        row2.addWidget(self.recall_export_btn)
        sl.addLayout(row2)
        lv.addWidget(search)

        self.recall_summary = QLabel("请输入查询条件并查询,将列出符合条件的所有材料流向记录。")
        self.recall_summary.setStyleSheet(
            "padding:10px;background:#fff3e0;color:#e65100;border-radius:6px;font-weight:bold;"
        )
        self.recall_summary.hide()
        lv.addWidget(self.recall_summary)

        self.recall_table = QTableWidget()
        self.recall_table.setColumnCount(12)
        headers = ["流水号", "工单号", "客户姓名", "联系电话", "物品描述",
                   "修复内容", "材料批号", "材料名称", "用量", "使用时间",
                   "召回状态", "备注"]
        self.recall_table.setHorizontalHeaderLabels(headers)
        self.recall_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.recall_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.recall_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.recall_table.verticalHeader().setVisible(False)
        self.recall_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        self.recall_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.recall_table.setStyleSheet(TABLE_STYLE)
        self.recall_table.cellDoubleClicked.connect(self.on_recall_cell_double_clicked)
        self.recall_table.cellChanged.connect(self.on_recall_cell_changed)
        self._recall_updating = False
        lv.addWidget(self.recall_table, 1)

        self._last_recall_results = []
        self.tabs.addTab(w, "⚠ 批次召回查询")

    # ---------- 客户档案 Tab ----------
    def _build_customer_tab(self):
        w = QWidget()
        lv = QVBoxLayout(w)
        lv.setSpacing(10)

        search_bar = QFrame()
        search_bar.setStyleSheet(FRAME_STYLE)
        sl = QHBoxLayout(search_bar)
        sl.setSpacing(8)
        sl.addWidget(QLabel("搜索:"))
        self.cust_kw = QLineEdit()
        self.cust_kw.setPlaceholderText("输入客户姓名或电话搜索")
        self.cust_kw.setFixedHeight(34)
        self.cust_kw.returnPressed.connect(self.refresh_customer_list)
        sl.addWidget(self.cust_kw, 1)
        cust_search_btn = QPushButton("🔍 查找")
        cust_search_btn.setFixedHeight(34)
        cust_search_btn.setStyleSheet(BTN_PRIMARY)
        cust_search_btn.clicked.connect(self.refresh_customer_list)
        sl.addWidget(cust_search_btn)
        lv.addWidget(search_bar)

        split = QSplitter(Qt.Horizontal)
        lv.addWidget(split, 1)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("👥 客户档案列表"))
        self.cust_table = QTableWidget()
        self.cust_table.setColumnCount(4)
        self.cust_table.setHorizontalHeaderLabels(["ID", "客户姓名", "联系电话", "建档时间"])
        self.cust_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cust_table.verticalHeader().setVisible(False)
        self.cust_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cust_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cust_table.setStyleSheet(TABLE_STYLE)
        self.cust_table.itemSelectionChanged.connect(self.on_customer_selected)
        ll.addWidget(self.cust_table, 1)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("📁 客户详细档案"))

        self.cust_info = QLabel("(请在左侧选择客户)")
        self.cust_info.setStyleSheet(
            "QLabel{background:white;border:1px solid #dde3ea;border-radius:6px;padding:12px;font-size:14px;}"
        )
        rl.addWidget(self.cust_info)

        self.cust_tabs = QTabWidget()
        rl.addWidget(self.cust_tabs, 1)

        self.cust_queue_tab = self._build_cust_sub_table(
            ["排队号", "物品描述", "状态", "过号次数", "取号时间"])
        self.cust_order_tab = self._build_cust_sub_table(
            ["工单号", "物品", "修复内容", "状态", "创建时间"])
        self.cust_flow_tab = self._build_cust_sub_table(
            ["工单号", "批号", "材料名称", "用量", "使用时间", "召回状态"])

        self.cust_tabs.addTab(self.cust_queue_tab["container"], "🕐 排队记录")
        self.cust_tabs.addTab(self.cust_order_tab["container"], "📋 工单记录")
        self.cust_tabs.addTab(self.cust_flow_tab["container"], "🧴 用料批次")

        split.addWidget(right)
        split.setSizes([360, 640])

        self.tabs.addTab(w, "👥 客户档案")
        self.refresh_customer_list()

    def _build_cust_sub_table(self, headers):
        container = QWidget()
        lv = QVBoxLayout(container)
        lv.setContentsMargins(0, 8, 0, 0)
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setStyleSheet(TABLE_STYLE)
        lv.addWidget(table)
        return {"container": container, "table": table}

    # ---------- 业务逻辑 ----------
    def _autofill_phone(self):
        name = self.o_name.text().strip()
        if not name:
            return
        exist = db.find_customer_by_name(name)
        if exist and exist.get("phone"):
            if not self.o_phone.text().strip():
                self.o_phone.setText(exist["phone"])

    def create_order(self):
        name = self.o_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入客户姓名")
            return
        phone = self.o_phone.text().strip()
        item = self.o_item.text().strip()
        content = self.o_content.text().strip()
        customer_id = None
        exist = db.find_customer_by_name(name)
        if exist:
            customer_id = exist["id"]
            if not phone and exist.get("phone"):
                phone = exist["phone"]
        else:
            if phone or item:
                customer_id = db.add_customer(name, phone=phone, item_desc=item)
        rid, ono = db.add_repair_order(customer_id, name, phone, item, content)
        self.o_name.clear()
        self.o_phone.clear()
        self.o_item.clear()
        self.o_content.clear()
        self.refresh_orders()
        self.refresh_customer_list()
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
            self.order_table.setItem(i, 3, QTableWidgetItem(r.get("customer_phone") or ""))
            self.order_table.setItem(i, 4, QTableWidgetItem(r.get("item_desc") or ""))
            self.order_table.setItem(i, 5, QTableWidgetItem(r.get("repair_content") or ""))
            self.order_table.setItem(i, 6, QTableWidgetItem(r.get("created_at") or ""))
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
        phone = order.get("customer_phone") or ""
        if not phone:
            exist = db.find_customer_by_name(order.get("customer_name", ""))
            if exist and exist.get("phone"):
                phone = exist["phone"]
        fid, msg = db.add_material_flow_with_consume(
            material_id=data["id"],
            batch_no=data["batch_no"],
            repair_order_id=order["id"],
            order_no=order["order_no"],
            customer_id=order.get("customer_id"),
            customer_name=order["customer_name"],
            customer_phone=phone,
            usage_amount=amount,
        )
        if fid is None:
            QMessageBox.warning(self, "登记失败", f"{msg}\n\n请检查库存或换一个批次使用。")
            return
        self._load_used_materials(order["id"])
        self.refresh_flows()
        self.refresh_materials()
        QMessageBox.information(self, "成功",
                                f"已登记使用批次 {data['batch_no']}\n"
                                f"用量: {amount} ml/g\n"
                                f"剩余库存: {db.get_material_by_id(data['id'])['quantity']} ml/g")

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
            self.flow_table.setItem(i, 5, QTableWidgetItem(f.get("customer_phone") or ""))
            self.flow_table.setItem(i, 6, QTableWidgetItem(str(f.get("usage_amount") or 0)))
            self.flow_table.setItem(i, 7, QTableWidgetItem(f.get("used_at") or ""))

            rs = f.get("recall_status") or RECALL_STATUS_PENDING
            rs_text = RECALL_STATUS_LABELS.get(rs, rs)
            rs_color = RECALL_STATUS_COLORS.get(rs, "#333")
            rs_item = QTableWidgetItem(rs_text)
            rs_item.setForeground(QColor(rs_color))
            rsf = rs_item.font()
            rsf.setBold(True)
            rs_item.setFont(rsf)
            self.flow_table.setItem(i, 8, rs_item)

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
            self.flow_table.setItem(i, 9, item)

    def do_recall_search(self):
        name = self.recall_name.text().strip()
        order = self.recall_order.text().strip()
        batch = self.recall_batch.text().strip()
        mat = self.recall_mat.text().strip()

        if not name and not order and not batch and not mat:
            ret = QMessageBox.question(self, "提示",
                                        "未填写任何查询条件,将显示全部流向记录。是否继续?")
            if ret != QMessageBox.Yes:
                return

        flows = db.get_flows_combined(
            customer_name=name,
            order_no=order,
            batch_no=batch,
            material_name=mat,
        )
        self._last_recall_results = flows
        self._render_recall_table(flows)

        missing = [r for r in flows if not r.get("customer_phone")]
        customers_set = set()
        orders_set = set()
        for r in flows:
            if r.get("customer_name"):
                customers_set.add(r["customer_name"])
            orders_set.add(r["order_no"])

        if flows:
            desc_parts = []
            if batch:
                desc_parts.append(f"批号「{batch}」")
            if name:
                desc_parts.append(f"客户「{name}」")
            if order:
                desc_parts.append(f"工单「{order}」")
            if mat:
                desc_parts.append(f"材料「{mat}」")
            desc = "、".join(desc_parts) if desc_parts else "全部"
            miss_txt = f" ⚠ {len(missing)}条缺电话" if missing else ""
            self.recall_summary.setText(
                f"⚠ {desc} 共 {len(flows)} 条流向 / {len(orders_set)} 单 / {len(customers_set)} 位客户{miss_txt},请尽快通知召回!"
            )
            self.recall_summary.show()
        else:
            self.recall_summary.setText("未找到符合条件的使用记录。")
            self.recall_summary.show()

    def _render_recall_table(self, flows):
        self._recall_updating = True
        self.recall_table.blockSignals(True)
        self.recall_table.setRowCount(len(flows))
        for i, f in enumerate(flows):
            fid = f["id"]
            self.recall_table.setItem(i, 0, QTableWidgetItem(str(fid)))
            self.recall_table.setItem(i, 1, QTableWidgetItem(f["order_no"]))
            self.recall_table.setItem(i, 2, QTableWidgetItem(f.get("customer_name") or ""))
            phone_text = f.get("customer_phone") or ""
            phone_item = QTableWidgetItem(phone_text)
            if not phone_text:
                phone_item.setForeground(QColor("#c62828"))
                pf = phone_item.font()
                pf.setBold(True)
                phone_item.setFont(pf)
                phone_item.setText("(缺电话 - 双击补录)")
            self.recall_table.setItem(i, 3, phone_item)
            self.recall_table.setItem(i, 4, QTableWidgetItem(f.get("item_desc") or ""))
            self.recall_table.setItem(i, 5, QTableWidgetItem(f.get("repair_content") or ""))
            self.recall_table.setItem(i, 6, QTableWidgetItem(f["batch_no"]))
            self.recall_table.setItem(i, 7, QTableWidgetItem(f.get("material_name") or ""))
            self.recall_table.setItem(i, 8, QTableWidgetItem(str(f.get("usage_amount") or 0)))
            self.recall_table.setItem(i, 9, QTableWidgetItem(f.get("used_at") or ""))

            rs = f.get("recall_status") or RECALL_STATUS_PENDING
            rs_combo = QComboBox()
            status_list = [
                (RECALL_STATUS_PENDING, RECALL_STATUS_LABELS[RECALL_STATUS_PENDING]),
                (RECALL_STATUS_NOTIFIED, RECALL_STATUS_LABELS[RECALL_STATUS_NOTIFIED]),
                (RECALL_STATUS_IN_STORE, RECALL_STATUS_LABELS[RECALL_STATUS_IN_STORE]),
                (RECALL_STATUS_CLOSED, RECALL_STATUS_LABELS[RECALL_STATUS_CLOSED]),
            ]
            for k, label in status_list:
                rs_combo.addItem(label, k)
            for idx, (k, _) in enumerate(status_list):
                if k == rs:
                    rs_combo.setCurrentIndex(idx)
                    break
            rs_combo.setStyleSheet(f"color:{RECALL_STATUS_COLORS.get(rs,'#333')};font-weight:bold;")
            rs_combo.currentIndexChanged.connect(
                lambda idx, fid2=fid, combo=rs_combo: self._on_recall_status_changed(fid2, combo)
            )
            self.recall_table.setCellWidget(i, 10, rs_combo)

            remark_text = f.get("recall_remark") or ""
            self.recall_table.setItem(i, 11, QTableWidgetItem(remark_text))
        self.recall_table.blockSignals(False)
        self._recall_updating = False

    def _on_recall_status_changed(self, fid, combo):
        if self._recall_updating:
            return
        status_key = combo.currentData()
        combo.setStyleSheet(f"color:{RECALL_STATUS_COLORS.get(status_key,'#333')};font-weight:bold;")
        row = -1
        for i in range(self.recall_table.rowCount()):
            it = self.recall_table.item(i, 0)
            if it and int(it.text()) == fid:
                row = i
                break
        remark = ""
        if row >= 0:
            rit = self.recall_table.item(row, 11)
            if rit:
                remark = rit.text().strip()
        db.update_flow_recall_status(fid, status_key, remark)
        # 同步 _last_recall_results
        for r in self._last_recall_results:
            if r["id"] == fid:
                r["recall_status"] = status_key
                r["recall_remark"] = remark
                break

    def on_recall_cell_double_clicked(self, row, col):
        if col != 3:
            return
        fid_item = self.recall_table.item(row, 0)
        if not fid_item:
            return
        fid = int(fid_item.text())
        customer_name = self.recall_table.item(row, 2).text() if self.recall_table.item(row, 2) else ""
        old_phone = self.recall_table.item(row, 3).text()
        if old_phone.startswith("(缺电话"):
            old_phone = ""
        phone, ok = QInputDialog.getText(self, "补录联系电话",
                                         f"请输入客户「{customer_name}」的联系电话:",
                                         text=old_phone)
        if not ok:
            return
        phone = phone.strip()
        if not phone:
            return
        db.update_flow_phone(fid, phone)
        phone_item = QTableWidgetItem(phone)
        self.recall_table.setItem(row, 3, phone_item)
        for r in self._last_recall_results:
            if r["id"] == fid:
                r["customer_phone"] = phone
                break
        self.refresh_flows()
        self.refresh_customer_list()

    def on_recall_cell_changed(self, row, col):
        if self._recall_updating:
            return
        if col != 11:
            return
        fid_item = self.recall_table.item(row, 0)
        if not fid_item:
            return
        fid = int(fid_item.text())
        remark = self.recall_table.item(row, 11).text().strip() if self.recall_table.item(row, 11) else ""
        row2 = self.recall_table.cellWidget(row, 10)
        status_key = RECALL_STATUS_PENDING
        if isinstance(row2, QComboBox):
            status_key = row2.currentData()
        db.update_flow_recall_status(fid, status_key, remark)
        for r in self._last_recall_results:
            if r["id"] == fid:
                r["recall_remark"] = remark
                break

    def batch_edit_phones(self):
        missing = [r for r in self._last_recall_results if not r.get("customer_phone")]
        if not missing:
            QMessageBox.information(self, "提示", "当前查询结果中没有缺电话的记录,无需补录!")
            return
        dlg = PhoneEditDialog(missing, self)
        if dlg.exec() != QDialog.Accepted:
            return
        updates = dlg.get_phone_updates()
        if not updates:
            return
        for fid, phone in updates.items():
            db.update_flow_phone(fid, phone)
            for r in self._last_recall_results:
                if r["id"] == fid:
                    r["customer_phone"] = phone
                    break
        self._render_recall_table(self._last_recall_results)
        self.refresh_flows()
        self.refresh_customer_list()
        still_missing = [r for r in self._last_recall_results if not r.get("customer_phone")]
        QMessageBox.information(self, "完成",
                                f"已补录 {len(updates)} 条联系电话。\n"
                                f"剩余 {len(still_missing)} 条缺电话记录。")

    def export_recall_list(self):
        if not self._last_recall_results:
            QMessageBox.information(self, "提示", "请先查询出结果后再导出")
            return
        missing = [r for r in self._last_recall_results if not r.get("customer_phone")]
        if missing:
            names = "、".join({r.get("customer_name") or "(未知)" for r in missing})
            ret = QMessageBox.warning(
                self, "还有电话缺失",
                f"仍有 {len(missing)} 条记录的联系电话缺失,包括客户: {names}。\n\n"
                f"选择操作:\n"
                f"  [是] = 跳过这些缺电话的记录,仅导出有电话的\n"
                f"  [否] = 返回补录,暂不导出\n"
                f"  [取消] = 直接导出全部(包含空电话行)",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            if ret == QMessageBox.No:
                return
            final_rows = [r for r in self._last_recall_results if r.get("customer_phone")] if ret == QMessageBox.Yes \
                else self._last_recall_results
        else:
            final_rows = self._last_recall_results

        if not final_rows:
            QMessageBox.information(self, "提示", "没有可导出的记录(所有记录都缺电话)。\n请先补录电话再导出。")
            return

        from datetime import datetime
        default_name = f"召回名单_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "导出召回名单", default_name, "CSV文件 (*.csv)")
        if not path:
            return
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "流水号", "工单号", "客户姓名", "联系电话", "物品描述",
                    "修复内容", "材料批号", "材料名称", "用量(ml/g)", "使用时间",
                    "召回状态", "备注"
                ])
                for r in final_rows:
                    rs = r.get("recall_status") or RECALL_STATUS_PENDING
                    writer.writerow([
                        r.get("id", ""),
                        r.get("order_no", ""),
                        r.get("customer_name", ""),
                        r.get("customer_phone", "") or "",
                        r.get("item_desc", ""),
                        r.get("repair_content", ""),
                        r.get("batch_no", ""),
                        r.get("material_name", ""),
                        r.get("usage_amount", ""),
                        r.get("used_at", ""),
                        RECALL_STATUS_LABELS.get(rs, rs),
                        r.get("recall_remark", "") or "",
                    ])
            skip_n = len(self._last_recall_results) - len(final_rows)
            info = f"已导出 {len(final_rows)} 条记录到:\n{path}"
            if skip_n > 0:
                info += f"\n\n(已跳过 {skip_n} 条缺电话的记录)"
            QMessageBox.information(self, "导出成功", info)
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def clear_recall_filters(self):
        self.recall_name.clear()
        self.recall_order.clear()
        self.recall_batch.clear()
        self.recall_mat.clear()
        self.recall_summary.hide()
        self.recall_table.setRowCount(0)
        self._last_recall_results = []

    # ---------- 客户档案 ----------
    def refresh_customer_list(self):
        kw = self.cust_kw.text().strip()
        rows = db.get_customers(kw)
        self.cust_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.cust_table.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.cust_table.setItem(i, 1, QTableWidgetItem(r["name"] or ""))
            self.cust_table.setItem(i, 2, QTableWidgetItem(r.get("phone") or "(未录入)"))
            self.cust_table.setItem(i, 3, QTableWidgetItem(r.get("created_at") or ""))
        if rows:
            self.cust_table.selectRow(0)

    def on_customer_selected(self):
        row = self.cust_table.currentRow()
        if row < 0:
            return
        cid_item = self.cust_table.item(row, 0)
        if not cid_item:
            return
        cid = int(cid_item.text())
        customer = db.get_customer_by_id(cid)
        if not customer:
            return
        phone = customer.get("phone") or "(未录入)"
        item_desc = customer.get("item_desc") or "(未记录)"
        self.cust_info.setText(
            f"👤 姓名: {customer['name']}    📞 电话: {phone}\n"
            f"📝 常见物品: {item_desc}    📅 建档时间: {customer.get('created_at') or ''}"
        )
        self._load_customer_queue(customer)
        self._load_customer_orders(customer)
        self._load_customer_flows(customer)

    def _load_customer_queue(self, customer):
        table = self.cust_queue_tab["table"]
        rows = db.get_queue_by_customer(customer_id=customer["id"], customer_name=customer["name"])
        table.setRowCount(len(rows))
        status_map = {
            "waiting": ("等候中", "#1976d2"),
            "calling": ("叫号中", "#d84315"),
            "serving": ("服务中", "#2e7d32"),
            "skipped": ("已过号", "#ef6c00"),
            "done": ("已完成", "#455a64"),
            "invalid": ("已作废", "#b71c1c"),
        }
        for i, r in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(r["ticket_no"]))
            table.setItem(i, 1, QTableWidgetItem(r.get("item_desc") or ""))
            st_text, st_color = status_map.get(r["status"], (r["status"], "#333"))
            if r.get("skip_count"):
                st_text += f" (过{r['skip_count']}次)"
            if r.get("priority_reason"):
                st_text += f" [{r['priority_reason']}]"
            it = QTableWidgetItem(st_text)
            it.setForeground(QColor(st_color))
            f = it.font()
            f.setBold(True)
            it.setFont(f)
            table.setItem(i, 2, it)
            table.setItem(i, 3, QTableWidgetItem(str(r.get("skip_count") or 0)))
            table.setItem(i, 4, QTableWidgetItem(r.get("created_at") or ""))

    def _load_customer_orders(self, customer):
        table = self.cust_order_tab["table"]
        rows = db.get_repair_orders_by_customer(customer_id=customer["id"], customer_name=customer["name"])
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(r["order_no"]))
            table.setItem(i, 1, QTableWidgetItem(r.get("item_desc") or ""))
            table.setItem(i, 2, QTableWidgetItem(r.get("repair_content") or ""))
            status_text, color = {
                "processing": ("处理中", "#ef6c00"),
                "done": ("已完成", "#2e7d32"),
                "cancelled": ("已取消", "#b71c1c"),
            }.get(r.get("status") or "processing", (r.get("status") or "-", "#333"))
            it = QTableWidgetItem(status_text)
            it.setForeground(QColor(color))
            f = it.font()
            f.setBold(True)
            it.setFont(f)
            table.setItem(i, 3, it)
            table.setItem(i, 4, QTableWidgetItem(r.get("created_at") or ""))

    def _load_customer_flows(self, customer):
        table = self.cust_flow_tab["table"]
        rows = db.get_flows_by_customer(customer_id=customer["id"], customer_name=customer["name"])
        mats = {m["id"]: m for m in db.get_materials()}
        table.setRowCount(len(rows))
        for i, f in enumerate(rows):
            m = mats.get(f.get("material_id") or -1, {})
            table.setItem(i, 0, QTableWidgetItem(f.get("order_no") or ""))
            table.setItem(i, 1, QTableWidgetItem(f.get("batch_no") or ""))
            table.setItem(i, 2, QTableWidgetItem(m.get("material_name") or ""))
            table.setItem(i, 3, QTableWidgetItem(str(f.get("usage_amount") or 0)))
            table.setItem(i, 4, QTableWidgetItem(f.get("used_at") or ""))
            rs = f.get("recall_status") or RECALL_STATUS_PENDING
            rs_text = RECALL_STATUS_LABELS.get(rs, rs)
            rs_it = QTableWidgetItem(rs_text)
            rs_it.setForeground(QColor(RECALL_STATUS_COLORS.get(rs, "#333")))
            rf = rs_it.font()
            rf.setBold(True)
            rs_it.setFont(rf)
            table.setItem(i, 5, rs_it)


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
BTN_SUCCESS = """
QPushButton { background:#2e7d32; color:white; border:none; border-radius:6px; padding:6px 16px; }
QPushButton:hover { background:#1b5e20; }
"""
BTN_WARN = """
QPushButton { background:#ef6c00; color:white; border:none; border-radius:6px; padding:6px 16px; }
QPushButton:hover { background:#e65100; }
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
