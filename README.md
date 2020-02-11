# Intro

This is a python visualizer for the MLX90640 and MLX90641. It is using the original mlx9064x-driver-py.

Currently this driver supports 3 type of interfaces:
- EVB90640-41 ==> https://www.melexis.com/en/product/EVB90640-41/Evaluation-Board-MLX90640
- Raspberry Pi with I2C on any GPIO pin.
- Raspberry Pi on built-in hardware I2C bus.


## Dependencies

- Python3
- mlx9064x-driver
- NumPy
- Matplotlib
- ctypes
- PyQt5
- PyQtGraph
- sciPy

## Getting started

```bash
pip install mlx9064x-visualizer
```

### Running mlx90640_demo.py

```bash
mlx9064x-visualizer auto
```
