# Intro

This is a python visualizer for the MLX90640 and MLX90641. It is using the original mlx9064x-driver-py.

Currently this driver supports 3 type of interfaces:
- EVB90640-41 ==> https://www.melexis.com/en/product/EVB90640-41/Evaluation-Board-MLX90640
- Raspberry Pi with I2C on any GPIO pin.
- Raspberry Pi on built-in hardware I2C bus.


## Dependencies

Driver:
- Python3
- pySerial

EVB user interface:
- Python3
- NumPy
- Matplotlib
- ctypes
- PyQt5
- PyQtGraph
- sciPy

## Getting started

### Clone and update submodules

1. clone the project using: 
```bash
git clone https://github.com/melexis-fir/mlx9064x-visualizer-py.git
```
2. navigate to ./mlx9064x-visualizer-py/mlx9064x-driver-py and update submodule using:
```bash
git submodule init
git submodule update
```

### Running mlx90640_demo.py

1. get the sources and chdir to the project-examples directory
2. run following command:
```bash
python3 mlx90640_demo.py
```
