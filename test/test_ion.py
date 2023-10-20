import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import time


matplotlib.use('TkAgg')
def mypause(interval):
    backend = plt.rcParams['backend']
    if backend in matplotlib.rcsetup.interactive_bk:
        figManager = matplotlib._pylab_helpers.Gcf.get_active()
        if figManager is not None:
            canvas = figManager.canvas
            if canvas.figure.stale:
                canvas.draw()
                canvas.start_event_loop(interval)
                return

plt.ion()
plt.show()
plt.grid(visible=True)
plt.ylim([-1, 1])
line1, = plt.plot([],label="Lowpass Filter Output")
line2, = plt.plot([],label="Highpass Filter Output")
# Configure labels for axes
ax = plt.gca()
ax.legend(handles=[line1, line2])
plt.xlabel("Time [Second]")
plt.ylabel("Amplitude [Volt]")

x0 = 0.5
y0 = -0.9

for i in range(10):
    x0 = (x0+0.1+1)%2-1
    y0 = (y0+0.2+1)%2-1
    t = np.arange(10)
    x0data = np.zeros(10)+x0
    y0data = np.zeros(10)+y0
    plt.xlim([t[0], t[-1]])
    # Update the plot
    line1.set_ydata(x0data)
    line2.set_ydata(y0data)
    line1.set_xdata(t)
    line2.set_xdata(t)
    mypause(2)
    # time.sleep(2)
plt.close()

