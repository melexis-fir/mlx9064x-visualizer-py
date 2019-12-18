import os, sys
# work-around for having the parent directory added to the search path of packages.
# to make `import mlx.pympt` to work, even EVB pip package itself is not installed!
# note: when installed, it will take the installed version!
# https://chrisyeh96.github.io/2017/08/08/definitive-guide-python-imports.html#case-2-syspath-could-change
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "mlx9064x-driver-py"))

import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QCheckBox, QComboBox, QLineEdit, QInputDialog
from PyQt5.QtGui import QIcon, QPixmap, QImage, QFont, QIntValidator, QDoubleValidator
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, Qt
from pyqtgraph.Qt import QtCore
from matplotlib import cm
import pyqtgraph as pg
from mlx.mlx90640 import Mlx9064x, Mlx9064xFilters

import numpy as np
import time
import struct
from scipy import interpolate
import serial



class  Thread_Visualizer(QThread):
    """
    This thread is used to read frames from the EVB, filter these frames, apply
    interpolation and send the frames to the main thread for visualization.
    Possible filters are:
        - de-interlace filter
        - IIR filter
        - TGC filter
    """
    sig = pyqtSignal(np.ndarray)
    def run(self):
        global dev
        global interpolation_factor
        global depth
        global threshold
        global deinterlace_filter_enabled
        global iir_filter_enabled
        global frame_rate

        self.isRunning = True
        self.init = False

        while self.isRunning:
            # Get frame from EVB90640
            try:
                frame = dev.read_frame()
            except:
                dev.clear_error(frame_rate)
                print("error")
            else:
                if frame is not None:
                    # Calculate temperature for each pixel
                    f = dev.do_compensation(frame)
                    ir_image = np.resize(f, (24, 32))

                    # De-interlace filter
                    if deinterlace_filter_enabled:
                        ctrl_reg_1, status = dev.i2c_read(0x800D, 2)
                        try:
                                ctrl_reg_1 = struct.unpack(">H", ctrl_reg_1)[0]  # TODO find endian
                        except:
                            ctrl_reg_1  = 0
                            print("missed")
                        #subpage = struct.unpack("<BB",dev.i2c_read(0x8000,2)[0])[1]
                        if ctrl_reg_1 > 0:
                            page = 1
                        else:
                            page = 0
                        de_interlaced = Mlx9064xFilters.deinterlace_filter(ir_image, page)
                        ir_image = de_interlaced

                    # IIR filter
                    if iir_filter_enabled:
                        if self.init == False:
                            iir_filtered = ir_image
                            cnt = np.ones([24, 32])
                            self.init = True
                        iir_filtered, cnt = Mlx9064xFilters.iir_filter(ir_image, iir_filtered, cnt, depth, threshold)
                        ir_image = iir_filtered

                    # TGC filter
                    # to be implemented

                    # Interpolate ir_image x times
                    x = np.linspace(0,31,32)
                    y = np.linspace(0,23,24)
                    f = interpolate.interp2d(x, y, ir_image, kind='cubic')
                    xx = np.linspace(0,31,32*interpolation_factor)
                    yy = np.linspace(0,23,24*interpolation_factor)
                    ir_image = f(xx, yy)

                    # Send ir_image_new to updateIrImage
                    self.sig.emit(ir_image)

    def stop(self):
        self.isRunning = False


