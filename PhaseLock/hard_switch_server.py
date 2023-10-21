
"""
Warning: this server only work when firmware properly configed in gui
"""
from moku.instruments import MultiInstrument
from moku.instruments import WaveformGenerator, LockInAmp, PIDController
from moku.exceptions import StreamException, MokuException
from sipyco.pc_rpc import simple_server_loop

import copy
import logging
from math import ceil
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import os
import threading
import time

# some basic value
phaseTolerance = 0.1 #degree
lockinFreq = 200000 #Hz
maxStep = 30 #degree
monitorSpan = 1 #s
phaseBrokenPanelTime = 20 # s(if phase broken, data will be shown on panel for this period of time)
panelUpdateInterval = 3 #s

# Setup logging and data saving
_currentPath = os.path.dirname(os.path.abspath(__file__))
_logger_path = _currentPath+'/logs'
_data_path = _currentPath+'/data'
if not os.path.exists(_logger_path):
    os.makedirs(_logger_path)
if not os.path.exists(_data_path):
    os.makedirs(_data_path)
logging.basicConfig(
        level=logging.INFO, filename=_logger_path+"/serverlog",
        format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
)
## set up logging to _console
_console = logging.StreamHandler()
_console.setLevel(logging.WARNING)
## set a format which is simpler for console use
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
_console.setFormatter(formatter)
## add the handler to the root logger
logging.getLogger('').addHandler(_console)
_moku_logger = logging.getLogger(__name__)

# avoid plt panel keep jumping out
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


class ConfigException(MokuException):
    """
    Moku not configed properly before running this server
    """
    pass

