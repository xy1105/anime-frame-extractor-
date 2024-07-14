import sys
import subprocess
import importlib

def check_and_install_libraries():
    required_libraries = [
        'PyQt5',
        'opencv-python',
        'numpy',
        'cryptography',
        'appdirs'  # 添加 appdirs 到必需库列表
    ]

    for library in required_libraries:
        try:
            importlib.import_module(library.replace('-', '_'))
            print(f"{library} 已安装")
        except ImportError:
            print(f"{library} 未安装，正在安装...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", library])
            print(f"{library} 安装完成")

# 在程序开始时检查并安装必要的库
check_and_install_libraries()

import os
import cv2
import numpy as np
import logging
import json
import base64
import hashlib
import random
import time
import appdirs
from cryptography.fernet import Fernet
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QProgressBar, QSlider, QCheckBox, QGroupBox, QGridLayout, 
                             QMessageBox, QStyleOptionSlider, QStyle, QDialog, QTextBrowser, QComboBox,
                             QLineEdit, QListWidget, QAbstractItemView, QToolTip, QDialogButtonBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import QFont, QColor, QPainter, QMouseEvent, QPen, QBrush

app_name = "动漫抽帧"
app_author = "YourCompanyName"
app_dir = appdirs.user_data_dir(app_name, app_author)
os.makedirs(app_dir, exist_ok=True)
log_file = os.path.join(app_dir, 'frame_extractor_debug.log')

logging.basicConfig(filename=log_file, level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

class WatermarkProtection:
    def __init__(self, watermark):
        self.watermark = watermark
        self.key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.key)
        self.encrypted_watermark = self.encrypt_watermark()
        self.checksum = self.generate_checksum()

    def encrypt_watermark(self):
        return self.cipher_suite.encrypt(self.watermark.encode())

    def decrypt_watermark(self, encrypted):
        return self.cipher_suite.decrypt(encrypted).decode()

    def generate_checksum(self):
        return hashlib.sha256(self.encrypted_watermark).hexdigest()

    def verify_integrity(self):
        return self.checksum == hashlib.sha256(self.encrypted_watermark).hexdigest()

    def get_watermark(self):
        if self.verify_integrity():
            return self.decrypt_watermark(self.encrypted_watermark)
        return None

watermark_protection = WatermarkProtection("by笑颜")

class Settings:
    def __init__(self):
        self.filename = os.path.join(app_dir, "settings.json")
        self.default_settings = {
            "threshold": 15,
            "min_area": 500,
            "blur_size": 5,
            "reverse_video": False
        }
        self.load()

    def load(self):
        try:
            with open(self.filename, 'r') as f:
                self.settings = json.load(f)
        except FileNotFoundError:
            self.settings = self.default_settings
            self.save()

    def save(self):
        with open(self.filename, 'w') as f:
            json.dump(self.settings, f)

    def get(self, key):
        return self.settings.get(key, self.default_settings[key])

    def set(self, key, value):
        self.settings[key] = value
        self.save()

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("设置")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        self.threshold_edit = QLineEdit(str(settings.get("threshold")))
        layout.addWidget(QLabel("默认阈值:"))
        layout.addWidget(self.threshold_edit)
        
        self.min_area_edit = QLineEdit(str(settings.get("min_area")))
        layout.addWidget(QLabel("默认最小变化区域:"))
        layout.addWidget(self.min_area_edit)
        
        self.blur_size_edit = QLineEdit(str(settings.get("blur_size")))
        layout.addWidget(QLabel("默认模糊程度:"))
        layout.addWidget(self.blur_size_edit)
        
        self.reverse_video_check = QCheckBox("默认倒放视频")
        self.reverse_video_check.setChecked(settings.get("reverse_video"))
        layout.addWidget(self.reverse_video_check)
        
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        
        button_style = """
        QPushButton {
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            font-size: 16px;
            margin: 4px 2px;
            border-radius: 5px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        """
        ok_button.setStyleSheet(button_style)
        cancel_button.setStyleSheet(button_style.replace("#4CAF50", "#f44336").replace("#45a049", "#da190b"))
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

    def accept(self):
        self.settings.set("threshold", int(self.threshold_edit.text()))
        self.settings.set("min_area", int(self.min_area_edit.text()))
        self.settings.set("blur_size", int(self.blur_size_edit.text()))
        self.settings.set("reverse_video", self.reverse_video_check.isChecked())
        super().accept()

