#!/usr/bin/env python3
"""
Spellcheck GUI - View and manage spell-check status of videos
"""

import sys
import os
import webbrowser
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# Check for PySide6
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTableView, QPushButton, QComboBox, QDateEdit, QLabel,
        QHeaderView, QMessageBox, QFileDialog, QGroupBox, QCheckBox,
        QAbstractItemView, QStatusBar
    )
    from PySide6.QtCore import (
        Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
        QDate, Signal
    )
    from PySide6.QtGui import QAction, QColor, QBrush
except ImportError:
    print("PySide6 is required for the GUI.")
    print("Install with: pip install PySide6")
    sys.exit(1)

from spellcheck_tracker import SpellcheckTracker, VideoStatus


class VideoTableModel(QAbstractTableModel):
    """Table model for displaying video status data"""

    COLUMNS = ['Title', 'Video ID', 'Spell-Checked', 'Check Date', 'Upload Date']

    def __init__(self, tracker: SpellcheckTracker):
        super().__init__()
        self.tracker = tracker
        self._data: List[VideoStatus] = []
        self.refresh()

    def refresh(self):
        """Reload data from tracker"""
        self.beginResetModel()
        self._data = self.tracker.get_all_videos()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role: int):
        if not index.isValid() or index.row() >= len(self._data):
            return None

        video = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:  # Title
                return video.title
            elif col == 1:  # Video ID
                return video.video_id
            elif col == 2:  # Spell-Checked
                return "Yes" if video.spell_checked else "No"
            elif col == 3:  # Check Date
                if video.spell_check_date:
                    dt = datetime.fromisoformat(video.spell_check_date)
                    return dt.strftime("%Y-%m-%d %H:%M")
                return "-"
            elif col == 4:  # Upload Date
                if video.last_uploaded_date:
                    dt = datetime.fromisoformat(video.last_uploaded_date)
                    return dt.strftime("%Y-%m-%d %H:%M")
                return "-"

        elif role == Qt.BackgroundRole:
            if col == 2:  # Color code spell-check status
                if video.spell_checked:
                    return QBrush(QColor(200, 255, 200))  # Light green
                else:
                    return QBrush(QColor(255, 220, 220))  # Light red

        elif role == Qt.UserRole:
            # Return the VideoStatus object for filtering
            return video

        return None

    def headerData(self, section: int, orientation, role: int):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def get_video_at_row(self, row: int) -> Optional[VideoStatus]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None


