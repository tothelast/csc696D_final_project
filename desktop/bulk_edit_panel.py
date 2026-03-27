"""Bulk Edit Panel - Edit shared attributes across multiple selected files."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QDoubleSpinBox, QGroupBox, QPushButton,
)

from desktop.theme import COLORS, ToastNotification
from desktop.material_categories import (
    rebuild_global_sets, create_autocomplete_combo, populate_all_combos,
    combo_value, block_signals,
)


class BulkEditPanel(QWidget):
    """Panel for editing shared attributes across multiple selected files."""

    def __init__(self):
        super().__init__()
        self.raw_files = []
        self.report = None
        self._dirty = set()  # tracks field names the user modified
        self.setup_ui()

    def set_report(self, report):
        """Store a reference to the Report so we can rebuild category sets from all files."""
        self.report = report

    def setup_ui(self):
        """Initialize the bulk edit UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)

        group = QGroupBox("Bulk Edit — Editing Multiple Files")
        group_layout = QVBoxLayout(group)

        # Info label
        self.info_label = QLabel("Edit values below and click Apply to save changes.")
        self.info_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-style: italic; padding: 4px 0;")
        group_layout.addWidget(self.info_label)

        form = QFormLayout()
        form.setSpacing(12)

        # Analysis Interval
        interval_layout = QHBoxLayout()
        interval_layout.setSpacing(6)
        self.interval_start = QDoubleSpinBox()
        self.interval_start.setRange(-1000, 10000)
        self.interval_start.setValue(7)
        self.interval_start.setSuffix(" s")
        self.interval_start.setDecimals(1)
        self.interval_start.setMinimumWidth(70)
        self.interval_start.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        interval_layout.addWidget(self.interval_start)
        interval_layout.addWidget(QLabel("to"))
        self.interval_end = QDoubleSpinBox()
        self.interval_end.setRange(-1000, 10000)
        self.interval_end.setValue(57)
        self.interval_end.setSuffix(" s")
        self.interval_end.setDecimals(1)
        self.interval_end.setMinimumWidth(70)
        self.interval_end.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        interval_layout.addWidget(self.interval_end)
        form.addRow("Analysis Interval:", interval_layout)

        self.wafer_type_combo = create_autocomplete_combo()
        form.addRow("Wafer:", self.wafer_type_combo)

        self.pad_type_combo = create_autocomplete_combo()
        form.addRow("Pad:", self.pad_type_combo)

        self.slurry_type_combo = create_autocomplete_combo()
        form.addRow("Slurry:", self.slurry_type_combo)

        self.conditioner_disk_type_combo = create_autocomplete_combo()
        form.addRow("Conditioner:", self.conditioner_disk_type_combo)

        # Set Points
        self.pressure_psi_input = QDoubleSpinBox()
        self.pressure_psi_input.setRange(0, 100)
        self.pressure_psi_input.setDecimals(1)
        self.pressure_psi_input.setMinimumWidth(150)
        self.pressure_psi_input.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        form.addRow("Pressure (PSI):", self.pressure_psi_input)

        self.polish_time_input = QDoubleSpinBox()
        self.polish_time_input.setRange(0, 1000)
        self.polish_time_input.setDecimals(1)
        self.polish_time_input.setMinimumWidth(150)
        self.polish_time_input.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        form.addRow("Polish Time (min):", self.polish_time_input)

        group_layout.addLayout(form)

        # Apply button — bottom-right of the group box
        apply_layout = QHBoxLayout()
        apply_layout.addStretch()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedWidth(100)
        self.apply_btn.clicked.connect(self.on_apply_clicked)
        apply_layout.addWidget(self.apply_btn)
        apply_layout.setContentsMargins(0, 8, 12, 8)
        group_layout.addLayout(apply_layout)

        # Dirty-tracking signals: mark fields as user-modified
        self.interval_start.valueChanged.connect(lambda: self._dirty.add('interval'))
        self.interval_end.valueChanged.connect(lambda: self._dirty.add('interval'))
        self.wafer_type_combo.currentTextChanged.connect(lambda: self._dirty.add('wafer_type'))
        self.pad_type_combo.currentTextChanged.connect(lambda: self._dirty.add('pad_type'))
        self.slurry_type_combo.currentTextChanged.connect(lambda: self._dirty.add('slurry_type'))
        self.conditioner_disk_type_combo.currentTextChanged.connect(lambda: self._dirty.add('conditioner_disk_type'))
        self.pressure_psi_input.valueChanged.connect(lambda: self._dirty.add('pressure_psi'))
        self.polish_time_input.valueChanged.connect(lambda: self._dirty.add('polish_time'))

        group_layout.addStretch()
        layout.addWidget(group)
        layout.addStretch()

    def set_files(self, raw_files):
        """Set the files to bulk edit."""
        self.raw_files = raw_files
        self.info_label.setText(
            f"Editing {len(raw_files)} files. Edit values below and click Apply."
        )

        # Rebuild category sets from ALL files in the report and refresh combos
        rebuild_global_sets(self.report)
        populate_all_combos(self)

        with block_signals(
            self.interval_start, self.interval_end,
            self.pressure_psi_input, self.polish_time_input
        ):
            # Show common values or reset to placeholder if they differ
            intervals = [f.interval for f in raw_files]
            starts = set(i[0] for i in intervals)
            ends = set(i[1] for i in intervals)
            self.interval_start.setValue(starts.pop() if len(starts) == 1 else 7)
            self.interval_end.setValue(ends.pop() if len(ends) == 1 else 57)

            self._load_common_combo(self.slurry_type_combo, [f.slurry_type for f in raw_files])
            self._load_common_combo(self.wafer_type_combo, [f.wafer_type for f in raw_files])
            self._load_common_combo(self.pad_type_combo, [f.pad_type for f in raw_files])
            self._load_common_combo(self.conditioner_disk_type_combo, [f.conditioner_disk_type for f in raw_files])

            # Set Points: show common value or 0
            psi_vals = set(f.pressure_psi for f in raw_files)
            self.pressure_psi_input.setValue(psi_vals.pop() if len(psi_vals) == 1 else 0)
            pt_vals = set(f.polish_time for f in raw_files)
            self.polish_time_input.setValue(pt_vals.pop() if len(pt_vals) == 1 else 0)

        # Clear dirty flags after all programmatic population so that
        # loading files doesn't count as user modification
        self._dirty.clear()

    def _load_common_combo(self, combo, values):
        """Set combo to common value if all files share it, otherwise clear."""
        unique = set(values)
        if len(unique) == 1:
            val = unique.pop()
            if val is None:
                combo.setCurrentText("")
            else:
                combo.setCurrentText(str(val))
        else:
            combo.setCurrentText("")

    def on_apply_clicked(self):
        """Apply only user-modified fields to every selected file."""
        if not self.raw_files or not self._dirty:
            return

        for f in self.raw_files:
            if 'interval' in self._dirty:
                start = self.interval_start.value()
                end = self.interval_end.value()
                if start < end:
                    f.interval = [start, end]
            if 'wafer_type' in self._dirty:
                f.wafer_type = combo_value(self.wafer_type_combo)
            if 'pad_type' in self._dirty:
                f.pad_type = combo_value(self.pad_type_combo)
            if 'slurry_type' in self._dirty:
                f.slurry_type = combo_value(self.slurry_type_combo)
            if 'conditioner_disk_type' in self._dirty:
                f.conditioner_disk_type = combo_value(self.conditioner_disk_type_combo)
            if 'pressure_psi' in self._dirty:
                f.pressure_psi = self.pressure_psi_input.value()
            if 'polish_time' in self._dirty:
                f.polish_time = self.polish_time_input.value()

        # Rebuild category sets from all files (reflects additions and removals)
        rebuild_global_sets(self.report)
        populate_all_combos(self)

        # Toast notification
        n = len(self.raw_files)
        ToastNotification(f"Changes applied to {n} files", self)

        # Reset dirty flags after applying
        self._dirty.clear()