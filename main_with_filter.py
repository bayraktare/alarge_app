import sys
import os
import platform
import sqlite3
import re
import glob
import paramiko
from io import BytesIO
import qrcode
from scipy.signal import savgol_filter
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoLocator, FormatStrFormatter

# Import Qt components
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QFrame, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QListWidget, QListWidgetItem, QGridLayout, QLabel, QDateEdit,
    QFileDialog, QMessageBox, QInputDialog, QStackedWidget, 
    QTableView, QStatusBar, QHeaderView
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QImage
)
from PyQt6.QtCore import (
    Qt, QRect, QSize, QRegularExpression, QSortFilterProxyModel
)
# Import validators from the correct location in PyQt6
from PyQt6.QtGui import QRegularExpressionValidator

# IMPORT / GUI AND MODULES AND WIDGETS
# ///////////////////////////////////////////////////////////////
from modules import *
from widgets import *
os.environ["QT_FONT_DPI"] = "96" # FIX Problem for High DPI and Scale above 100%
# SET AS GLOBAL WIDGETS
# ///////////////////////////////////////////////////////////////
widgets = None

# from src.customWidgets import *

class WidgetCache:
    def __init__(self):
        self.cache = {}
        
    def save(self, tab_widget, db_id):
        widgets = [tab_widget.widget(index) for index in range(tab_widget.count())]
        self.cache[db_id] = widgets

    def restore(self, tab_widget, db_id):
        if db_id in self.cache:
            tab_widget.clear()
            widgets = self.cache[db_id]
            for widget in widgets:
                tab_widget.addTab(widget, widget.windowTitle())
    def returnCache(self):
        return self.cache
    
class FileListWidgetItem(QWidget):
    """
    A custom widget for displaying file list items in the database explorer.

    Attributes:
    -----------#+
    layout : QVBoxLayout#+
        The vertical layout for arranging the widgets.#+
#+
    Methods:#+
    --------#+
    __init__(self, file_path: str, parent: QWidget = None)#+
        Initializes the FileListWidgetItem with the given file path and parent widget.#+
        Creates and adds necessary widgets to the layout.#+
    """#+
#+
    def __init__(self, file_path: str, parent: QWidget = None):#+
        """#+
        Initializes the FileListWidgetItem with the given file path and parent widget.#+
        Creates and adds necessary widgets to the layout.#+
#+
        Parameters:#+
        -----------#+
        file_path : str#+
            The path of the file to be displayed.#+
        parent : QWidget, optional#+
            The parent widget for this item. The default is None.#+
        """#+
        super().__init__(parent)#+
#+
        self.layout = QVBoxLayout()#+
#+
        file_name = os.path.basename(file_path)#+
        file_icon = QIcon(file_path)#+
#+
        file_label = QLabel(file_name)#+
        file_label.setAlignment(Qt.AlignLeft)#+
        file_label.setPixmap(file_icon.pixmap(32, 32))#+
#+
        self.layout.addWidget(file_label)#+
        self.setLayout(self.layout)#+

    def __init__(self, file_path):
        super().__init__()
        
        self.filePath = file_path
        self.fileName = os.path.basename(file_path)
        self.fileBaseName = os.path.splitext(self.fileName)[0]
        
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()  
        
        self.nameLabel = QLabel(self.formatString(self.fileBaseName))
        self.nameLabel.setFixedHeight(30)
        self.nameLabel.setAlignment(Qt.AlignCenter)
            
        layout.addWidget(self.nameLabel)
        layout.setAlignment(Qt.AlignCenter)        
        self.setLayout(layout)
        
    @staticmethod
    def formatString(string):
        formattedString = string.replace('_', ' ')
        formattedString = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', formattedString)
        
        return formattedString
    

class CustomFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.test_id = ""
        self.selected_date = ""

    def setTestID(self, test_id):
        self.test_id = test_id
        self.invalidateFilter()

    def setSelectedDate(self, selected_date):
        self.selected_date = selected_date
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        if not model:
            return True

        # Default to accepting the row if no filters are set
        if not self.test_id and not self.selected_date:
            return True
            
        # Find the TestID column (usually column 0, but let's make sure)
        test_id_column = 0
        for col in range(model.columnCount()):
            header = model.headerData(col, Qt.Orientation.Horizontal)
            if isinstance(header, str) and "id" in header.lower():
                test_id_column = col
                break
                
        # Find the Date column (usually column 1, but let's check)
        date_column = 1
        for col in range(model.columnCount()):
            header = model.headerData(col, Qt.Orientation.Horizontal)
            if isinstance(header, str) and "date" in header.lower() or "tarih" in header.lower():
                date_column = col
                break

        # Get the data for filtering
        test_id_index = model.index(source_row, test_id_column, source_parent)
        date_index = model.index(source_row, date_column, source_parent)
        
        # Get the actual data
        test_id_data = str(model.data(test_id_index) or "")
        date_data = str(model.data(date_index) or "")
        
        # Debug output
        print(f"Filtering row {source_row}: TestID '{test_id_data}' against '{self.test_id}', Date '{date_data}' against '{self.selected_date}'")

        # Filter logic: test_id_matches is True if test_id is empty or if it's in the data
        test_id_matches = not self.test_id or self.test_id in test_id_data
        date_matches = not self.selected_date or self.selected_date in date_data

        return test_id_matches and date_matches

class TableItem:
    def __init__(self, data):
        self._data = data
        self._row = -1
        
    def data(self, role=Qt.DisplayRole):
        return self._data
        
    def row(self):
        return self._row
    
    def setRow(self, row):
        self._row = row

