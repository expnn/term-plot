# -*- coding: utf-8 -*-

import numpy as np
import matplotlib
import matplotlib.pyplot as plt


if __name__ == '__main__':
    matplotlib.use('module://term_plot.backend')

    a = np.random.randn(100)
    fig = plt.figure()

    plt.plot(a)
    fig.show()
