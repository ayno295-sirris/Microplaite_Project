"""Qt style sheet."""

QSS = """
QMainWindow,
QWidget#appRoot {
    background: #f0f5fa;
    color: #0f1a29;
    font-family: Inter, Segoe UI, Arial, sans-serif;
}

QLabel {
    color: #0f1a29;
}

QLabel#pageTitle {
    font-size: 28px;
    font-weight: 800;
}

QLabel#portLabel,
QLabel#caption,
QLabel#smallText,
QLabel#bottomStatus {
    color: #4d5e73;
}

QLabel#portLabel {
    font-size: 16px;
}

QLabel#caption {
    font-size: 16px;
}

QLabel#captionLarge {
    color: #4d5e73;
    font-size: 20px;
}

QLabel#smallText {
    font-size: 13px;
}

QLabel#tinyText {
    color: #4d5e73;
    font-size: 12px;
}

QLabel#sectionTitle {
    font-size: 21px;
    font-weight: 800;
}

QLabel#trendLabel {
    color: #4d5e73;
    font-size: 13px;
    font-weight: 800;
}

QLabel#temperatureValue {
    font-size: 52px;
    font-weight: 900;
}

QLabel#detailTempValue {
    font-size: 48px;
    font-weight: 900;
}

QLabel#hugeValue {
    font-size: 58px;
    font-weight: 900;
}

QLabel#mediumValue {
    font-size: 30px;
    font-weight: 900;
}

QLabel#metricValue {
    font-size: 22px;
    font-weight: 900;
}

QLabel#footerValue {
    font-size: 20px;
    font-weight: 900;
}

QLabel#infoText {
    font-size: 18px;
    color: #0f1a29;
}

QLabel#pidName {
    color: #4d5e73;
    font-size: 18px;
}

QLabel#pidValue {
    color: #0f1a29;
    font-size: 18px;
    font-weight: 800;
}

QLabel#neoStateValue {
    color: #148f52;
    font-size: 58px;
    font-weight: 900;
}

QLabel#bottomStatus {
    font-size: 14px;
}

QFrame#card,
QFrame#temperatureCard,
QFrame#thermalCard,
QFrame#pumpCard,
QFrame#neoPixelCard,
QFrame#cameraCard {
    background: #ffffff;
    border: 1px solid #ccdbeb;
    border-radius: 18px;
}

QFrame#temperatureCard {
    border-radius: 22px;
}

QFrame#cameraPreview,
QFrame#cameraFullPreview,
QLabel#cameraPreview,
QLabel#cameraFullPreview {
    background: #141c29;
    border: 0;
    border-radius: 14px;
    color: #b2c4d6;
    font-size: 22px;
}

QFrame#cameraFullPreview,
QLabel#cameraFullPreview {
    border-radius: 18px;
}

QLabel#cameraText {
    color: #b2c4d6;
    font-size: 22px;
}

QFrame#statusDotOk,
QFrame#statusDotError {
    border: 0;
    border-radius: 6px;
}

QFrame#statusDotOk {
    background: #148f52;
}

QFrame#statusDotError {
    background: #d1142e;
}

QLabel#statusPillRunning,
QLabel#statusPillIdle,
QLabel#statusPillError,
QLabel#statusPillDisconnected {
    min-width: 132px;
    max-width: 172px;
    min-height: 32px;
    max-height: 38px;
    border-radius: 13px;
    padding: 4px 12px;
    color: #ffffff;
    font-size: 16px;
    font-weight: 900;
    qproperty-alignment: AlignCenter;
}

QLabel#statusPillRunning {
    background: #148f52;
}

QLabel#statusPillIdle {
    background: #216ee5;
}

QLabel#statusPillError {
    background: #d1142e;
}

QLabel#statusPillDisconnected {
    background: #4a5e73;
}

QPushButton {
    border: 0;
    border-radius: 18px;
    color: #ffffff;
    font-weight: 900;
}

QPushButton#primaryButton {
    background: #216ee5;
    font-size: 21px;
}

QPushButton#primaryButton:hover {
    background: #155fd2;
}

QPushButton#stopButton {
    background: #d1142e;
    font-size: 38px;
}

QPushButton#stopButtonCompact {
    background: #d1142e;
    font-size: 25px;
}

QPushButton#stopButtonSmall {
    background: #d1142e;
    font-size: 20px;
}

QPushButton#stopButton:hover,
QPushButton#stopButtonCompact:hover,
QPushButton#stopButtonSmall:hover {
    background: #b40f26;
}

QPushButton#secondaryButton {
    background: #4a5e73;
    font-size: 17px;
}

QPushButton#secondaryButton:hover {
    background: #3c5065;
}

QPushButton#smallDarkButton {
    background: #0f1a29;
    border-radius: 16px;
    font-size: 24px;
}

QPushButton#okButton {
    background: #148f52;
    font-size: 22px;
}

QPushButton:disabled {
    background: #9aa9b8;
    color: #eff4f8;
}

QProgressBar {
    background: #e5edf5;
    border: 0;
    border-radius: 7px;
}

QProgressBar::chunk {
    background: #216ee5;
    border-radius: 7px;
}

QSlider::groove:horizontal {
    background: #e5edf5;
    height: 18px;
    border-radius: 9px;
}

QSlider::sub-page:horizontal {
    background: #216ee5;
    border-radius: 9px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 1px solid #ccdbeb;
    width: 38px;
    margin: -10px 0;
    border-radius: 19px;
}

QSlider:disabled::sub-page:horizontal {
    background: #9aa9b8;
}

QSpinBox {
    min-height: 34px;
    border: 1px solid #ccdbeb;
    border-radius: 10px;
    padding: 2px 8px;
    background: #ffffff;
    color: #0f1a29;
    font-size: 17px;
}

QSpinBox:disabled {
    color: #4d5e73;
    background: #f5f8fb;
}

QPlainTextEdit#logBox {
    background: #0a121f;
    border: 0;
    border-radius: 12px;
    color: #e0f5ff;
    font-family: Consolas, monospace;
    font-size: 12px;
    padding: 8px 10px;
}
"""
