"""Category Manager - Global autocomplete sets and combo box helpers.

Manages the global category vocabulary (wafer, pad, slurry, conditioner)
that persists across file selections and is shared by both
FileDetailsPanel and BulkEditPanel.
"""

from contextlib import contextmanager

from PyQt6.QtWidgets import QComboBox, QCompleter, QLineEdit
from PyQt6.QtCore import Qt, QStringListModel

# ---------------------------------------------------------------------------
# Global sets for autocomplete category values (persist across file selections)
# ---------------------------------------------------------------------------
_wafer_types_set = set()
_pad_types_set = set()
_slurry_types_set = set()
_conditioner_types_set = set()


def rebuild_global_sets(report):
    """Clear and rebuild all category sets from every file in the report.

    This ensures the dropdown options reflect only values that currently
    exist across all files — orphaned values are automatically pruned.
    """
    _wafer_types_set.clear()
    _pad_types_set.clear()
    _slurry_types_set.clear()
    _conditioner_types_set.clear()

    if report is None:
        return

    for f in report.files:
        if f.wafer_type is not None and str(f.wafer_type).strip():
            _wafer_types_set.add(str(f.wafer_type).strip())
        if f.pad_type is not None and str(f.pad_type).strip():
            _pad_types_set.add(str(f.pad_type).strip())
        if f.slurry_type is not None and str(f.slurry_type).strip():
            _slurry_types_set.add(str(f.slurry_type).strip())
        if f.conditioner_disk_type is not None and str(f.conditioner_disk_type).strip():
            _conditioner_types_set.add(str(f.conditioner_disk_type).strip())


class _ShowAllLineEdit(QLineEdit):
    """QLineEdit subclass that shows all completer options on focus/click
    when the field is empty."""

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._show_all_if_empty()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._show_all_if_empty()

    def _show_all_if_empty(self):
        completer = self.completer()
        if completer and not self.text():
            completer.setCompletionPrefix("")
            completer.complete()


def create_autocomplete_combo(parent=None):
    """Create an editable QComboBox with case-insensitive autocomplete.

    Shows all options when the field is clicked/focused while empty.
    """
    combo = QComboBox(parent)
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.setMinimumWidth(150)

    # Replace the default line edit with our subclass
    line_edit = _ShowAllLineEdit(combo)
    line_edit.setPlaceholderText("Select or type...")
    combo.setLineEdit(line_edit)

    completer = QCompleter([], combo)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    combo.setCompleter(completer)
    return combo


def populate_combo_from_set(combo, global_set):
    """Refresh a combo box's items from a global set, preserving current text."""
    current_text = combo.currentText()
    combo.blockSignals(True)
    combo.clear()
    combo.addItems(sorted(global_set))
    # Update the completer model
    combo.completer().setModel(QStringListModel(sorted(global_set)))
    # Restore previous text
    if current_text:
        combo.setCurrentText(current_text)
    else:
        combo.setCurrentIndex(-1)
    combo.blockSignals(False)


def populate_all_combos(panel):
    """Refresh all four category combo boxes on a panel from global sets.

    The panel must have attributes: wafer_type_combo, pad_type_combo,
    slurry_type_combo, conditioner_disk_type_combo.
    """
    populate_combo_from_set(panel.wafer_type_combo, _wafer_types_set)
    populate_combo_from_set(panel.pad_type_combo, _pad_types_set)
    populate_combo_from_set(panel.slurry_type_combo, _slurry_types_set)
    populate_combo_from_set(panel.conditioner_disk_type_combo, _conditioner_types_set)


def combo_value(combo):
    """Return the combo text as a string, or None if empty."""
    text = combo.currentText().strip()
    return text if text else None


def set_combo_value(combo, value):
    """Set combo box text to value, or clear if None."""
    if value is None:
        combo.setCurrentText("")
    else:
        combo.setCurrentText(str(value))


@contextmanager
def block_signals(*widgets):
    """Context manager to block and restore signals on multiple Qt widgets."""
    for w in widgets:
        w.blockSignals(True)
    try:
        yield
    finally:
        for w in widgets:
            w.blockSignals(False)