class App(QWidget):
    """
    This thread is used to creating and updating the GUI. All button, textboxes, ...
    are defined in this class.
    """
    def __init__(self):
        super().__init__()
        self.title = 'EVB MLX90640'
        self.left = 30
        self.top = 30
        self.width = 830
        self.height = 500
        self.initUI()

    @pyqtSlot(np.ndarray)
    def updatIrImage(self, ir_image):
        if self.autoscale:
            self.p1.setImage(np.rot90(ir_image))
        else:
            self.p1.setImage(np.rot90(ir_image), levels=[self.minT, self.maxT])

    def initUI(self):
        global run
        run = False

        self.autoscale = True
        self.minT = 20.0
        self.maxT = 35.0
        self.inv_X = True
        self.inv_Y = True
        self.fps = 2

        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon('./melexis_logo.png'))
        self.setGeometry(self.left, self.top, self.width, self.height)

        pos = np.linspace(0., 1.0, 128)
        color = cm.jet(pos)
        cmap = pg.ColorMap(pos, color)
        lut = cmap.getLookupTable(0.0, 1.0, 256)

        # Create a viewbox for the ir image
        ir_image = np.zeros([24,32])
        self.gv1 = pg.GraphicsView(self)
        self.gv1.move(10,10)
        self.gv1.resize(640,480)
        self.l1 = pg.GraphicsLayout()
        self.vb1 = pg.ViewBox()
        self.gv1.setCentralWidget(self.vb1)
        self.p1 = pg.ImageItem()
        self.vb1.addItem(self.p1)
        self.vb1.invertY(self.inv_Y)
        self.vb1.invertX(self.inv_X)
        self.p1.setLookupTable(lut)
        self.p1.setImage(np.rot90(ir_image))
        self.vb1.show()

        # Create the start/stop button
        self.btn1 = QPushButton("Start", self)
        self.btn1.clicked.connect(self.start_visualizer)
        self.btn1.resize(120,40)
        self.btn1.move(700,450)

        # Create horizontal/vertical mirror buttons
        self.btn2 = QPushButton("Mirror horizontal", self)
        self.btn2.clicked.connect(self.mirror_horizontal)
        self.btn2.resize(120,40)
        self.btn2.move(700,350)
        self.btn3 = QPushButton("Mirror vertical", self)
        self.btn3.clicked.connect(self.mirror_vertical)
        self.btn3.resize(120,40)
        self.btn3.move(700,300)

        # Set interpolation factor
        self.labelInterpolation = QLabel(self)
        self.labelInterpolation.setText("Interpolation ")
        self.labelInterpolation.setAlignment(Qt.AlignRight)
        self.labelInterpolation.resize(100,20)
        self.labelInterpolation.move(660,12)

        self.comboBox1 = QComboBox(self)
        self.comboBox1.addItem("1")
        self.comboBox1.addItem("2")
        self.comboBox1.addItem("3")
        self.comboBox1.addItem("4")
        self.comboBox1.setCurrentIndex(0)
        self.comboBox1.activated[str].connect(self.set_interpolation)
        self.comboBox1.resize(60,20)
        self.comboBox1.move(760,10)

        # Set refresh rate in Hz
        self.labelFps = QLabel(self)
        self.labelFps.setText("FPS ")
        self.labelFps.setAlignment(Qt.AlignRight)
        self.labelFps.resize(100,20)
        self.labelFps.move(660,42)

        self.comboBox2 = QComboBox(self)
        self.comboBox2.addItem("0.5Hz")
        self.comboBox2.addItem("1Hz")
        self.comboBox2.addItem("2Hz")
        self.comboBox2.addItem("4Hz")
        self.comboBox2.addItem("8Hz")
        self.comboBox2.addItem("16Hz")
        self.comboBox2.addItem("32Hz")
        self.comboBox2.addItem("64Hz")
        self.comboBox2.setCurrentIndex(2)
        self.comboBox2.activated[str].connect(self.set_fps)
        self.comboBox2.resize(60,20)
        self.comboBox2.move(760,40)

        # Set emissivity factor
        self.labelEmissivity = QLabel(self)
        self.labelEmissivity.setText("Emissivity ")
        self.labelEmissivity.setAlignment(Qt.AlignRight)
        self.labelEmissivity.resize(100,20)
        self.labelEmissivity.move(660,72)

        self.lineEdit1 = QLineEdit(self)
        self.lineEdit1.setValidator(QDoubleValidator(0.000,1.000,3))
        self.lineEdit1.setText("1.000")
        self.lineEdit1.resize(60,20)
        self.lineEdit1.move(760,70)
        self.lineEdit1.textChanged.connect(self.set_emissivity)

        # Enable/disable de-interlace filter
        self.checkBox1 = QCheckBox("Enable de-interlace filter", self)
        self.checkBox1.move(680,100)
        self.checkBox1.stateChanged.connect(self.deinterlace_filter)

        # Enable/disable IIR filter and change settings of filter
        self.checkBox2 = QCheckBox("Enable IIR filter", self)
        self.checkBox2.move(680,130)
        self.checkBox2.stateChanged.connect(self.iir_filter)

        self.labelDepth = QLabel(self)
        self.labelDepth.setText("Depth ")
        self.labelDepth.setAlignment(Qt.AlignRight)
        self.labelDepth.resize(100,20)
        self.labelDepth.move(660,152)

        self.lineEdit2 = QLineEdit(self)
        self.lineEdit2.setValidator(QIntValidator(0,12))
        self.lineEdit2.setText("8")
        self.lineEdit2.resize(60,20)
        self.lineEdit2.move(760,150)
        self.lineEdit2.textChanged.connect(self.set_depth)

        self.labelThreshold = QLabel(self)
        self.labelThreshold.setText("Threshold ")
        self.labelThreshold.setAlignment(Qt.AlignRight)
        self.labelThreshold.resize(100,20)
        self.labelThreshold.move(660,182)

        self.lineEdit3 = QLineEdit(self)
        self.lineEdit3.setValidator(QDoubleValidator(0.0,10.0,1))
        self.lineEdit3.setText("2.5")
        self.lineEdit3.resize(60,20)
        self.lineEdit3.move(760,180)
        self.lineEdit3.textChanged.connect(self.set_threshold)

        # Enable/disable autorange and change settings of autorange
        self.checkBox3 = QCheckBox("Enable autorange", self)
        self.checkBox3.toggle()
        self.checkBox3.move(680,210)
        self.checkBox3.stateChanged.connect(self.autorange)

        self.labelMinT = QLabel(self)
        self.labelMinT.setText("From ")
        self.labelMinT.setAlignment(Qt.AlignRight)
        self.labelMinT.resize(100,20)
        self.labelMinT.move(660,232)

        self.lineEdit4 = QLineEdit(self)
        self.lineEdit4.setValidator(QDoubleValidator(-40.00,300.00,2))
        self.lineEdit4.setText("20.00")
        self.lineEdit4.resize(60,20)
        self.lineEdit4.move(760,230)
        self.lineEdit4.textChanged.connect(self.set_minT)
        self.lineEdit4.setReadOnly(True)

        self.labelMaxT = QLabel(self)
        self.labelMaxT.setText("To ")
        self.labelMaxT.setAlignment(Qt.AlignRight)
        self.labelMaxT.resize(100,20)
        self.labelMaxT.move(660,262)

        self.lineEdit5 = QLineEdit(self)
        self.lineEdit5.setValidator(QDoubleValidator(-40.00,300.00,2))
        self.lineEdit5.setText("35.00")
        self.lineEdit5.resize(60,20)
        self.lineEdit5.move(760,260)
        self.lineEdit5.textChanged.connect(self.set_maxT)
        self.lineEdit5.setReadOnly(True)

        ## Set up thread for updating the ir image
        self.thVisualizer = Thread_Visualizer(self)
        self.thVisualizer.sig.connect(self.updatIrImage)

    def start_visualizer(self):
        """
        Start/stop updating the ir image
        """
        if self.btn1.text() == "Start":
            dev.set_frame_rate(self.fps)

            time.sleep(0.5)

            self.thVisualizer.start()
            self.btn1.setText("Stop")
        else:
            self.thVisualizer.stop()

            self.btn1.setText("Start")

    def deinterlace_filter(self, state):
        """
        Enable/disable de-interlace filter
        """
        global deinterlace_filter_enabled
        if state == Qt.Checked:
            deinterlace_filter_enabled = True
        else:
            deinterlace_filter_enabled = False

    def iir_filter(self, state):
        """
        Enable/disable iir filter
        """
        global iir_filter_enabled
        if state == Qt.Checked:
            iir_filter_enabled = True
            self.lineEdit2.setReadOnly(False)
            self.lineEdit3.setReadOnly(False)
        else:
            iir_filter_enabled = False
            self.lineEdit2.setReadOnly(True)
            self.lineEdit3.setReadOnly(True)

    def autorange(self, state):
        """
        Enable/disable auto ranging and change temperature scale
        """
        if state == Qt.Checked:
            self.autoscale = True
            self.lineEdit4.setReadOnly(True)
            self.lineEdit5.setReadOnly(True)
        else:
            self.autoscale = False
            self.lineEdit4.setReadOnly(False)
            self.lineEdit5.setReadOnly(False)

    def set_fps(self, text):
        """
        Change refresh rate in Hz
        """
        global frame_rate
        self.fps = float(text[:-2])
        frame_rate = self.fps

    def set_depth(self, text):
        """
        Change depth of iir filter
        """
        global depth
        depth = int(text)

    def set_threshold(self, text):
        """
        Change threshold of iir filter
        """
        global threshold
        threshold = float(text)

    def set_minT(self):
        self.minT = float(self.lineEdit4.text())

    def set_maxT(self):
        self.maxT = float(self.lineEdit5.text())

    def set_interpolation(self, text):
        """
        Change interpolation factor
        """
        global interpolation_factor
        interpolation_factor = int(text)

    def set_emissivity(self, text):
        """
        Change emissivity coefficient
        """
        emissivity = float(self.lineEdit1.text())
        if (emissivity > 0 and emissivity <= 1):
            dev.set_m_fEmissivity(emissivity)

    def mirror_horizontal(self):
        if self.inv_X:
            self.inv_X = False
            self.vb1.invertX(self.inv_X)
        else:
            self.inv_X = True
            self.vb1.invertX(self.inv_X)

    def mirror_vertical(self):
        if self.inv_Y:
            self.inv_Y = False
            self.vb1.invertY(self.inv_Y)
        else:
            self.inv_Y = True
            self.vb1.invertY(self.inv_Y)


def main():
    global dev
    global interpolation_factor
    global depth
    global threshold
    global deinterlace_filter_enabled
    global iir_filter_enabled


    port = 'auto'
    if len(sys.argv) >= 2:
        port = sys.argv[1]

    dev = Mlx9064x(port, frame_rate=8.0)
    dev.init()

    interpolation_factor = 1
    depth = 8
    threshold = 2.5
    deinterlace_filter_enabled = False
    iir_filter_enabled = False

    app = QApplication(sys.argv)
    ex = App()
    ex.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