class VideoFilterProxyModel(QSortFilterProxyModel):
    """Proxy model for filtering and sorting"""

    def __init__(self):
        super().__init__()
        self._spell_check_filter = "all"  # all, checked, unchecked
        self._date_filter_enabled = False
        self._date_before: Optional[datetime] = None
        self._date_after: Optional[datetime] = None

    def set_spell_check_filter(self, filter_value: str):
        """Set filter: 'all', 'checked', 'unchecked'"""
        self._spell_check_filter = filter_value
        self.invalidateFilter()

    def set_date_filter(self, enabled: bool,
                        before: Optional[datetime] = None,
                        after: Optional[datetime] = None):
        """Set date range filter"""
        self._date_filter_enabled = enabled
        self._date_before = before
        self._date_after = after
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        index = self.sourceModel().index(source_row, 0, source_parent)
        video = self.sourceModel().data(index, Qt.UserRole)

        if video is None:
            return False

        # Spell-check filter
        if self._spell_check_filter == "checked" and not video.spell_checked:
            return False
        if self._spell_check_filter == "unchecked" and video.spell_checked:
            return False

        # Date filter
        if self._date_filter_enabled and video.spell_check_date:
            check_date = datetime.fromisoformat(video.spell_check_date)

            if self._date_before and check_date >= self._date_before:
                return False
            if self._date_after and check_date <= self._date_after:
                return False

        return True


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.tracker = SpellcheckTracker()
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self):
        """Create and arrange UI components"""
        self.setWindowTitle("Caption Spell-Check Tracker")
        self.setMinimumSize(900, 600)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Filter panel
        self.setup_filters(layout)

        # Table
        self.setup_table(layout)

        # Action buttons
        self.setup_actions(layout)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Menu
        self.setup_menu()

    def setup_menu(self):
        """Create menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_data)
        file_menu.addAction(refresh_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_filters(self, layout: QVBoxLayout):
        """Create filter controls"""
        filter_group = QGroupBox("Filters")
        filter_layout = QHBoxLayout(filter_group)

        # Spell-check status filter
        filter_layout.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["All", "Not Spell-Checked", "Spell-Checked"])
        self.status_combo.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.status_combo)

        filter_layout.addSpacing(20)

        # Date filter
        self.date_filter_check = QCheckBox("Filter by date:")
        self.date_filter_check.toggled.connect(self.on_filter_changed)
        filter_layout.addWidget(self.date_filter_check)

        filter_layout.addWidget(QLabel("Checked before:"))
        self.date_before = QDateEdit()
        self.date_before.setCalendarPopup(True)
        self.date_before.setDate(QDate.currentDate())
        self.date_before.dateChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.date_before)

        filter_layout.addStretch()

        layout.addWidget(filter_group)

    def setup_table(self, layout: QVBoxLayout):
        """Create table view"""
        self.model = VideoTableModel(self.tracker)
        self.proxy_model = VideoFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortRole(Qt.DisplayRole)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)

        # Column sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Title
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Video ID
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Spell-Checked
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Check Date
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Upload Date

        self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)

        layout.addWidget(self.table)

    def setup_actions(self, layout: QVBoxLayout):
        """Create action buttons"""
        button_layout = QHBoxLayout()

        self.btn_open_video = QPushButton("Open in Browser")
        self.btn_open_video.clicked.connect(self.open_video_in_browser)
        self.btn_open_video.setEnabled(False)
        button_layout.addWidget(self.btn_open_video)

        self.btn_view_original = QPushButton("View Original Caption")
        self.btn_view_original.clicked.connect(self.view_original_caption)
        self.btn_view_original.setEnabled(False)
        button_layout.addWidget(self.btn_view_original)

        self.btn_mark_checked = QPushButton("Mark as Spell-Checked")
        self.btn_mark_checked.clicked.connect(self.mark_as_spell_checked)
        self.btn_mark_checked.setEnabled(False)
        button_layout.addWidget(self.btn_mark_checked)

        button_layout.addStretch()

        self.btn_export = QPushButton("Export Selected")
        self.btn_export.clicked.connect(self.export_selected)
        self.btn_export.setEnabled(False)
        button_layout.addWidget(self.btn_export)

        layout.addLayout(button_layout)

    def on_filter_changed(self):
        """Handle filter changes"""
        # Status filter
        status_text = self.status_combo.currentText()
        if status_text == "All":
            self.proxy_model.set_spell_check_filter("all")
        elif status_text == "Not Spell-Checked":
            self.proxy_model.set_spell_check_filter("unchecked")
        else:
            self.proxy_model.set_spell_check_filter("checked")

        # Date filter
        if self.date_filter_check.isChecked():
            before_date = self.date_before.date().toPython()
            before_datetime = datetime.combine(before_date, datetime.max.time())
            self.proxy_model.set_date_filter(True, before=before_datetime)
        else:
            self.proxy_model.set_date_filter(False)

        self.update_status()

    def on_selection_changed(self):
        """Enable/disable actions based on selection"""
        has_selection = len(self.table.selectionModel().selectedRows()) > 0
        self.btn_open_video.setEnabled(has_selection)
        self.btn_view_original.setEnabled(has_selection)
        self.btn_mark_checked.setEnabled(has_selection)
        self.btn_export.setEnabled(has_selection)

    def get_selected_videos(self) -> List[VideoStatus]:
        """Get list of selected videos"""
        videos = []
        for index in self.table.selectionModel().selectedRows():
            source_index = self.proxy_model.mapToSource(index)
            video = self.model.get_video_at_row(source_index.row())
            if video:
                videos.append(video)
        return videos

    def open_video_in_browser(self):
        """Open selected video in browser"""
        videos = self.get_selected_videos()
        for video in videos[:5]:  # Limit to 5 to avoid opening too many tabs
            webbrowser.open(video.url)

    def view_original_caption(self):
        """Open original caption file"""
        videos = self.get_selected_videos()
        if not videos:
            return

        video = videos[0]
        caption_path = self.tracker.get_original_caption_path(video.video_id)

        if caption_path and caption_path.exists():
            # Open with default text editor
            if sys.platform == 'win32':
                os.startfile(caption_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', caption_path])
            else:
                subprocess.run(['xdg-open', caption_path])
        else:
            QMessageBox.warning(
                self,
                "Not Found",
                f"Original caption file not found for {video.video_id}"
            )

    def mark_as_spell_checked(self):
        """Mark selected videos as spell-checked"""
        videos = self.get_selected_videos()
        if not videos:
            return

        reply = QMessageBox.question(
            self,
            "Confirm",
            f"Mark {len(videos)} video(s) as spell-checked?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            for video in videos:
                self.tracker.mark_spell_checked(video.video_id)
            self.refresh_data()
            self.status_bar.showMessage(f"Marked {len(videos)} video(s) as spell-checked", 3000)

    def export_selected(self):
        """Export selected videos to JSON"""
        videos = self.get_selected_videos()
        if not videos:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Videos",
            "selected_videos.json",
            "JSON Files (*.json)"
        )

        if file_path:
            import json
            from dataclasses import asdict

            data = {
                'exported_at': datetime.now().isoformat(),
                'video_count': len(videos),
                'videos': [asdict(v) for v in videos]
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.status_bar.showMessage(f"Exported {len(videos)} videos to {file_path}", 3000)

    def refresh_data(self):
        """Reload data from tracker"""
        self.model.refresh()
        self.update_status()

    def update_status(self):
        """Update status bar with counts"""
        stats = self.tracker.get_stats()
        visible = self.proxy_model.rowCount()
        self.status_bar.showMessage(
            f"Showing {visible} of {stats['total']} videos | "
            f"Checked: {stats['spell_checked']} | "
            f"Not checked: {stats['not_checked']} | "
            f"Uploaded: {stats['uploaded']}"
        )

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About",
            "Caption Spell-Check Tracker\n\n"
            "Track which YouTube videos have been spell-checked.\n\n"
            "Part of the Caption Spell Checker project."
        )


def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Caption Spell-Check Tracker")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