# MAIN WINDOW CLASS
# ///////////////////////////////////////////////////////////////
class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)

        # super(MainWindow, self).__init__()

        # SET AS GLOBAL WIDGETS
        # ///////////////////////////////////////////////////////////////
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.lastSelectedRow = None
        self.widgetCache = WidgetCache()
        global widgets
        widgets = self.ui

        self.initUI()

        self.addDataBaseFromDir("./databases")
        self.add_component_row()

        self.ui.addDatabaseButton.clicked.connect(self.addDatabase)
        self.ui.createReportButton.clicked.connect(self.createReport)
        self.ui.getDetailsButton.clicked.connect(self.getTestDetails)
        self.ui.visualizeDataButton.clicked.connect(self.visualizeData)
        # self.ui.newButton.clicked.connect(self.ssh_connect)
        self.ui.listWidget.selectionModel().selectionChanged.connect(self.updateTabs)

        # USE CUSTOM TITLE BAR | USE AS "False" FOR MAC OR LINUX
        # ///////////////////////////////////////////////////////////////
        Settings.ENABLE_CUSTOM_TITLE_BAR = True

        # APP NAME
        # ///////////////////////////////////////////////////////////////
        title = "ALARAGE Lab."
        description = "ALARGE Lab. Test Equipments Reporting Tool"
        # APPLY TEXTS
        self.setWindowTitle(title)
        widgets.titleRightInfo.setText(description)

        # TOGGLE MENU
        # ///////////////////////////////////////////////////////////////
        widgets.toggleButton.clicked.connect(lambda: UIFunctions.toggleMenu(self, True))

        # SET UI DEFINITIONS
        # ///////////////////////////////////////////////////////////////
        UIFunctions.uiDefinitions(self)

        # QTableWidget PARAMETERS
        # ///////////////////////////////////////////////////////////////
        widgets.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # BUTTONS CLICK
        # ///////////////////////////////////////////////////////////////

        # LEFT MENUS
        widgets.btn_home.clicked.connect(self.buttonClick)
        widgets.btn_widgets.clicked.connect(self.buttonClick)
        widgets.btn_new.clicked.connect(self.buttonClick)
        widgets.btn_save.clicked.connect(self.buttonClick)

        # EXTRA LEFT BOX
        def openCloseLeftBox():
            UIFunctions.toggleLeftBox(self, True)
        widgets.toggleLeftBox.clicked.connect(openCloseLeftBox)
        widgets.extraCloseColumnBtn.clicked.connect(openCloseLeftBox)

        # EXTRA RIGHT BOX
        def openCloseRightBox():
            UIFunctions.toggleRightBox(self, True)
        widgets.settingsTopBtn.clicked.connect(openCloseRightBox)

        # SHOW APP
        # ///////////////////////////////////////////////////////////////
        self.show()

        # SET CUSTOM THEME
        # ///////////////////////////////////////////////////////////////
        useCustomTheme = True
        themeFile = "themes\py_dracula_dark.qss"

        # SET THEME AND HACKS
        if useCustomTheme:
            # LOAD AND APPLY STYLE
            UIFunctions.theme(self, themeFile, True)

            # SET HACKS
            AppFunctions.setThemeHack(self)

        # SET HOME PAGE AND SELECT MENU
        # ///////////////////////////////////////////////////////////////
        widgets.stackedWidget.setCurrentWidget(widgets.new_page)
        widgets.btn_new.setStyleSheet(UIFunctions.selectMenu(widgets.btn_new.styleSheet()))

        
        # VAR

        # self.ip_address = None
        # self.username = None
        # self.password = None
        # self.data_path = None
        # self.local_path = './databases/MFI.db'

        self.ip_address = None
        self.username = None
        self.password = None
        self.data_path = r'C:\Users\krkrt\Desktop\db\MFI.db'
        self.local_path = './databases/MFI.db'


        

        self.setupComboBox()

        widgets.btn_add_component.clicked.connect(self.add_component_row)
        widgets.btn_remove_component.clicked.connect(self.remove_component_row)

        widgets.btn_save.clicked.connect(self.newRecord)

        widgets.add_connection.clicked.connect(self.sftp)

        widgets.btn_connect.clicked.connect(self.sftp_with_combobox)
        widgets.btn_save_txt_1.clicked.connect(self.save_to_txt)
        widgets.btn_generate_pdf_1.clicked.connect(self.make_pdf)
        widgets.btn_generate_qr_1.clicked.connect(self.make_qrcode)

    def initUI(self):
        # Apply modern design principles to the entire UI
        self.setStyleSheet("""
            QMainWindow {
                background-color: rgb(40, 44, 52);
            }
            
            QScrollBar:vertical {
                border: none;
                background-color: rgb(52, 59, 72);
                width: 14px;
                margin: 15px 0 15px 0;
                border-radius: 0px;
            }
            
            QScrollBar::handle:vertical {
                background-color: rgb(85, 170, 255);
                min-height: 30px;
                border-radius: 7px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: rgb(155, 155, 255);
            }
            
            QScrollBar::handle:vertical:pressed {
                background-color: rgb(189, 147, 249);
            }
            
            QToolTip {
                color: #ffffff;
                background-color: rgba(33, 37, 43, 180);
                border: 1px solid rgb(44, 49, 58);
                background-image: none;
                background-position: left center;
                background-repeat: no-repeat;
                border-left: 2px solid rgb(189, 147, 249);
                padding-left: 8px;
                margin: 0px;
            }
        """)
        
        # Apply styles to the main areas
        self.ui.home.setStyleSheet(""" 
            QFrame {
                background-color: rgb(40, 44, 52);
                border-radius: 8px;
            }
            QPushButton {
                background-color: rgb(52, 59, 72);
                color: rgb(221, 221, 221);
                font-weight: bold;
                border-radius: 5px;
                padding: 8px 15px;
                border: 2px solid rgb(44, 49, 58);
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: rgb(57, 65, 80);
                border: 2px solid rgb(61, 70, 86);
            }
            QPushButton:pressed {
                background-color: rgb(35, 40, 49);
                border: 2px solid rgb(43, 50, 61);
            }
            QPushButton:selected {
                background-color: rgb(189, 147, 249);
                border: 2px solid rgb(170, 132, 255);
            }
            QLabel {
                color: rgb(221, 221, 221);
                font-weight: bold;
                font-size: 12pt;
            }
            QLineEdit {
                background-color: rgb(33, 37, 43);
                border-radius: 5px;
                border: 2px solid rgb(52, 59, 72);
                padding: 5px;
                color: rgb(221, 221, 221);
                font-size: 11pt;
            }
            QLineEdit:focus {
                border: 2px solid rgb(85, 170, 255);
            }
            QDateEdit {
                background-color: rgb(33, 37, 43);
                border-radius: 5px;
                border: 2px solid rgb(52, 59, 72);
                padding: 5px;
                color: rgb(221, 221, 221);
                font-size: 11pt;
            }
            QDateEdit:focus {
                border: 2px solid rgb(85, 170, 255);
            }
            QComboBox {
                background-color: rgb(33, 37, 43);
                border-radius: 5px;
                border: 2px solid rgb(52, 59, 72);
                padding: 5px;
                color: rgb(221, 221, 221);
                font-size: 11pt;
            }
            QComboBox:focus {
                border: 2px solid rgb(85, 170, 255);
            }
        """)
        
        # Style the report widget
        self.ui.reportWidget.setStyleSheet("""
            QFrame {
                background-color: rgb(44, 49, 58);
                border-radius: 8px;
                margin: 10px;
            }
            QPushButton {
                background-color: rgb(52, 59, 72);
                color: rgb(221, 221, 221);
                font-weight: bold;
                border-radius: 5px;
                padding: 8px 15px;
                border: 2px solid rgb(44, 49, 58);
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: rgb(57, 65, 80);
                border: 2px solid rgb(61, 70, 86);
            }
            QLabel {
                color: rgb(221, 221, 221);
                font-weight: bold;
                padding: 5px;
            }
        """)
        
        # Style the tab widget
        self.ui.tabWidget.setStyleSheet("""
            QTabWidget {
                background-color: rgb(33, 37, 43);
            }
            QTabWidget::pane {
                border: 1px solid rgb(44, 49, 58);
                border-radius: 5px;
                background-color: rgb(33, 37, 43);
            }
            QTabBar::tab {
                background-color: rgb(52, 59, 72);
                color: rgb(221, 221, 221);
                padding: 10px 15px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: rgb(189, 147, 249);
                color: rgb(255, 255, 255);
            }
            QTabBar::tab:hover:!selected {
                background-color: rgb(57, 65, 80);
            }
        """)
        
        # Style the list widget for databases
        self.ui.listWidget.setStyleSheet("""
            QListWidget {
                background-color: rgb(44, 49, 58);
                border-radius: 5px;
                border: 1px solid rgb(52, 59, 72);
                padding: 5px;
            }
            QListWidget::item {
                background-color: rgb(52, 59, 72);
                margin: 5px;
                border-radius: 5px;
                border: 1px solid rgb(44, 49, 58);
                padding: 8px;
            }
            QListWidget::item:hover {
                background-color: rgb(57, 65, 80);
                border: 1px solid rgb(61, 70, 86);
            }
            QListWidget::item:selected {
                background-color: rgb(189, 147, 249);
                border: 1px solid rgb(170, 132, 255);
            }
            QLabel {
                background: transparent;
                border: none;
                color: rgb(221, 221, 221);
                font-weight: bold;
            }
        """)
        
        # Style table views
        self.setTableStyle("""
            QTableView {
                background-color: rgb(33, 37, 43);
                border-radius: 5px;
                padding: 5px;
                gridline-color: rgb(44, 49, 58);
            }
            QTableView::item {
                border-color: rgb(44, 49, 58);
                padding: 5px;
            }
            QTableView::item:selected {
                background-color: rgb(189, 147, 249);
                color: rgb(255, 255, 255);
            }
            QHeaderView::section {
                background-color: rgb(52, 59, 72);
                color: rgb(221, 221, 221);
                padding: 10px;
                border: 1px solid rgb(44, 49, 58);
                font-weight: bold;
            }
            QScrollBar:horizontal {
                border: none;
                background: rgb(52, 59, 72);
                height: 14px;
                margin: 0px 15px 0px 15px;
                border-radius: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: rgb(85, 170, 255);
                min-width: 30px;
                border-radius: 7px;
            }
            QScrollBar::up-arrow:horizontal, QScrollBar::down-arrow:horizontal
            {
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal
            {
                background: none;
            }
        """)
        
        # Apply filter section improvements
        self.setupSearchFunctionality()
        self.styleFilterSection()
        
        # Add tooltips for better usability
        self.addTooltips()
        
        # Add a status bar for user feedback
        self.setupStatusBar()

    def setupIcons(self):
        """Set up icons for all buttons in the application"""
        # Define icon paths - will work with either SVG or PNG
        icon_paths = {
            "search": "icons/search.svg",
            "reset": "icons/reset.svg",
            "add": "icons/add.svg",
            "visualize": "icons/visualize.svg",
            "details": "icons/details.svg",
            "report": "icons/report.svg",
            "home": "icons/home.svg",
            "database": "icons/database.svg",
            "connect": "icons/connect.svg"
        }
        
        # Define fallback icon paths if SVG is not supported
        fallback_icons = {
            "search": ":/icons/images/icons/cil-magnifying-glass.png",
            "reset": ":/icons/images/icons/cil-loop-circular.png",
            "add": ":/icons/images/icons/cil-plus.png",
            "visualize": ":/icons/images/icons/cil-chart.png",
            "details": ":/icons/images/icons/cil-description.png",
            "report": ":/icons/images/icons/cil-file.png",
            "home": ":/icons/images/icons/cil-home.png",
            "database": ":/icons/images/icons/cil-folder-open.png",
            "connect": ":/icons/images/icons/cil-link.png"
        }
        
        # Helper function to load an icon with fallback
        def load_icon(key):
            primary_path = icon_paths.get(key)
            fallback_path = fallback_icons.get(key)
            
            if os.path.exists(primary_path):
                return QIcon(primary_path)
            elif fallback_path:
                return QIcon(fallback_path)
            else:
                print(f"Warning: No icon found for {key}")
                return QIcon()
        
        # Set icons for main navigation buttons
        self.ui.btn_home.setIcon(load_icon("home"))
        self.ui.btn_widgets.setIcon(load_icon("database"))
        self.ui.btn_new.setIcon(load_icon("add"))
        
        # Set icons for action buttons
        self.ui.filtersearch.setIcon(load_icon("search"))
        self.ui.resetFilterButton.setIcon(load_icon("reset"))
        self.ui.addDatabaseButton.setIcon(load_icon("add"))
        self.ui.visualizeDataButton.setIcon(load_icon("visualize"))
        self.ui.getDetailsButton.setIcon(load_icon("details"))
        self.ui.createReportButton.setIcon(load_icon("report"))
        
        # Set icon for connection related buttons
        if hasattr(self.ui, "btn_connect"):
            self.ui.btn_connect.setIcon(load_icon("connect"))
        
        # Set standard icon sizes
        standard_size = QSize(20, 20)
        small_size = QSize(16, 16)
        
        # Apply icon sizes to all buttons with icons
        for button in self.findChildren(QPushButton):
            if not button.icon().isNull():
                if any(x in button.objectName() for x in ["btn_", "filter", "search"]):
                    button.setIconSize(small_size)
                else:
                    button.setIconSize(standard_size)
                
                # Add a bit of padding to make buttons look better with icons
                button.setStyleSheet(button.styleSheet() + "padding-left: 5px;")

    # Enhancement to your MainWindow.__init__ method
    # Add this line after initializing UI components:
    def enhanceInitialization(self):
        """Add this code to your __init__ method to incorporate the icons"""
        # Existing initialization code...
        
        # Add the icon setup after UI initialization
        self.setupIcons()
        
        # Make the UI more user-friendly with tooltips and better styling
        self.addTooltips()
        self.setupStatusBar()
        
        # Apply consistent styling to all tables
        self.setTableStyle("""
            QTableView {
                background-color: rgb(33, 37, 43);
                border-radius: 5px;
                padding: 5px;
                gridline-color: rgb(44, 49, 58);
            }
            QTableView::item {
                border-color: rgb(44, 49, 58);
                padding: 5px;
            }
            QTableView::item:selected {
                background-color: rgb(189, 147, 249);
                color: rgb(255, 255, 255);
            }
            QHeaderView::section {
                background-color: rgb(52, 59, 72);
                color: rgb(221, 221, 221);
                padding: 10px;
                border: 1px solid rgb(44, 49, 58);
                font-weight: bold;
            }
        """)

    def setTableStyle(self, style):
        """Apply the given style to all table views in the application"""
        # First apply to any existing table views
        for tab_index in range(self.ui.tabWidget.count()):
            tab = self.ui.tabWidget.widget(tab_index)
            if tab:
                for table_view in tab.findChildren(QTableView):
                    table_view.setStyleSheet(style)
                for table_widget in tab.findChildren(QTableWidget):
                    table_widget.setStyleSheet(style)
        
        # Store the style to apply to future tables
        self._table_style = style

    def styleFilterSection(self):
        """Apply improved styles to the filter section"""
        # Create a frame for the filter area
        filter_frame = QFrame(self.ui.home)
        filter_frame.setGeometry(QRect(20, 20, 761, 130))
        filter_frame.setFrameShape(QFrame.StyledPanel)
        filter_frame.setFrameShadow(QFrame.Raised)
        filter_frame.setObjectName("filter_frame")
        
        # Create a layout for the filter frame
        filter_layout = QVBoxLayout(filter_frame)
        filter_layout.setContentsMargins(20, 20, 20, 20)
        filter_layout.setSpacing(10)
        
        # Create a title label
        title_label = QLabel("Search and Filter", filter_frame)
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: rgb(189, 147, 249);")
        filter_layout.addWidget(title_label)
        
        # Create a horizontal layout for the filter controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)
        
        # Test ID section
        test_id_layout = QVBoxLayout()
        test_id_label = QLabel("Test ID:", filter_frame)
        test_id_label.setAlignment(Qt.AlignLeft)
        self.ui.testID.setPlaceholderText("Enter Test ID")
        test_id_layout.addWidget(test_id_label)
        test_id_layout.addWidget(self.ui.testID)
        controls_layout.addLayout(test_id_layout)
        
        # Date section
        date_layout = QVBoxLayout()
        date_label = QLabel("Test Date:", filter_frame)
        date_label.setAlignment(Qt.AlignLeft)
        date_layout.addWidget(date_label)
        date_layout.addWidget(self.ui.testdate)
        controls_layout.addLayout(date_layout)
        
        # Buttons section
        button_layout = QVBoxLayout()
        button_layout.addStretch()
        
        buttons_row = QHBoxLayout()
        
        # Style the search button with an icon
        self.ui.filtersearch.setText("Search")
        self.ui.filtersearch.setIcon(QIcon("icons/search.png"))  # Make sure this icon exists
        self.ui.filtersearch.setIconSize(QSize(16, 16))
        self.ui.filtersearch.setStyleSheet("""
            QPushButton {
                background-color: rgb(85, 170, 255);
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgb(105, 180, 255);
            }
        """)
        
        # Style the reset button with an icon
        self.ui.resetFilterButton.setText("Reset")
        self.ui.resetFilterButton.setIcon(QIcon("icons/reset.png"))  # Make sure this icon exists
        self.ui.resetFilterButton.setIconSize(QSize(16, 16))
        
        buttons_row.addWidget(self.ui.filtersearch)
        buttons_row.addWidget(self.ui.resetFilterButton)
        button_layout.addLayout(buttons_row)
        
        controls_layout.addLayout(button_layout)
        filter_layout.addLayout(controls_layout)
        
        # Add the filter frame to the home layout
        # Note: You may need to adjust this based on your existing layout
        if hasattr(self.ui.home, 'layout') and self.ui.home.layout():
            self.ui.home.layout().addWidget(filter_frame)
        else:
            home_layout = QVBoxLayout(self.ui.home)
            home_layout.addWidget(filter_frame)
            self.ui.home.setLayout(home_layout)

    def setupStatusBar(self):
        """Set up a status bar for user feedback"""
        # Create a status bar if it doesn't exist
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        # Style the status bar
        self.statusBar.setStyleSheet("""
            QStatusBar {
                background-color: rgb(33, 37, 43);
                color: rgb(221, 221, 221);
                border-top: 1px solid rgb(44, 49, 58);
                padding: 5px;
            }
        """)
        
        # Add initial message
        self.statusBar.showMessage("Ready")
        
        # Connect signals to update status
        self.ui.filtersearch.clicked.connect(lambda: self.statusBar.showMessage("Filtering data..."))
        self.ui.resetFilterButton.clicked.connect(lambda: self.statusBar.showMessage("Filters reset"))
        self.ui.addDatabaseButton.clicked.connect(lambda: self.statusBar.showMessage("Select a database file to add"))
        self.ui.listWidget.itemClicked.connect(lambda: self.statusBar.showMessage("Loading database..."))
        self.ui.createReportButton.clicked.connect(lambda: self.statusBar.showMessage("Generating report..."))

    def addTooltips(self):
        """Add helpful tooltips to UI elements"""
        self.ui.testID.setToolTip("Enter the Test ID to filter by")
        self.ui.testdate.setToolTip("Select a date to filter tests by date")
        self.ui.filtersearch.setToolTip("Apply the filter to find matching tests")
        self.ui.resetFilterButton.setToolTip("Clear all filters and show all data")
        self.ui.addDatabaseButton.setToolTip("Add a new database file")
        self.ui.createReportButton.setToolTip("Generate a report for the selected test")
        self.ui.getDetailsButton.setToolTip("View detailed information for the selected test")
        self.ui.visualizeDataButton.setToolTip("Create visualizations of the selected test data")

    def filterByTestID(self):
        """Improved filter function with better user feedback"""
        test_id = self.ui.testID.text().strip()
        selected_date = self.ui.testdate.date().toString("yyyy-MM-dd")

        # Update status
        self.statusBar.showMessage(f"Filtering for Test ID: {test_id}, Date: {selected_date}")

        if not test_id and not selected_date:
            # Show a message to the user
            QMessageBox.information(self, "Filter Criteria", "Please enter at least one filter criteria.")
            self.statusBar.showMessage("No filter criteria provided")
            return

        current_tab = self.ui.tabWidget.currentWidget()
        if not current_tab:
            QMessageBox.warning(self, "No Tab Selected", "Please select a tab with test data first.")
            self.statusBar.showMessage("No tab selected for filtering")
            return
            
        # Look for QTableView or QTableWidget in the tab
        tableView = None
        if current_tab.layout():
            for i in range(current_tab.layout().count()):
                widget = current_tab.layout().itemAt(i).widget()
                if isinstance(widget, QTableView):
                    tableView = widget
                    break
        
        if not tableView:
            tableView = current_tab.findChild(QTableView)
            if not tableView:
                QMessageBox.warning(self, "No Data View", "No data table found in the current tab.")
                self.statusBar.showMessage("No data table found for filtering")
                return

        # Show a "Filtering..." progress message
        self.statusBar.showMessage("Applying filters, please wait...")
        QApplication.processEvents()  # Allow the UI to update
        
        # Get the current model
        currentModel = tableView.model()
        if not currentModel:
            QMessageBox.warning(self, "No Data Model", "The data table has no model to filter.")
            self.statusBar.showMessage("No data model found for filtering")
            return
            
        # Determine the source model
        sourceModel = currentModel
        if isinstance(currentModel, QSortFilterProxyModel):
            sourceModel = currentModel.sourceModel()
        
        # Create and configure the proxy model
        proxy_model = CustomFilterProxyModel(tableView)
        proxy_model.setSourceModel(sourceModel)
        proxy_model.setTestID(test_id)
        proxy_model.setSelectedDate(selected_date)
        
        # Set the model to the view
        tableView.setModel(proxy_model)
        
        # Set up selection handling
        self.setupQTableView(tableView, sourceModel)
        
        # Show results
        row_count = proxy_model.rowCount()
        self.statusBar.showMessage(f"Filter applied: Found {row_count} matching records")
        
        # Highlight the first row if available
        if row_count > 0:
            tableView.selectRow(0)
        
        # Visual feedback for user
        if row_count == 0:
            # No results found - show in a subtle, non-intrusive way
            result_label = QLabel(f"No matches found for the specified criteria", current_tab)
            result_label.setStyleSheet("color: rgb(255, 170, 127); padding: 10px; font-style: italic;")
            result_label.setAlignment(Qt.AlignCenter)
            
            # Add to layout if possible, or show as overlay
            if hasattr(current_tab, 'layout') and current_tab.layout():
                current_tab.layout().addWidget(result_label)
            else:
                result_label.setParent(tableView)
                result_label.move(tableView.width() // 2 - result_label.width() // 2, 
                                tableView.height() // 2 - result_label.height() // 2)
                result_label.show()
                # Schedule removal after 5 seconds
                QTimer.singleShot(5000, result_label.deleteLater)

    def setupSearchFunctionality(self):
        self.ui.filtersearch.clicked.connect(self.filterByTestID)
        self.ui.resetFilterButton.clicked.connect(self.resetFilter)

    def filterByTestID(self):
        test_id = self.ui.testID.text().strip()
        selected_date = self.ui.testdate.date().toString("yyyy-MM-dd")

        print(f"Filtering with TestID: '{test_id}', Date: '{selected_date}'")

        if not test_id and not selected_date:
            print("No filter criteria provided")
            return

        current_tab = self.ui.tabWidget.currentWidget()
        if not current_tab:
            print("No current tab selected")
            return
            
        # Look for QTableView or QTableWidget in the tab
        tableView = None
        if current_tab.layout():
            for i in range(current_tab.layout().count()):
                widget = current_tab.layout().itemAt(i).widget()
                if isinstance(widget, QTableView):
                    tableView = widget
                    print("Found QTableView in tab")
                    break
        
        if not tableView:
            tableView = current_tab.findChild(QTableView)
            if tableView:
                print("Found QTableView with findChild")
            else:
                print("No QTableView found in the current tab")
                return

        # Get the current model
        currentModel = tableView.model()
        if not currentModel:
            print("No model found in the TableView")
            return
            
        # Determine the source model
        sourceModel = currentModel
        if isinstance(currentModel, QSortFilterProxyModel):
            sourceModel = currentModel.sourceModel()
            print("Using existing proxy model's source")
        
        print(f"Source model found with {sourceModel.rowCount()} rows and {sourceModel.columnCount()} columns")
        
        # Create and configure the proxy model
        proxy_model = CustomFilterProxyModel(tableView)
        proxy_model.setSourceModel(sourceModel)
        proxy_model.setTestID(test_id)
        proxy_model.setSelectedDate(selected_date)
        
        # Set the model to the view
        tableView.setModel(proxy_model)
        
        # Set up selection handling
        self.setupQTableView(tableView, sourceModel)
        
        print(f"Filter applied, view now shows {proxy_model.rowCount()} rows")

    def resetFilter(self):
        print("Resetting filter")
        current_tab = self.ui.tabWidget.currentWidget()
        if not current_tab:
            print("No current tab selected")
            return
            
        # Look for QTableView in the tab
        tableView = None
        if current_tab.layout():
            for i in range(current_tab.layout().count()):
                widget = current_tab.layout().itemAt(i).widget()
                if isinstance(widget, QTableView):
                    tableView = widget
                    break
        
        if not tableView:
            tableView = current_tab.findChild(QTableView)
            if not tableView:
                print("No QTableView found in the current tab")
                return

        # Get the current model
        currentModel = tableView.model()
        if not currentModel:
            print("No model found in the TableView")
            return
            
        # If using a proxy model, restore the source model
        if isinstance(currentModel, QSortFilterProxyModel):
            sourceModel = currentModel.sourceModel()
            tableView.setModel(sourceModel)
            self.setupQTableView(tableView, sourceModel)
            print("Filter reset, restored original model")
            
            # Clear the text fields
            self.ui.testID.clear()
            # Reset date to current date
            self.ui.testdate.setDate(QDate.currentDate())

    def addDataBaseFromDir(self, path):
        if not os.path.isdir(path):
            raise ValueError(f"The provided path '{path}' is not a valid directory.")
            
        path = glob.glob(os.path.join(path, '*.db'))
        
        for file_path in path:
            item_widget = FileListWidgetItem(file_path)
            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())
            item.setData(Qt.UserRole, file_path)
            self.ui.listWidget.addItem(item)
            self.ui.listWidget.setItemWidget(item, item_widget)

    def addDatabase(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileNames(self, 'Select Database Files', '', 'Database Files (*.db);;All Files (*)', options=options)
        
        if fileName:
            fileName = fileName[0]
            existingPaths = [self.ui.listWidget.item(i).data(Qt.UserRole) for i in range(self.ui.listWidget.count())]
            for file in existingPaths:
                if self.comparePaths(fileName, file, home=os.getcwd()):
                    print(f"File '{fileName}' is already in the list.")
                    return
            item_widget = FileListWidgetItem(fileName)
            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())
            item.setData(Qt.UserRole, fileName)
            self.ui.listWidget.addItem(item)
            self.ui.listWidget.setItemWidget(item, item_widget)

    def populateTabs(self, file_path):
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        regExp = re.compile(re.escape("TestAna"), re.IGNORECASE)
        
        for table_name, in tables:
            pattern = r'[_\-\\p{P}\s]'
            s = re.sub(pattern, '', table_name)
            if regExp.search(s):
                tab = QWidget()
                tab_layout = QVBoxLayout()  
                tableWidget = QTableWidget()
                
                cursor.execute(f"SELECT * FROM {table_name};")
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                formattedColums = [self.formatString(column) for column in columns]

                tableWidget.setColumnCount(len(columns))
                tableWidget.setHorizontalHeaderLabels(formattedColums)
                tableWidget.setRowCount(len(rows))

                for row_idx, row in enumerate(rows):
                    for col_idx, value in enumerate(row):
                        item = QTableWidgetItem(str(value))
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        tableWidget.setItem(row_idx, col_idx, item)
                        
                # Create a QSortFilterProxyModel
                proxy_model = QSortFilterProxyModel()
                proxy_model.setSourceModel(tableWidget.model())  # Set the source model
                
                # Set the proxy model to the table view
                tableView = QTableView()
                tableView.setModel(proxy_model)
                
                # Set the selection behavior to select entire rows
                tableView.setSelectionBehavior(QTableView.SelectRows)
                
                # Add this line to set the stylesheet for the selected row
                tableView.setStyleSheet("""
                    QTableView::item:selected {
                        background-color: rgb(189, 147, 249); /* Change this color to your preference */
                    }
                """)
                
                tab_layout.addWidget(tableView)  # Add the table view to the tab layout
                self.setupQTableView(tableView, tableWidget.model())
                
                # Hide the QTableWidget
                tableWidget.setVisible(False)
                
                tableWidget.setSelectionBehavior(QTableWidget.SelectRows)
                tableWidget.setSelectionMode(QTableWidget.SingleSelection)
                tableWidget.itemSelectionChanged.connect(self.selectRow)

                tab_layout.addWidget(tableWidget)
                tab.setLayout(tab_layout)
                tab.setWindowTitle(self.formatString(table_name))
                self.ui.tabWidget.addTab(tab, self.formatString(table_name))
                
        self.widgetCache.save(self.ui.tabWidget, file_path)
        conn.close()
    def setupQTableView(self, tableView, sourceModel):
        # Set up selection handling for QTableView
        tableView.setSelectionMode(QTableView.SingleSelection)
        tableView.setSelectionBehavior(QTableView.SelectRows)
        tableView.selectionModel().selectionChanged.connect(self.onTableViewSelectionChanged)
        
    def onTableViewSelectionChanged(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            proxyModel = self.sender().model()
            sourceModel = proxyModel.sourceModel()
            
            # Get the selected row from the proxy model
            proxyRow = indexes[0].row()
            
            # Convert to source model row if using proxy
            sourceRow = proxyModel.mapToSource(indexes[0]).row()
            
            # Store selected row data similar to QTableWidget format
            columns = []
            items = []
            for column in range(sourceModel.columnCount()):
                headerData = sourceModel.headerData(column, Qt.Horizontal)
                columns.append(headerData)
                modelIndex = sourceModel.index(sourceRow, column)
                data = sourceModel.data(modelIndex)
                item = TableItem(data)
                item.setRow(sourceRow)
                items.append(item)
                
            self.lastSelectedRow = [columns, items] 


    def searchtest(self):
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()

        testid = self.ui.lineEdit.text()  

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        regExp = re.compile(re.escape("TestAna"), re.IGNORECASE)
        
        for table_name, in tables:
            pattern = r'[_\-\\p{P}\s]'
            s = re.sub(pattern, '', table_name)
            if regExp.search(s):
                tab = QWidget()
                tab_layout = QVBoxLayout()  
                tableWidget = QTableWidget()
                
                
                cursor.execute(f"SELECT * FROM {table_name};")
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                formattedColums = [self.formatString(column) for column in columns]

                tableWidget.setColumnCount(len(columns))
                tableWidget.setHorizontalHeaderLabels(formattedColums)
                tableWidget.setRowCount(len(rows))
    
                for row_idx, row in enumerate(rows):
                    for col_idx, value in enumerate(row):
                        item = QTableWidgetItem(str(value))
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        tableWidget.setItem(row_idx, col_idx, item)
                        
                tableWidget.setSelectionBehavior(QTableWidget.SelectRows)
                tableWidget.setSelectionMode(QTableWidget.SingleSelection)
                tableWidget.itemSelectionChanged.connect(self.selectRow)
    
                tab_layout.addWidget(tableWidget)
                tab.setLayout(tab_layout)
                tab.setWindowTitle(self.formatString(table_name))
                self.ui.tabWidget.addTab(tab, self.formatString(table_name))
                
        self.widgetCache.save(self.ui.tabWidget, file_path)
        conn.close()

    
        
        


        
    def selectRow(self):
        tableWidget = self.sender()
        selected_items = tableWidget.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            tableWidget.selectRow(row)
            columns = []
            for column in range(tableWidget.columnCount()):
                item = tableWidget.horizontalHeaderItem(column)
                if item:
                    columns.append(item.text())
            self.lastSelectedRow = [columns, selected_items]
            
    def getTestDetails(self):
        if self.lastSelectedRow is None:
            return
        
        try:
            file_path, testType, testId, hatId = self.findSelectedTest()
        except:
            print("No test selected or error in finding test details.")
            return

        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        regExp = re.compile(re.escape("TestDetay"), re.IGNORECASE)
        regExp2 = re.compile(re.escape("TestId"), re.IGNORECASE)
        pattern = r'[_\-\\p{P}\s]'
            
        for table_name, in tables:
            s = re.sub(pattern, '', table_name)
            if regExp.search(s):
                try:
                    tab = QWidget()
                    tab_layout = QVBoxLayout()  
                    tableWidget = QTableWidget()
                    
                    cursor.execute(f"SELECT * FROM {table_name};")
                    rows = cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    
                    i = next((column_idx for column_idx, column in enumerate(columns) if regExp2.search(re.sub(pattern, '', column)) is not None), None)

                    filteredRows = [row for row in rows if row[i] == int(testId)]
                    
                    formattedColums = [self.formatString(column) for column in columns]
                                        
                    tableWidget.setColumnCount(len(columns))
                    tableWidget.setHorizontalHeaderLabels(formattedColums)
                    tableWidget.setRowCount(len(filteredRows))
                    
                    for row_idx, row in enumerate(filteredRows):
                        for col_idx, value in enumerate(row):
                            item = QTableWidgetItem(str(value))
                            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                            item.setFlags(Qt.ItemIsEnabled)
                            tableWidget.setItem(row_idx, col_idx, item)
                            
                    tableWidget.setSelectionBehavior(QTableWidget.SelectRows)
                    tableWidget.setSelectionMode(QTableWidget.SingleSelection)
                    tableWidget.itemSelectionChanged.connect(self.selectRow)
                    
                    tab_name = f'Test Id: {testId}, Hat No: {hatId}' if hatId is not None else f'Test Id: {testId}'
                    tab_layout.addWidget(tableWidget)
                    tab.setLayout(tab_layout)
                    tab.setWindowTitle(tab_name)
                    
                    self.ui.tabWidget.addTab(tab, tab_name)
                    self.widgetCache.save(self.ui.tabWidget, file_path)
                except:
                    print(f"Error processing table '{table_name}': {e}")
                    pass
                
    def findSelectedTest(self):
        selected_items = self.ui.listWidget.selectedItems()
        
        if selected_items and self.lastSelectedRow:
            remPunct = r'[_\-\\p{P}\s]'
            patterns = [
                (re.compile(re.escape("DSCOIT"), re.IGNORECASE), 'DSC-OIT'),
                (re.compile(re.escape("MFI"), re.IGNORECASE), 'MFI'),
                (re.compile(re.escape("VICAT"), re.IGNORECASE), 'VICAT')
            ]
            
            selected_item = selected_items[0]
            file_path = selected_item.data(Qt.UserRole)
            
            testType = None

            if file_path:
                for pattern, test_type in patterns:
                    if pattern.search(re.sub(remPunct, '', file_path)) is not None:
                        testType = test_type
                
                regExp = re.compile(re.escape("TestId"), re.IGNORECASE)
                regExp2 = re.compile(re.escape("Hat"), re.IGNORECASE)
                
                if testType == 'VICAT':
                    if regExp2.search(re.sub(remPunct, '', self.lastSelectedRow[0][1])) is None:
                        print("00")
                        return

                # Iterate through the column names and find the column id belonging to 'TestId' and 'HatNum'
                i = next((column_idx for column_idx, column in enumerate(self.lastSelectedRow[0]) if regExp.search(re.sub(remPunct, '', column)) is not None), None)
                j = next((column_idx for column_idx, column in enumerate(self.lastSelectedRow[0]) if regExp2.search(re.sub(remPunct, '', column)) is not None), None)
                
                try:
                    testId = int(self.lastSelectedRow[1][i].data(0))
                    lineNum = int(self.lastSelectedRow[1][j].data(0))
                except:
                    lineNum = None
            return file_path, testType, testId, lineNum

    def createReport(self):
        try:
            file_path, testType, testId, lineNum = self.findSelectedTest()
        except:
            print("No test selected or error in finding test details.")
            return
                
        print(file_path)
        print(testType)
        print(testId)
        print(lineNum)
        filename = f'{testType}_{testId}_{lineNum}_Report.pdf' if lineNum is not None else f'{testType}_{testId}_Report.pdf'
        ReportCreator(filename=filename, testType=testType, test_db=file_path, test_ID=testId, line_num=lineNum)
    
    def visualizeData(self):
        try:
            file_path, testType, testId, lineNum = self.findSelectedTest()
        except:
            print("No test selected or error in finding test details.")
            return
        
        tab = QWidget()
        tab_name = 'Test'
        tab_layout = QGridLayout()
        tab.setLayout(tab_layout)
        tab.setWindowTitle(tab_name)
        
        data = self.getTestData(testType)
        
        # If data is None or empty, show a message and return
        if not data:
            message_label = QLabel("No data available to visualize")
            tab_layout.addWidget(message_label, 0, 0)
            self.ui.tabWidget.addTab(tab, tab_name)
            self.widgetCache.save(self.ui.tabWidget, file_path)
            return
        
        # Check if we have MFI data (dictionary) or graph data (list)
        if isinstance(data, dict) and data.get('type') == 'mfi_table':
            # For MFI test type, create a QTableWidget from the data
            columns = data.get('columns', [])
            tableWidget = QTableWidget()
            columnHeaders = [' Agirlik (gr)', ' Kesme Zam. (sn)', ' MVR (mm³/10dk)', ' MFR (gr/10dk)']
            
            num_cols = len(columns)
            num_rows = len(columns[0]) if num_cols > 0 and len(columns) > 0 else 0
            
            tableWidget.setRowCount(num_rows)
            tableWidget.setColumnCount(num_cols)
            tableWidget.setHorizontalHeaderLabels(columnHeaders)
            
            for col_index in range(num_cols):
                tableWidget.setColumnWidth(col_index, 100)
            if num_cols > 3:
                tableWidget.setColumnWidth(3, 150)
            
            for row_index, row_data in enumerate(columns):
                for col_index, item in enumerate(row_data):
                    cell = QTableWidgetItem(item if isinstance(item, str) and bool(item) else '-')
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    tableWidget.setItem(col_index, row_index, cell)
            
            # Add the table widget to the layout
            tab_layout.addWidget(tableWidget, 0, 0)
        else:
            # For other test types, data is a list of graph data
            dataset = []
            titles = []
            xAxises = []
            yAxises = []
            
            for sublist in data:
                dataset.append(sublist[0])
                titles.append(sublist[1])
                xAxises.append(sublist[2])
                yAxises.append(sublist[3])
            
            for index in range(len(dataset)):
                graphImage = self.createGraph(dataset[index], title=titles[index], xAxis=xAxises[index], yAxis=yAxises[index])
                graphPixmap = QPixmap.fromImage(graphImage)
                
                graphLabel = QLabel()
                graphLabel.setPixmap(graphPixmap)
                graphLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                if (len(dataset) % 2 != 0 and index == len(dataset) - 1):
                    tab_layout.addWidget(graphLabel, index // 2, 0, 1, 2)
                else:
                    tab_layout.addWidget(graphLabel, index // 2, index % 2)
                
            tab_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.ui.tabWidget.addTab(tab, tab_name)
        self.widgetCache.save(self.ui.tabWidget, file_path)
        
    def getTestData(self, testType):
        print(f"Getting data for test type: {testType}")
        remPunct = r'[_\-\\p{P}\s]'
        
        tabExp = re.compile(re.escape("TestId"), re.IGNORECASE)
        
        tab = None
        print(f"Searching through {self.ui.tabWidget.count()} tabs")
        
        for index in range(self.ui.tabWidget.count()):
            tab_text = self.ui.tabWidget.tabText(index)
            print(f"Checking tab {index}: '{tab_text}'")
            if tabExp.search(re.sub(remPunct, '', tab_text)):
                tab = self.ui.tabWidget.widget(index)
                print(f"Found matching tab: {tab_text}")
                break
        
        if tab is None:
            print("No tab with TestId found")
            return []
                
        if tab.layout() and tab.layout().count() > 0:
            # Try to find QTableView or QTableWidget in the tab
            table = None
            for i in range(tab.layout().count()):
                widget = tab.layout().itemAt(i).widget()
                if isinstance(widget, QTableView):
                    print("Found QTableView")
                    table = widget
                    break
                elif isinstance(widget, QTableWidget):
                    print("Found QTableWidget")
                    table = widget
                    break
            
            if table is None:
                print("No table widget found in tab")
                return []
            
            print(f"Found table of type: {type(table).__name__}")
        else:
            print("Tab has no layout or empty layout")
            return []
                    
        data = []
        
        if testType == 'DSC-OIT':
            patterns = [
                [re.compile(re.escape("Numune"), re.IGNORECASE), []],
                [re.compile(re.escape("Referans"), re.IGNORECASE), []],
                [re.compile(re.escape("Watt"), re.IGNORECASE), []],
                [re.compile(re.escape("TestSure"), re.IGNORECASE), []]
            ]
        elif testType == 'MFI':
            patterns = [
                [re.compile(re.escape("Agirlik"), re.IGNORECASE), []],
                [re.compile(re.escape("Zaman"), re.IGNORECASE), []],
                [re.compile(re.escape("MVR"), re.IGNORECASE), []],
                [re.compile(re.escape("MFR"), re.IGNORECASE), []]
            ]
        elif testType == 'VICAT':
            patterns = [
                [re.compile(re.escape("Sicaklik"), re.IGNORECASE), []],
                [re.compile(re.escape("Batma"), re.IGNORECASE), []]
            ]
        else: 
            return []  # Return empty list instead of None

        for column in range(table.columnCount() if isinstance(table, QTableWidget) else 
                     table.model().columnCount()):
    
            # Get column header text
            if isinstance(table, QTableWidget):
                item = table.horizontalHeaderItem(column)
                column_text = item.text() if item else ""
            else:  # QTableView
                model = table.model()
                column_text = model.headerData(column, Qt.Horizontal) or ""
            
            print(f"Column {column}: '{column_text}'")
            
            # Match patterns
            for pattern, columnData in patterns:
                if pattern.search(re.sub(remPunct, '', column_text)):
                    print(f"Pattern match: {pattern.pattern}")
                    columnData.extend(self.getColumnData(table, column))
        
        columns = [sublist[1] for sublist in patterns]
        
        if testType == 'DSC-OIT':
            data.append([[['Numune Sıcaklığı', columns[3], columns[0]], ['Referans Sıcaklığı', columns[3], columns[1]]], 'Sıcaklık Zaman Grafiği', 'Test Süresi', 'Sıcaklık'])
            data.append([[['Watt', columns[3], columns[2]]], 'Isı Zaman Grafiği', 'Test Süresi', 'Watt'])
            data.append([[['Isı', columns[0], columns[2]]], 'Isı Sıcaklık Grafiği', 'Sıcaklık', 'Isı'])
        elif testType == 'MFI':
            # For MFI, return a special dictionary that identifies it as MFI data
            return {'type': 'mfi_table', 'columns': columns}
        elif testType == 'VICAT':
            data.append([[['Batma', columns[1], columns[0]]], 'Sıcaklık Batma Grafiği', 'Sıcaklık', 'Batma'])
        
        return data  # Explicitly return data
    
    @staticmethod
    def getColumnData(table, index):
        column_data = []
        
        # Check if we have a QTableWidget
        if isinstance(table, QTableWidget):
            row_count = table.rowCount()
            for row in range(row_count):
                item = table.item(row, index)
                if item:
                    column_data.append(item.text())
        
        # Check if we have a QTableView
        elif isinstance(table, QTableView):
            model = table.model()
            if model:
                row_count = model.rowCount()
                for row in range(row_count):
                    model_index = model.index(row, index)
                    data = model.data(model_index)
                    if data:
                        column_data.append(str(data))
        
        # Print the data length for debugging
        print(f"Column {index} has {len(column_data)} data points")
        return column_data

    @staticmethod
    def comparePaths(path1, path2, home=None):
        
        def normalizePath(path, home=None):
            if home:
                path = os.path.join(home, path)
            return os.path.realpath(path)
        
        abs_path1 = normalizePath(path1, home)
        abs_path2 = normalizePath(path2, home)
        return abs_path1 == abs_path2

    @staticmethod
    def formatString(string):
        formattedString = string.replace('_', ' ')
        formattedString = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', formattedString)
        
        return formattedString

    @staticmethod
    def createGraph(data, title='Title', xAxis='xAxisLabel', yAxis='yAxisLabel'):
        def smooth_data(x, y, window_length=11, polyorder=2):
            try:
                # Convert to float if needed
                x_float = [float(val) if val not in (None, 'None') else 0.0 for val in x]
                y_float = [float(val) if val not in (None, 'None') else 0.0 for val in y]
                
                # Check if we have enough data points for the window length
                if len(y_float) < window_length:
                    window_length = max(min(len(y_float) // 2 * 2 - 1, 5), 3)  # Ensure odd number
                    polyorder = min(polyorder, window_length - 1)  # Polyorder must be less than window length
                
                return savgol_filter(y_float, window_length=window_length, polyorder=polyorder)
            except Exception as e:
                print(f"Error in smooth_data: {e}")
                return y  # Return original data if smoothing fails
        
        def prepareData(x, y):
            try:
                # Filter out None, 'None', and convert to float
                valid_indices = []
                for i in range(min(len(x), len(y))):
                    if x[i] not in (None, 'None') and y[i] not in (None, 'None'):
                        try:
                            float(x[i])
                            float(y[i])
                            valid_indices.append(i)
                        except (ValueError, TypeError):
                            pass
                
                x_cleaned = [float(x[i]) for i in valid_indices]
                y_cleaned = [float(y[i]) for i in valid_indices]
                return x_cleaned, y_cleaned
            except Exception as e:
                print(f"Error in prepareData: {e}")
                return [], []  # Return empty lists if preparation fails

        buf = BytesIO()
        
        try:
            plt.figure(figsize=(8, 6))
            
            valid_datasets = 0
            for dataset in data:
                try:
                    label, x, y = dataset
                    if not x or not y:  # Skip empty datasets
                        continue
                        
                    x, y = prepareData(x, y)
                    
                    if len(x) > 0 and len(y) > 0:  # Only plot if we have valid data
                        window_len = min(11, max(3, len(x) // 2 * 2 + 1))
                        polyorder = min(2, window_len - 1)
                        
                        if len(x) > 3:  # Need at least 3 points for smoothing
                            y_smooth = smooth_data(x, y, window_length=window_len, polyorder=polyorder)
                            plt.plot(x, y_smooth, label=label)
                        else:
                            plt.plot(x, y, label=label)
                        valid_datasets += 1
                except Exception as e:
                    print(f"Error plotting dataset: {e}")
                    continue
            
            if valid_datasets == 0:
                # Create a simple message if no valid datasets
                plt.text(0.5, 0.5, "No valid data to plot", 
                        horizontalalignment='center', verticalalignment='center',
                        transform=plt.gca().transAxes)
            else:
                plt.gca().xaxis.set_major_locator(AutoLocator())
                plt.gca().yaxis.set_major_locator(AutoLocator())
                
                # Use safe formatting (only if there's data)
                if len(x) > 0:
                    try:
                        plt.gca().xaxis.set_major_formatter(FormatStrFormatter('%d' if isinstance(x[0], int) else '%.2f'))
                        plt.gca().yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
                    except:
                        pass  # Fallback to default formatting
            
            plt.title(title)
            plt.xlabel(xAxis)
            plt.ylabel(yAxis)
            plt.grid(color='gray', linestyle='dashdot', linewidth=1)
            if valid_datasets > 0:
                plt.legend()
            
            plt.savefig(buf, format='png', bbox_inches='tight')
            plt.close()
            buf.seek(0)
            
            plot_image = QImage()
            plot_image.loadFromData(buf.getvalue())
            
            return plot_image
        except Exception as e:
            print(f"Error in createGraph: {e}")
            # Create a simple error image
            plt.figure(figsize=(8, 6))
            plt.text(0.5, 0.5, f"Error creating graph: {str(e)}", 
                    horizontalalignment='center', verticalalignment='center',
                    transform=plt.gca().transAxes)
            plt.savefig(buf, format='png', bbox_inches='tight')
            plt.close()
            buf.seek(0)
            
            plot_image = QImage()
            plot_image.loadFromData(buf.getvalue())
            
            return plot_image
    def updateTabs(self):
        self.ui.tabWidget.clear()
        self.lastSelectedRow = None
        
        selected_items = self.ui.listWidget.selectedItems()
        if selected_items:
            selected_item = selected_items[0]
            file_path = selected_item.data(Qt.UserRole)
            
            if file_path:
                if file_path in self.widgetCache.returnCache():
                    self.widgetCache.restore(self.ui.tabWidget, file_path)
                else:
                    self.populateTabs(file_path)
                   

    def setupComboBox(self):
        # Clear existing items
        self.ui.connection_combo_box.clear()

        # Read saved user data and populate the combo box
        try:
            with open('saved_user', 'r') as file:
                for line in file:
                    ip_address, username, password = line.strip().split(',')
                    self.ui.connection_combo_box.addItem(ip_address)
        except FileNotFoundError:
            print("No saved user file found.")

        self.ui.connection_combo_box.currentIndexChanged.connect(self.onComboBoxChange)

    def onComboBoxChange(self, index):
        # Read the saved_user file again to get the selected details
        try:
            with open('saved_user', 'r') as file:
                lines = file.readlines()
                if 0 <= index < len(lines):
                    ip_address, username, password = lines[index].strip().split(',')
                    self.ip_address = ip_address
                    self.username = username
                    self.password = password
                    print(f"Selected IP: {self.ip_address}, Username: {self.username}")
        except FileNotFoundError:
            print("No saved user file found.")

    # ssh_connect('192.168.1.1', 'krkrt', '78963', r'C:\Users\krkrt\Desktop\db\MFI.db', 'local_file.db')

    def sftp(self):
        
        ip_address, ok = QInputDialog.getText(self, "Connection Details", "Enter IPv4 Address:")
        print(type(ip_address))
        print(ip_address)
        print(type(self.ip_address))
        print(self.ip_address)
        if not ok:
            return
        
        username, ok = QInputDialog.getText(self, "Connection Details", "Enter Username:")
        print(type(username))
        print(username)
        print(type(self.username))
        print(self.username)
        if not ok:
            return
        password, ok = QInputDialog.getText(self, "Connection Details", "Enter Password:")
        print(type(password))
        print(password)
        print(type(self.password))
        print(self.password)
        if not ok:
            return
        
        QMessageBox.information(self, "Success", "")

        #eğer bağlantı başarılı ise kaydet yapılcak ama bağlantıyı deneyemiyorum
        with open('saved_user', 'a') as file:
            file.write(f"{ip_address},{username},{password}\n")

        self.setupComboBox()

        try:
        # Create an SSH client
            client = paramiko.SSHClient()
        # Automatically add the server's host key (this is insecure, consider using a known_hosts file)
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # Connect to the server
            client.connect(ip_address, username=username, password=password)
            print(f"Successfully connected to {ip_address}")

            remote_file = r'C:\Users\krkrt\Desktop\db\MFI.db'
            local_path = './databases/MFI.db'

        # Create an SFTP session
            sftp = client.open_sftp()
        # Transfer the file from remote to local
            sftp.get(remote_file, local_path)
            print(f"Successfully transferred {remote_file} to {local_path}")



            item_widget = FileListWidgetItem(local_path)
            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())
            item.setData(Qt.UserRole, local_path)
            self.ui.listWidget.addItem(item)
            self.ui.listWidget.setItemWidget(item, item_widget)

        # Close the SFTP session
            sftp.close()
        except paramiko.SSHException as e:
            print(f"SSH connection failed: {e}")
        except FileNotFoundError:
            print(f"File not found: {remote_file}")
        finally:
            client.close()

    def sftp_with_combobox(self):

        print(self.ip_address)
        print(self.username)
        print(self.password)

        try:
        # Create an SSH client
            client = paramiko.SSHClient()
        # Automatically add the server's host key (this is insecure, consider using a known_hosts file)
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # Connect to the server
            client.connect(self.ip_address, username=self.username, password=self.password)
            print(f"Successfully connected to {self.ip_address}")

            remote_file = r'C:\Users\krkrt\Desktop\db\MFI.db' #düzeltilcek
            local_path = './databases/MFI.db'# düzeltilcek

        # Create an SFTP session
            sftp = client.open_sftp()
        # Transfer the file from remote to local
            sftp.get(remote_file, local_path)
            print(f"Successfully transferred {remote_file} to {local_path}")



            item_widget = FileListWidgetItem(local_path)
            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())
            item.setData(Qt.UserRole, local_path)
            self.ui.listWidget.addItem(item)
            self.ui.listWidget.setItemWidget(item, item_widget)

        # Close the SFTP session
            sftp.close()
        except paramiko.SSHException as e:
            print(f"SSH connection failed: {e}")
        except FileNotFoundError:
            print(f"File not found: {remote_file}")
        finally:
            client.close()

    def addComboBoxItem(self, item_text):
        if item_text:
            self.ui.comboBox_2.addItem(item_text)
            print(f"Added item: {item_text} to comboBox")

    ################ New Record Window ################

    def newRecord(self):
        # Check if the company information file exists
        self.material_window = NewRecordWindow()
        self.material_window.show()


    def add_component_row(self):
        hbox = QHBoxLayout()
        input_name = QLineEdit()
        input_name.setPlaceholderText("Component Name")
        input_percent = PercentageLineEdit()
        input_percent.setPlaceholderText("Component Percent")
        supplier_name = QLineEdit()
        supplier_name.setPlaceholderText("Supplier Name")
        hbox.addWidget(input_name)
        hbox.addWidget(input_percent)
        hbox.addWidget(supplier_name)
        self.ui.component_layout_1.addLayout(hbox)
 
    def remove_component_row(self):
        if self.ui.component_layout_1.count() > 0:
            layout_item = self.ui.component_layout_1.takeAt(self.ui.component_layout_1.count() - 1)
            for i in reversed(range(layout_item.count())):
                layout_item.itemAt(i).widget().setParent(None)

    def save_to_sql(self):
        # Create database connection
        conn = sqlite3.connect('material_records.db')
        cursor = conn.cursor()

        # Create table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY,
                raw_material TEXT,
                supplier TEXT,
                manufacturing_date TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS components (
                material_id INTEGER,
                component_name TEXT,
                component_percent TEXT,
                FOREIGN KEY(material_id) REFERENCES materials(id)
            )
        ''')

        # Insert material information
        cursor.execute('''
            INSERT INTO materials (raw_material, supplier, manufacturing_date)
            VALUES (?, ?, ?)
        ''', (self.ui.input_raw_material_1.text(), self.ui.input_supplier.text(), self.ui.input_manufacturing_date_1.text()))

        material_id = cursor.lastrowid

        # Insert component information
        for i in range(self.ui.component_layout_1.count()):
            layout_item = self.ui.component_layout_1.itemAt(i)
            component_name = layout_item.itemAt(0).widget().text()
            component_percent = layout_item.itemAt(1).widget().text()
            cursor.execute('''
                INSERT INTO components (material_id, component_name, component_percent)
                VALUES (?, ?, ?)
            ''', (material_id, component_name, component_percent))

        conn.commit()
        conn.close()

        # Inform the user
        QMessageBox.information(self, "Success", "Record saved to SQL database successfully.")

    def save_to_txt(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save to Text File", "", "Text Files (*.txt);;All Files (*)", options=options)
        if file_path:
            with open(file_path, 'w') as file:
                file.write(f"Raw Material: {self.ui.input_raw_material_1.text()}\n")
                file.write("Components:\n")
                for i in range(self.ui.component_layout_1.count()):
                    layout_item = self.ui.component_layout_1.itemAt(i)
                    if layout_item is not None:
                        component_name_widget = layout_item.itemAt(0)
                        component_percent_widget = layout_item.itemAt(1)
                        supplier_name_widget = layout_item.itemAt(2)
                        
                        if component_name_widget and component_percent_widget and supplier_name_widget:
                            component_name = component_name_widget.widget().text()
                            component_percent = component_percent_widget.widget().text()
                            supplier_name = supplier_name_widget.widget().text()
                            file.write(f"  - {component_name}: {component_percent}% {supplier_name}\n")
                file.write(f"Manufacturing Date: {self.ui.input_manufacturing_date_1.text()}\n")

            # Inform the user
            QMessageBox.information(self, "Success", "Record saved to text file successfully.")

    def make_qrcode(self):
        if not self.ui.input_raw_material_1.text() or not self.ui.input_manufacturing_date_1.text():
            QMessageBox.warning(self, "Input Error", "Please fill in all the fields before generating a QR code.")
            return
        
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save QR Code", "", "PNG Files (*.png);;All Files (*)", options=options)
        if file_path:
            text = f"Raw Material: {self.ui.input_raw_material_1.text()}\nComponents:\n"
            for i in range(self.ui.component_layout_1.count()):
                layout_item = self.ui.component_layout_1.itemAt(i)
                if layout_item is not None:
                    component_name_widget = layout_item.itemAt(0)
                    component_percent_widget = layout_item.itemAt(1)
                    supplier_name_widget = layout_item.itemAt(2)
                    
                    if component_name_widget and component_percent_widget and supplier_name_widget:
                        component_name = component_name_widget.widget().text()
                        component_percent = component_percent_widget.widget().text()
                        supplier_name = supplier_name_widget.widget().text()
                        text += f"  - {component_name}: {component_percent}% {supplier_name}\n"
            text += f"Manufacturing Date: {self.ui.input_manufacturing_date_1.text()}"
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
            qr.add_data(text)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(file_path)
        
        QMessageBox.information(self, "Success", "QR Code generated and saved successfully.")

    


    def make_pdf(self):

        # if not self.input_raw_material.text() or not self.input_manufacturing_date.text():
        #     QMessageBox.warning(self, "Input Error", "Please fill in all the fields before generating a QR code.")
        #     return
        # else:
            component_name = self.ui.input_raw_material_1.text()
            PDFPSReporte(f'{component_name}.pdf', input_raw_material=self.ui.input_raw_material_1, input_manufacturing_date=self.ui.input_manufacturing_date_1, component_layout=self.ui.component_layout_1)

            QMessageBox.information(self, "Success", "PDF generated and saved successfully.")

    # BUTTONS CLICK
    # Post here your functions for clicked buttons
    # ///////////////////////////////////////////////////////////////
    def buttonClick(self):
        # GET BUTTON CLICKED
        btn = self.sender()
        btnName = btn.objectName()

        # SHOW HOME PAGE
        if btnName == "btn_home":
            widgets.stackedWidget.setCurrentWidget(widgets.home)
            UIFunctions.resetStyle(self, btnName)
            btn.setStyleSheet(UIFunctions.selectMenu(btn.styleSheet()))

        # SHOW WIDGETS PAGE
        if btnName == "btn_widgets":
            widgets.stackedWidget.setCurrentWidget(widgets.material_page)
            UIFunctions.resetStyle(self, btnName)
            btn.setStyleSheet(UIFunctions.selectMenu(btn.styleSheet()))

        # SHOW NEW PAGE
        if btnName == "btn_new":
            widgets.stackedWidget.setCurrentWidget(widgets.new_page) # SET PAGE
            UIFunctions.resetStyle(self, btnName) # RESET ANOTHERS BUTTONS SELECTED
            btn.setStyleSheet(UIFunctions.selectMenu(btn.styleSheet())) # SELECT MENU

        if btnName == "btn_save":
            print("Save BTN clicked!")

        # PRINT BTN NAME
        print(f'Button "{btnName}" pressed!')


    # RESIZE EVENTS
    # ///////////////////////////////////////////////////////////////
    def resizeEvent(self, event):
        # Update Size Grips
        UIFunctions.resize_grips(self)

    # MOUSE CLICK EVENTS
    # ///////////////////////////////////////////////////////////////
    def mousePressEvent(self, event):
        # SET DRAG POS WINDOW
        self.dragPos = event.globalPos()

        # PRINT MOUSE EVENTS
        if event.buttons() == Qt.LeftButton:
            print('Mouse click: LEFT CLICK')
        if event.buttons() == Qt.RightButton:
            print('Mouse click: RIGHT CLICK')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("alargepng.ico"))
    window = MainWindow()
    sys.exit(app.exec_())
