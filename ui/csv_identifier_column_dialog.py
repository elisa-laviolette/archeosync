"""
Dialog to choose which CSV column populates the ``identifier`` field on Imported_CSV_Points.

Used when several non-coordinate columns could serve as the topo–object link and the CSV has
no column named ``identifier``. The choice is persisted via plugin settings.
"""

from typing import List, Optional

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt


def _align_center_flag():
    """Return a center-alignment flag compatible with Qt5 and Qt6."""
    if hasattr(Qt, "AlignCenter"):
        return Qt.AlignCenter
    alignment_flag = getattr(Qt, "AlignmentFlag", None)
    if alignment_flag is not None and hasattr(alignment_flag, "AlignCenter"):
        return alignment_flag.AlignCenter
    raise AttributeError("Qt center alignment flag is not available.")


class CsvIdentifierColumnDialog(QtWidgets.QDialog):
    """
    Ask the user which unified CSV column key should populate ``identifier`` on the import layer.
    """

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget],
        candidates: List[str],
        initial_selection: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Topo point identifier column"))
        self.setModal(True)
        self._candidates = list(candidates)
        self._combo = QtWidgets.QComboBox()
        self._combo.setMinimumWidth(320)
        for c in self._candidates:
            self._combo.addItem(c, c)
        if initial_selection and initial_selection in self._candidates:
            idx = self._combo.findData(initial_selection)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)

        info = QtWidgets.QLabel(
            self.tr(
                "Several text columns are present and there is no column named \"identifier\". "
                "Choose which column should be copied into the \"identifier\" field "
                "(for relations with objects). This choice is saved in plugin settings and can be "
                "changed later in ArcheoSync configuration."
            )
        )
        info.setWordWrap(True)
        info.setAlignment(_align_center_flag())

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(info)
        form = QtWidgets.QFormLayout()
        form.addRow(self.tr("Column to use as identifier:"), self._combo)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def selected_column_key(self) -> str:
        """Return the selected unified mapping key (CSV column group name)."""
        data = self._combo.currentData()
        if data is not None:
            return str(data)
        return self._combo.currentText().strip()

    def accept(self) -> None:
        if not self.selected_column_key():
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Invalid selection"),
                self.tr("Please choose a column."),
            )
            return
        super().accept()