class HelpDialog(QDialog):
    def __init__(self, title, content):
        super().__init__()
        self.setWindowTitle(title)
        self.setFixedSize(500, 400)
        layout = QVBoxLayout()
        text_browser = QTextBrowser()
        text_browser.setHtml(content)
        layout.addWidget(text_browser)
        self.setLayout(layout)

class AEStyleSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)
        self.hover = False
        self.pressed = False
        self.floating_label = QLabel(self)
        self.floating_label.setStyleSheet("background-color: black; color: white; padding: 2px;")
        self.floating_label.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            option = QStyleOptionSlider()
            self.initStyleOption(option)
            groove_rect = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderGroove, self)
            handle_rect = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
            
            if groove_rect.contains(event.pos()):
                self.setValue(self.pixelPosToRangeValue(event.pos()))
                event.accept()
            elif handle_rect.contains(event.pos()):
                event.accept()
                self.pressed = True
                return super().mousePressEvent(event)
        
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.pressed:
            self.setValue(self.pixelPosToRangeValue(event.pos()))
        
        self.floating_label.setText(str(self.value()))
        self.floating_label.adjustSize()
        self.floating_label.move(event.pos().x() - self.floating_label.width() // 2, -25)
        self.floating_label.show()

        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.pressed = False
        self.floating_label.hide()
        return super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self.floating_label.hide()
        return super().leaveEvent(event)

    def pixelPosToRangeValue(self, pos):
        option = QStyleOptionSlider()
        self.initStyleOption(option)

        groove_rect = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderGroove, self)
        slider_length = self.style().pixelMetric(QStyle.PM_SliderLength, option, self)
        slider_min = groove_rect.x()
        slider_max = groove_rect.right() - slider_length + 1
        
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(),
                                              pos.x() - slider_min, slider_max - slider_min, option.upsideDown)

