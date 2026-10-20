# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'recipes_page.ui'
##
## Created by: Qt User Interface Compiler version 6.8.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget)

class Ui_RecipesPage(object):
    def setupUi(self, RecipesPage):
        if not RecipesPage.objectName():
            RecipesPage.setObjectName(u"RecipesPage")
        RecipesPage.resize(1280, 720)
        self.recipes_page_layout = QVBoxLayout(RecipesPage)
        self.recipes_page_layout.setSpacing(8)
        self.recipes_page_layout.setObjectName(u"recipes_page_layout")
        self.recipes_page_layout.setContentsMargins(20, 12, 20, 12)
        self.recipes_header = QWidget(RecipesPage)
        self.recipes_header.setObjectName(u"recipes_header")
        self.recipes_header.setMinimumSize(QSize(0, 72))
        self.recipes_header.setMaximumSize(QSize(16777215, 72))
        self.recipes_header_layout = QHBoxLayout(self.recipes_header)
        self.recipes_header_layout.setSpacing(12)
        self.recipes_header_layout.setObjectName(u"recipes_header_layout")
        self.recipes_header_layout.setContentsMargins(0, 0, 0, 0)
        self.recipes_back_button = QPushButton(self.recipes_header)
        self.recipes_back_button.setObjectName(u"recipes_back_button")
        self.recipes_back_button.setMinimumSize(QSize(118, 54))
        self.recipes_back_button.setMaximumSize(QSize(118, 54))

        self.recipes_header_layout.addWidget(self.recipes_back_button)

        self.recipes_title_label = QLabel(self.recipes_header)
        self.recipes_title_label.setObjectName(u"recipes_title_label")
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        self.recipes_title_label.setFont(font)

        self.recipes_header_layout.addWidget(self.recipes_title_label)

        self.recipes_header_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.recipes_header_layout.addItem(self.recipes_header_spacer)

        self.recipes_port_label = QLabel(self.recipes_header)
        self.recipes_port_label.setObjectName(u"recipes_port_label")

        self.recipes_header_layout.addWidget(self.recipes_port_label)

        self.recipes_reconnect_button = QPushButton(self.recipes_header)
        self.recipes_reconnect_button.setObjectName(u"recipes_reconnect_button")
        self.recipes_reconnect_button.setMinimumSize(QSize(150, 54))
        self.recipes_reconnect_button.setMaximumSize(QSize(150, 54))

        self.recipes_header_layout.addWidget(self.recipes_reconnect_button)

        self.recipes_status_label = QLabel(self.recipes_header)
        self.recipes_status_label.setObjectName(u"recipes_status_label")
        self.recipes_status_label.setMinimumSize(QSize(150, 40))
        self.recipes_status_label.setMaximumSize(QSize(150, 40))
        self.recipes_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.recipes_header_layout.addWidget(self.recipes_status_label)

        self.recipes_global_stop_button = QPushButton(self.recipes_header)
        self.recipes_global_stop_button.setObjectName(u"recipes_global_stop_button")
        self.recipes_global_stop_button.setMinimumSize(QSize(158, 64))
        self.recipes_global_stop_button.setMaximumSize(QSize(158, 64))

        self.recipes_header_layout.addWidget(self.recipes_global_stop_button)


        self.recipes_page_layout.addWidget(self.recipes_header)

        self.recipes_content_layout = QHBoxLayout()
        self.recipes_content_layout.setObjectName(u"recipes_content_layout")
        self.recipes_content_left_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.recipes_content_layout.addItem(self.recipes_content_left_spacer)

        self.recipes_card = QFrame(RecipesPage)
        self.recipes_card.setObjectName(u"recipes_card")
        self.recipes_card.setMinimumSize(QSize(900, 430))
        self.recipes_card.setMaximumSize(QSize(900, 430))
        self.recipes_card.setFrameShape(QFrame.Shape.NoFrame)
        self.recipes_card_layout = QVBoxLayout(self.recipes_card)
        self.recipes_card_layout.setSpacing(12)
        self.recipes_card_layout.setObjectName(u"recipes_card_layout")
        self.recipes_card_layout.setContentsMargins(24, 20, 24, 20)
        self.recipe_selection_caption = QLabel(self.recipes_card)
        self.recipe_selection_caption.setObjectName(u"recipe_selection_caption")
        font1 = QFont()
        font1.setPointSize(16)
        font1.setBold(True)
        self.recipe_selection_caption.setFont(font1)

        self.recipes_card_layout.addWidget(self.recipe_selection_caption)

        self.recipe_combo = QComboBox(self.recipes_card)
        self.recipe_combo.setObjectName(u"recipe_combo")
        self.recipe_combo.setMinimumSize(QSize(0, 48))
        self.recipe_combo.setMaximumSize(QSize(16777215, 48))

        self.recipes_card_layout.addWidget(self.recipe_combo)

        self.recipe_details_layout = QGridLayout()
        self.recipe_details_layout.setObjectName(u"recipe_details_layout")
        self.recipe_details_layout.setHorizontalSpacing(18)
        self.recipe_details_layout.setVerticalSpacing(8)
        self.recipe_name_caption = QLabel(self.recipes_card)
        self.recipe_name_caption.setObjectName(u"recipe_name_caption")

        self.recipe_details_layout.addWidget(self.recipe_name_caption, 0, 0, 1, 1)

        self.recipe_name_label = QLabel(self.recipes_card)
        self.recipe_name_label.setObjectName(u"recipe_name_label")
        font2 = QFont()
        font2.setPointSize(14)
        font2.setBold(True)
        self.recipe_name_label.setFont(font2)

        self.recipe_details_layout.addWidget(self.recipe_name_label, 0, 1, 1, 1)

        self.recipe_step_caption = QLabel(self.recipes_card)
        self.recipe_step_caption.setObjectName(u"recipe_step_caption")

        self.recipe_details_layout.addWidget(self.recipe_step_caption, 1, 0, 1, 1)

        self.recipe_step_label = QLabel(self.recipes_card)
        self.recipe_step_label.setObjectName(u"recipe_step_label")
        font3 = QFont()
        font3.setPointSize(12)
        font3.setBold(True)
        self.recipe_step_label.setFont(font3)

        self.recipe_details_layout.addWidget(self.recipe_step_label, 1, 1, 1, 1)

        self.recipe_progress_caption = QLabel(self.recipes_card)
        self.recipe_progress_caption.setObjectName(u"recipe_progress_caption")

        self.recipe_details_layout.addWidget(self.recipe_progress_caption, 2, 0, 1, 1)

        self.recipe_progress_label = QLabel(self.recipes_card)
        self.recipe_progress_label.setObjectName(u"recipe_progress_label")
        self.recipe_progress_label.setFont(font3)

        self.recipe_details_layout.addWidget(self.recipe_progress_label, 2, 1, 1, 1)

        self.recipe_state_caption = QLabel(self.recipes_card)
        self.recipe_state_caption.setObjectName(u"recipe_state_caption")

        self.recipe_details_layout.addWidget(self.recipe_state_caption, 3, 0, 1, 1)

        self.recipe_state_label = QLabel(self.recipes_card)
        self.recipe_state_label.setObjectName(u"recipe_state_label")
        self.recipe_state_label.setFont(font3)

        self.recipe_details_layout.addWidget(self.recipe_state_label, 3, 1, 1, 1)

        self.recipe_error_label = QLabel(self.recipes_card)
        self.recipe_error_label.setObjectName(u"recipe_error_label")
        self.recipe_error_label.setWordWrap(True)

        self.recipe_details_layout.addWidget(self.recipe_error_label, 4, 0, 1, 2)


        self.recipes_card_layout.addLayout(self.recipe_details_layout)

        self.recipes_card_vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.recipes_card_layout.addItem(self.recipes_card_vertical_spacer)

        self.recipe_controls_layout = QHBoxLayout()
        self.recipe_controls_layout.setSpacing(12)
        self.recipe_controls_layout.setObjectName(u"recipe_controls_layout")
        self.recipe_start_button = QPushButton(self.recipes_card)
        self.recipe_start_button.setObjectName(u"recipe_start_button")
        self.recipe_start_button.setMinimumSize(QSize(220, 56))
        self.recipe_start_button.setMaximumSize(QSize(220, 56))

        self.recipe_controls_layout.addWidget(self.recipe_start_button)

        self.recipe_stop_button = QPushButton(self.recipes_card)
        self.recipe_stop_button.setObjectName(u"recipe_stop_button")
        self.recipe_stop_button.setMinimumSize(QSize(220, 56))
        self.recipe_stop_button.setMaximumSize(QSize(220, 56))

        self.recipe_controls_layout.addWidget(self.recipe_stop_button)

        self.recipe_controls_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.recipe_controls_layout.addItem(self.recipe_controls_spacer)


        self.recipes_card_layout.addLayout(self.recipe_controls_layout)


        self.recipes_content_layout.addWidget(self.recipes_card)

        self.recipes_content_right_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.recipes_content_layout.addItem(self.recipes_content_right_spacer)


        self.recipes_page_layout.addLayout(self.recipes_content_layout)

        self.recipes_page_bottom_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.recipes_page_layout.addItem(self.recipes_page_bottom_spacer)

        QWidget.setTabOrder(self.recipes_back_button, self.recipes_reconnect_button)
        QWidget.setTabOrder(self.recipes_reconnect_button, self.recipes_global_stop_button)
        QWidget.setTabOrder(self.recipes_global_stop_button, self.recipe_combo)
        QWidget.setTabOrder(self.recipe_combo, self.recipe_start_button)
        QWidget.setTabOrder(self.recipe_start_button, self.recipe_stop_button)

        self.retranslateUi(RecipesPage)

        QMetaObject.connectSlotsByName(RecipesPage)
    # setupUi

    def retranslateUi(self, RecipesPage):
        RecipesPage.setWindowTitle(QCoreApplication.translate("RecipesPage", u"Recipes", None))
        self.recipes_back_button.setText(QCoreApplication.translate("RecipesPage", u"BACK", None))
        self.recipes_title_label.setText(QCoreApplication.translate("RecipesPage", u"Recipes", None))
        self.recipes_port_label.setText(QCoreApplication.translate("RecipesPage", u"- disconnected", None))
        self.recipes_reconnect_button.setText(QCoreApplication.translate("RecipesPage", u"RECONNECT", None))
        self.recipes_status_label.setText(QCoreApplication.translate("RecipesPage", u"DISCONNECTED", None))
        self.recipes_global_stop_button.setText(QCoreApplication.translate("RecipesPage", u"STOP", None))
        self.recipe_selection_caption.setText(QCoreApplication.translate("RecipesPage", u"Recipe selection", None))
        self.recipe_name_caption.setText(QCoreApplication.translate("RecipesPage", u"Name", None))
        self.recipe_name_label.setText(QCoreApplication.translate("RecipesPage", u"-", None))
        self.recipe_step_caption.setText(QCoreApplication.translate("RecipesPage", u"Current step", None))
        self.recipe_step_label.setText(QCoreApplication.translate("RecipesPage", u"-", None))
        self.recipe_progress_caption.setText(QCoreApplication.translate("RecipesPage", u"Progress", None))
        self.recipe_progress_label.setText(QCoreApplication.translate("RecipesPage", u"step 0 / 0", None))
        self.recipe_state_caption.setText(QCoreApplication.translate("RecipesPage", u"State", None))
        self.recipe_state_label.setText(QCoreApplication.translate("RecipesPage", u"Stopped", None))
        self.recipe_error_label.setText("")
        self.recipe_start_button.setText(QCoreApplication.translate("RecipesPage", u"START RECIPE", None))
        self.recipe_stop_button.setText(QCoreApplication.translate("RecipesPage", u"STOP RECIPE", None))
    # retranslateUi