class HardSwitchServer:
    def __init__(
            self, phaseThreshold, outThreshold,
            showMonitor=True
        ) -> None:
        self._logger = _moku_logger 
        try:
            # init mokupro as mim, platform_id indicate number of slots to use
            print("initializing...")
            self._logger.info("try to init")
            print("fetching mim...")
            self._mim = MultiInstrument('192.168.50.8', platform_id=4, persist_state=True, ignore_busy=True, force_connect=True)

            # check
            if self._mim.get_instruments() != ['WaveformGenerator', 'LockInAmplifier', 'PIDController', 'LockInAmplifier']:
                raise ConfigException("Moku not configed properly before running this server")
            
            # aomDriver=WaveformGenerator(slot=1, persist_state=True,multi_instrument=self._mim)
            print("fetching oppositePhase...")
            self._oppositePhase = LockInAmp(slot=2, persist_state=True, multi_instrument=self._mim)
            # tweezerPhase = LockInAmp(slot=4, persist_state=True, multi_instrument=self._mim)
            print("fetching pid...")
            self._pid = PIDController(slot=3, persist_state=True, multi_instrument=self._mim)
        except Exception as err:
            self._logger.warning("failed to init", err)
            self._mim.relinquish_ownership()
            assert False
        print("configuring...")
        self._phaseThreshold = phaseThreshold
        self._outThreshold = outThreshold
        self._curPhase = self._oppositePhase.get_demodulation()['phase']
        self._pid.set_monitor(1, 'Control1')
        self._pid.set_monitor(2, 'Output1')
        self._pid.set_timebase(-monitorSpan/2, monitorSpan/2)
        self._pid.set_trigger(type='Edge', source='ProbeA', level=0)
        self._pid.set_acquisition_mode(mode='Precision')
        self._mim.sync()
        print("starting monitor...")
        # start (a) thread to monitor phase lock
        ## prepare
        self._showMonitor = showMonitor
        self._monitorStop: threading.Event = threading.Event()
        self._monitorStop.clear()
        self._monitorThread = threading.Thread(target=self._monitor, daemon=True)
        if self._showMonitor:
            self._panelData = None
            self._dataUpdated = False
            self._panelThread = threading.Thread(target=self._panel, daemon=True)
            # setup monitor panel
            plt.ion()
            plt.show()
            plt.grid(visible=True)
            plt.ylim([-1, 1])
            plt.xlim([-monitorSpan/2, monitorSpan/2])
            self._line1, = plt.plot([],label="phase")
            self._line2, = plt.plot([],label="piezo output")
            # Configure labels for axes
            self._ax = plt.gca()
            self._ax.legend(handles=[self._line1, self._line2])
            plt.xlabel("Time [Second]")
            plt.ylabel("Amplitude [Volt]")
        ## start
            self._panelThread.start()
        self._monitorThread.start()

        print("finish initialization!")
        self._logger.info("initialization success")

    def __enter__(self):
        return self
    
    @staticmethod
    def _convert_780_to_1064(phase):
        return phase*780/1064
    
    def update_phase_780(self, former, latter) -> bool:
        # convert to 1064
        return self.update_phase_1064(
            self._convert_780_to_1064(former),
            self._convert_780_to_1064(latter)
        )

    def update_phase_1064(self, former, latter) -> bool:
        # check former
        if abs(former-self._curPhase) > phaseTolerance:
            self._logger.warning("former phase doesn't conform to current phase of 1064")
            self._logger.warning("former: {former}, current Phase: {self._curPhase}")
        # call 1064 step
        return self.step_phase_1064(latter-self._curPhase)

    def set_phase_780(self, phase) -> bool:
        return self.set_phase_1064(
            self._convert_780_to_1064(phase)
        )
    
    def set_phase_1064(self, phase) -> bool:
        return self.step_phase_1064(phase - self._curPhase)

    def step_phase_780(self, step) -> bool:
        # convert to 1064
        return self.step_phase_1064(self._convert_780_to_1064(step))

    def step_phase_1064(self, step) -> bool:
        success = True
        # divide into multi stages if needed
        stages = 1 if abs(step) <= maxStep else ceil(abs(step)/maxStep)
        stepi = step/stages
        # apply
        for i in range(stages):
            self._curPhase += stepi
            tempPhase = self._oppositePhase.set_demodulation(
                mode='Internal',frequency=lockinFreq, 
                phase=self._curPhase,strict=False
            )['phase']
            # check if success
            if abs(self._curPhase - tempPhase) > phaseTolerance:
                self._logger.error("phase not set successfully, objective phase:{self._curPhase}, phase after setting: {tempPhase}")
                success = False
            # update _curphase
            self._curPhase = tempPhase
        return success

    def get_phase_1064(self):
        return self._curPhase

    
    def _monitor(self):
        # setup Oscilloscope(already setted in init)
        lastTime = time.time()
        # start loop:
        while not self._monitorStop.is_set():
            # fetch data
            tempdata = self._pid.get_data()
            # check validation of tempdata(TODO: use try if this still not work)
            if tempdata['ch1'] == None:
                self._logger.warning("failed to get data from moku")
                print(tempdata)
                continue
            # check phaselock(2 threshold)
            # if outof threshold:
                # log warning
                # record data
            isBroken = False
            if np.max(np.absolute(tempdata['ch1'])) > self._phaseThreshold:
                self._logger.warning("PHASE out of threshold, phase lock maybe broken!")
                isBroken = True
            if np.max(np.absolute(tempdata['ch2'])) > self._outThreshold:
                self._logger.warning("piezo OUTPUT near the boudary!")
                isBroken = True
            if isBroken:
                # require panel update in urgent manner
                if self._showMonitor:
                    self._panelData = copy.deepcopy(tempdata)
                    self._dataUpdated = True
                    lastTime += phaseBrokenPanelTime
                # save to file
                np.save(_data_path+"/MonotorWarning_"+time.strftime("%Y%m%d-%H%M%S")+".npy", tempdata)
            # update monitor pannelData if showMonitor(and curTime-lastTime enough), update label
            # this has low priority, so don't update if flag not cleared
            if self._showMonitor and (not self._dataUpdated):
                curTime = time.time()
                if curTime - lastTime > panelUpdateInterval:
                    self._panelData = copy.deepcopy(tempdata)
                    self._dataUpdated = True
                    lastTime = curTime
        # handle stop
       

    def _panel(self):
        # start loop:
        while not self._monitorStop.is_set():
            if self._dataUpdated:
                # deep copy and clear flag(can use lock to avoid copy)
                tempdata = copy.deepcopy(self._panelData)
                self._dataUpdated = False
                # update panel
                self._line1.set_ydata(tempdata['ch1'])
                self._line2.set_ydata(tempdata['ch2'])
                self._line1.set_xdata(tempdata['time'])
                self._line2.set_xdata(tempdata['time'])
            # sleep
            mypause(panelUpdateInterval)
        # handle stop
        plt.close()



    def __exit__(self, exc_type, exc_value, traceback):
        print("exist correctly")
        self._logger.info("exist correctly")
        # stop monitoring
        if not self._monitorStop.is_set():
            self._monitorStop.set()
            self._monitorThread.join()
            self._panelThread.join()
        else:
            self._logger.warning("monitor already stopped")
        # release conection with moku
        self._mim.relinquish_ownership()

with HardSwitchServer(
    phaseThreshold=0.3, outThreshold=0.85, showMonitor=True
) as mokuServer:
    mokuServer.set_phase_780(0)
    simple_server_loop(
        {
            "mokuServer": mokuServer
        },
        "192.168.50.84", 41103
    )