class AnimatedProgressBar(QProgressBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.setDuration(300)  # 300毫秒的动画时间

    def setValue(self, value):
        self.animation.setStartValue(self.value())
        self.animation.setEndValue(value)
        self.animation.start()

class VideoProcessor(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str, float, int)
    error = pyqtSignal(str)

    def __init__(self, input_path, output_path, threshold, min_area, blur_size, reverse_video):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.threshold = threshold
        self.min_area = min_area
        self.blur_size = blur_size if blur_size % 2 == 1 else blur_size + 1  # 确保模糊大小为奇数
        self.reverse_video = reverse_video

    def run(self):
        try:
            logging.info(f"开始处理视频: {self.input_path}")
            cap = cv2.VideoCapture(self.input_path)
            if not cap.isOpened():
                raise IOError("无法打开输入视频文件")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            logging.info(f"视频信息: 总帧数={total_frames}, FPS={fps}, 分辨率={width}x{height}")

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(self.output_path, fourcc, fps, (width, height))

            frames_to_keep = []
            prev_frame = None

            for i in range(total_frames):
                ret, frame = cap.read()
                if not ret:
                    logging.warning(f"在第 {i} 帧读取失败")
                    break

                if i < 5 or i > total_frames - 5:  # 保留开头和结尾的5帧
                    frames_to_keep.append(frame)
                    continue

                if prev_frame is None:
                    frames_to_keep.append(frame)
                    prev_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    prev_frame = cv2.GaussianBlur(prev_frame, (self.blur_size, self.blur_size), 0)
                    continue

                frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                frame_gray = cv2.GaussianBlur(frame_gray, (self.blur_size, self.blur_size), 0)

                diff = cv2.absdiff(frame_gray, prev_frame)
                _, thresh = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if any(cv2.contourArea(contour) > self.min_area for contour in contours):
                    frames_to_keep.append(frame)

                prev_frame = frame_gray
                self.progress.emit(int((i + 1) / total_frames * 100), os.path.basename(self.input_path))

            logging.info(f"保留了 {len(frames_to_keep)} 帧")

            if self.reverse_video:
                frames_to_keep = frames_to_keep[::-1]
                logging.info("视频帧已倒序")

            for frame in frames_to_keep:
                out.write(frame)

            cap.release()
            out.release()

            original_duration = total_frames / fps
            new_duration = len(frames_to_keep) / fps
            tw_speed = (new_duration / original_duration) * 100

            logging.info(f"处理完成。建议的TW速度: {tw_speed:.2f}%")
            self.finished.emit(f"处理成功完成！", tw_speed, len(frames_to_keep))
        except Exception as e:
            logging.exception("处理视频时发生错误")
            self.error.emit(f"处理视频时发生错误: {str(e)}")

class BatchProcessor(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, video_list, output_dir, threshold, min_area, blur_size, reverse_video):
        super().__init__()
        self.video_list = video_list
        self.output_dir = output_dir
        self.threshold = threshold
        self.min_area = min_area
        self.blur_size = blur_size
        self.reverse_video = reverse_video

    def run(self):
        try:
            for i, video_path in enumerate(self.video_list):
                output_path = os.path.join(self.output_dir, f"processed_{os.path.basename(video_path)}")
                processor = VideoProcessor(video_path, output_path, self.threshold, self.min_area, self.blur_size, self.reverse_video)
                processor.progress.connect(self.update_progress)
                processor.run()
                self.progress.emit(int((i + 1) / len(self.video_list) * 100), "总进度")
            self.finished.emit()
        except Exception as e:
            logging.exception("批量处理时发生错误")
            self.error.emit(str(e))

    def update_progress(self, value, filename):
        self.progress.emit(value, filename)

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.title = '动漫抽帧'
        self.settings = Settings()
        self.initUI()
        self.watermark_check_timer = QTimer(self)
        self.watermark_check_timer.timeout.connect(self.check_watermark)
        self.watermark_check_timer.start(random.randint(10000, 30000))

    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(100, 100, 800, 600)
        self.setFont(QFont("Microsoft YaHei", 10))

        main_layout = QVBoxLayout()

        # 文件选择部分
        file_group = QGroupBox("文件选择")
        file_layout = QGridLayout()
        
        self.input_label = QLabel('输入视频：未选择')
        file_layout.addWidget(self.input_label, 0, 0, 1, 2)
        
        input_button = QPushButton('选择输入视频')
        input_button.clicked.connect(self.select_input)
        file_layout.addWidget(input_button, 0, 2)

        settings_button = QPushButton('设置')
        settings_button.clicked.connect(self.open_settings)
        file_layout.addWidget(settings_button, 0, 3)

        self.output_label = QLabel('输出路径：未设置')
        file_layout.addWidget(self.output_label, 1, 0, 1, 2)
        
        self.output_mode = QComboBox()
        self.output_mode.addItems(['自动生成', '手动选择'])
        self.output_mode.currentIndexChanged.connect(self.toggle_output_selection)
        file_layout.addWidget(self.output_mode, 1, 2)
        
        self.output_button = QPushButton('选择输出路径')
        self.output_button.clicked.connect(self.select_output)
        self.output_button.setEnabled(False)
        file_layout.addWidget(self.output_button, 1, 3)

        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)

        # 参数设置部分
        param_group = QGroupBox("参数设置")
        param_layout = QGridLayout()

        self.create_ae_style_slider(param_layout, '阈值：', 0, 30, self.settings.get("threshold"), 0, self.get_threshold_help)
        self.create_ae_style_slider(param_layout, '最小变化区域：', 0, 2000, self.settings.get("min_area"), 1, self.get_min_area_help)
        self.create_ae_style_slider(param_layout, '模糊程度：', 0, 30, self.settings.get("blur_size"), 2, self.get_blur_help)

        self.reverse_video = QCheckBox('倒放视频')
        self.reverse_video.setChecked(False)
        param_layout.addWidget(self.reverse_video, 3, 0, 1, 4)

        param_group.setLayout(param_layout)
        main_layout.addWidget(param_group)

        # 批量处理部分
        batch_group = QGroupBox("批量处理")
        batch_layout = QVBoxLayout()

        self.video_list = QListWidget()
        self.video_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        batch_layout.addWidget(self.video_list)

        batch_buttons_layout = QHBoxLayout()
        add_videos_button = QPushButton("添加视频")
        add_videos_button.clicked.connect(self.add_videos)
        batch_buttons_layout.addWidget(add_videos_button)

        remove_videos_button = QPushButton("移除选中视频")
        remove_videos_button.clicked.connect(self.remove_videos)
        batch_buttons_layout.addWidget(remove_videos_button)

        clear_videos_button = QPushButton("清空列表")
        clear_videos_button.clicked.connect(self.clear_videos)
        batch_buttons_layout.addWidget(clear_videos_button)

        batch_layout.addLayout(batch_buttons_layout)

        batch_group.setLayout(batch_layout)
        main_layout.addWidget(batch_group)

        # 处理和进度部分
        process_group = QGroupBox("处理")
        process_layout = QVBoxLayout()

        self.process_button = QPushButton('处理视频')
        self.process_button.clicked.connect(self.process_video)
        process_layout.addWidget(self.process_button)

        self.batch_process_button = QPushButton('批量处理视频')
        self.batch_process_button.clicked.connect(self.batch_process_videos)
        process_layout.addWidget(self.batch_process_button)

        self.progress_bar = AnimatedProgressBar()
        self.progress_bar.setTextVisible(False)
        process_layout.addWidget(self.progress_bar)

        self.status_label = QLabel('')
        process_layout.addWidget(self.status_label)

        self.tw_speed_label = QLabel('')
        process_layout.addWidget(self.tw_speed_label)

        process_group.setLayout(process_layout)
        main_layout.addWidget(process_group)

        # 添加水印
        self.watermark_label = QLabel(watermark_protection.get_watermark(), self)
        self.watermark_label.setStyleSheet("color: black; font-family: Arial;")
        self.watermark_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        main_layout.addWidget(self.watermark_label)

        self.setLayout(main_layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 调整水印位置到右下角
        self.watermark_label.setGeometry(
            self.width() - self.watermark_label.width() - 10,
            self.height() - self.watermark_label.height() - 10,
            self.watermark_label.width(),
            self.watermark_label.height()
        )

    def create_ae_style_slider(self, layout, label_text, min_value, max_value, default_value, row, help_func):
        layout.addWidget(QLabel(label_text), row, 0)
        slider = AEStyleSlider(Qt.Horizontal)
        slider.setRange(min_value, max_value)
        slider.setValue(default_value)
        layout.addWidget(slider, row, 1)
        
        value_edit = QLineEdit(str(default_value))
        value_edit.setFixedWidth(50)
        layout.addWidget(value_edit, row, 2)
        
        help_button = QPushButton('?')
        help_button.setFixedSize(20, 20)
        help_button.setStyleSheet("""
            QPushButton {
                border: 1px solid #bbb;
                border-radius: 10px;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        help_button.clicked.connect(lambda: self.show_help_dialog(f"{label_text[:-1]}详细说明", help_func()))
        layout.addWidget(help_button, row, 3)

        slider.valueChanged.connect(lambda v: value_edit.setText(str(v)))
        value_edit.editingFinished.connect(lambda: self.update_slider_from_edit(slider, value_edit, min_value, max_value))
        
        setattr(self, f"{label_text.lower().replace('：', '').replace(' ', '_')}_slider", slider)
        setattr(self, f"{label_text.lower().replace('：', '').replace(' ', '_')}_edit", value_edit)

    def update_slider_from_edit(self, slider, edit, min_value, max_value):
        try:
            value = int(edit.text())
            if min_value <= value <= max_value:
                slider.setValue(value)
            else:
                edit.setText(str(slider.value()))
        except ValueError:
            edit.setText(str(slider.value()))

    def show_help_dialog(self, title, content):
        dialog = HelpDialog(title, content)
        dialog.exec_()

    def select_input(self):
        fname, _ = QFileDialog.getOpenFileName(self, '选择输入视频', '', '视频文件 (*.mp4 *.avi)')
        if fname:
            self.input_label.setText(f'输入视频：{fname}')
            self.input_path = fname
            if self.output_mode.currentText() == '自动生成':
                self.generate_output_path()

    def toggle_output_selection(self, index):
        if index == 0:  # 自动生成
            self.output_button.setEnabled(False)
            if hasattr(self, 'input_path'):
                self.generate_output_path()
        else:  # 手动选择
            self.output_button.setEnabled(True)

    def generate_output_path(self):
        input_dir = os.path.dirname(self.input_path)
        input_name = os.path.splitext(os.path.basename(self.input_path))[0]
        self.output_path = os.path.join(input_dir, f"{input_name}_processed.mp4")
        self.output_label.setText(f'输出路径：{self.output_path}')

    def select_output(self):
        fname, _ = QFileDialog.getSaveFileName(self, '选择输出视频', '', '视频文件 (*.mp4)')
        if fname:
            self.output_label.setText(f'输出路径：{fname}')
            self.output_path = fname

    def add_videos(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择视频文件", "", "视频文件 (*.mp4 *.avi)")
        self.video_list.addItems(files)

    def remove_videos(self):
        for item in self.video_list.selectedItems():
            self.video_list.takeItem(self.video_list.row(item))

    def clear_videos(self):
        self.video_list.clear()

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_():
            self.load_settings()

    def load_settings(self):
        self.阈值_slider.setValue(self.settings.get("threshold"))
        self.最小变化区域_slider.setValue(self.settings.get("min_area"))
        self.模糊程度_slider.setValue(self.settings.get("blur_size"))
        self.reverse_video.setChecked(self.settings.get("reverse_video"))

    def process_video(self):
        if not hasattr(self, 'input_path'):
            self.status_label.setText('请选择输入视频。')
            return
        if self.output_mode.currentText() == '手动选择' and not hasattr(self, 'output_path'):
            self.status_label.setText('请选择输出路径。')
            return

        try:
            logging.info("开始视频处理")
            self.processor = VideoProcessor(
                self.input_path, 
                self.output_path, 
                self.阈值_slider.value(),
                self.最小变化区域_slider.value(),
                self.模糊程度_slider.value(),
                self.reverse_video.isChecked()
            )
            self.processor.progress.connect(self.update_progress)
            self.processor.finished.connect(self.process_finished)
            self.processor.error.connect(self.process_error)
            self.processor.start()
            self.process_button.setEnabled(False)
            self.batch_process_button.setEnabled(False)
            self.status_label.setText('处理中...')
        except Exception as e:
            logging.exception("启动视频处理时发生错误")
            QMessageBox.critical(self, "错误", f"启动视频处理时发生错误: {str(e)}")

    def batch_process_videos(self):
        if self.video_list.count() == 0:
            QMessageBox.warning(self, "警告", "请先添加要处理的视频")
            return

        output_dir = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if not output_dir:
            return

        video_list = [self.video_list.item(i).text() for i in range(self.video_list.count())]
        
        self.batch_processor = BatchProcessor(
            video_list,
            output_dir,
            self.阈值_slider.value(),
            self.最小变化区域_slider.value(),
            self.模糊程度_slider.value(),
            self.reverse_video.isChecked()
        )
        self.batch_processor.progress.connect(self.update_batch_progress)
        self.batch_processor.finished.connect(self.batch_process_finished)
        self.batch_processor.error.connect(self.process_error)
        self.batch_processor.start()
        
        self.process_button.setEnabled(False)
        self.batch_process_button.setEnabled(False)
        self.status_label.setText('批量处理中...')

    def update_progress(self, value, filename):
        self.progress_bar.setValue(value)
        self.status_label.setText(f'正在处理: {filename} - {value}%')

    def update_batch_progress(self, value, filename):
        if filename == "总进度":
            self.progress_bar.setValue(value)
            self.status_label.setText(f'批量处理进度: {value}%')
        else:
            self.status_label.setText(f'正在处理: {filename} - {value}%')

    def process_finished(self, message, tw_speed, kept_frames):
        deeper_red = QColor(255, 100, 100)
        self.status_label.setText(f"{message}保留了 <font color='{deeper_red.name()}'>{kept_frames}</font> 帧。")
        self.tw_speed_label.setText(f"建议在TW中将速度设置为 <font color='{deeper_red.name()}'>{tw_speed:.2f}%</font> 以恢复原视频时长")
        self.process_button.setEnabled(True)
        self.batch_process_button.setEnabled(True)
        self.progress_bar.setValue(100)  # 确保进度条显示100%
        QMessageBox.information(self, "处理完成", f"{message}\n保留了 {kept_frames} 帧。\n\n建议在TW中将速度设置为 {tw_speed:.2f}% 以恢复原视频时长")

    def batch_process_finished(self):
        self.status_label.setText("批量处理完成")
        self.process_button.setEnabled(True)
        self.batch_process_button.setEnabled(True)
        self.progress_bar.setValue(100)
        QMessageBox.information(self, "批量处理完成", "所有视频处理完成")

    def process_error(self, error_message):
        self.status_label.setText(error_message)
        self.process_button.setEnabled(True)
        self.batch_process_button.setEnabled(True)
        QMessageBox.critical(self, "错误", error_message)

    def check_watermark(self):
        if not watermark_protection.verify_integrity():
            self.close()
        self.watermark_check_timer.setInterval(random.randint(10000, 30000))

    def get_threshold_help(self):
        return """
        <h3>阈值</h3>
        <p>阈值决定了多大的变化被认为是"显著"的。</p>
        <ul>
            <li>调整范围：0-30</li>
            <li>较低的值会捕捉更多细微的变化。</li>
            <li>较高的值只会捕捉大的变化。</li>
        </ul>
        <p>建议：</p>
        <ul>
            <li>对于动作快速的动画，使用较低的阈值（如5-15）。</li>
            <li>对于变化缓慢的场景，使用较高的阈值（如20-30）。</li>
            <li>开始时可以尝试使用15作为基准，然后根据结果进行调整。</li>
        </ul>
        """

    def get_min_area_help(self):
        return """
        <h3>最小变化区域</h3>
        <p>定义被认为是"显著"变化的最小区域大小（以像素为单位）。</p>
        <ul>
            <li>调整范围：0-2000 像素</li>
            <li>较小的值会捕捉更多细节变化。</li>
            <li>较大的值只会捕捉大面积的变化。</li>
        </ul>
        <p>建议：</p>
        <ul>
            <li>对于需要捕捉细微表情变化的场景，使用较小的值（如100-300）。</li>
            <li>对于只关注大幅度动作的场景，使用较大的值（如1000-2000）。</li>
            <li>一般情况下，500是一个不错的起始值。</li>
        </ul>
        """

    def get_blur_help(self):
        return """
        <h3>模糊程度</h3>
        <p>在比较帧之前对图像进行模糊处理，减少噪声影响。</p>
        <ul>
            <li>调整范围：0-30（实际使用时会转换为奇数）</li>
            <li>较小的值保留更多细节，但可能更容易受噪声影响。</li>
            <li>较大的值会模糊更多细节，但能更好地抵抗噪声。</li>
        </ul>
        <p>建议：</p>
        <ul>
            <li>对于高质量、低噪声的视频，使用较小的值（如3-7）。</li>
            <li>对于有些模糊或有噪点的视频，使用较大的值（如11-15）。</li>
            <li>通常情况下，5是一个比较平衡的选择。</li>
        </ul>
        """

    def closeEvent(self, event):
        # 正常关闭程序时删除日志文件
        if os.path.exists(log_file):
            try:
                os.remove(log_file)
            except:
                pass  # 如果无法删除，静默失败
        super().closeEvent(event)

def validate_watermark():
    if not watermark_protection.verify_integrity():
        print("程序完整性检查失败")
        time.sleep(random.random())
        sys.exit(1)

def a1b2c3d4e5f6g7h8i9j0(x):
    return x()

def exception_hook(exctype, value, traceback):
    logging.error("Uncaught exception", exc_info=(exctype, value, traceback))
    sys.__excepthook__(exctype, value, traceback)

if __name__ == '__main__':
    sys.excepthook = exception_hook
    a1b2c3d4e5f6g7h8i9j0(validate_watermark)
    try:
        app = QApplication(sys.argv)
        ex = App()
        ex.show()
        sys.exit(app.exec_())
    except Exception as e:
        logging.exception("程序执行时发生未捕获的异常")
        QMessageBox.critical(None, "严重错误", f"程序发生未预期的错误:\n{str(e)}\n\n请查看日志文件获取详细信息。")
