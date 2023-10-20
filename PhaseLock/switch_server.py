#%%
# Warning: this server only work when firmware properly configed in gui

from moku.instruments import MultiInstrument
from moku.instruments import WaveformGenerator, LockInAmp, PIDController
import time

# init mokupro as mim, platform_id indicate number of slots to use
print("initializing...")
print("fecthing mim")
mim = MultiInstrument('192.168.50.8', platform_id=4, persist_state=True, ignore_busy=True, force_connect=True)

instrus = mim.get_instruments()
# aomDriver=WaveformGenerator(slot=1, persist_state=True,multi_instrument=mim)
print("fetching oppositePhase")
oppositePhase = LockInAmp(slot=2, persist_state=True, multi_instrument=mim)
# tweezerPhase = LockInAmp(slot=4, persist_state=True, multi_instrument=mim)
# pid = PIDController(slot=3, persist_state=True, multi_instrument=mim)

print("finish initialization!")

# %%
# oppositePhase.set_outputs(main="Theta", aux="Demod")
time.sleep(180)
start_t = time.time()
feedback = []
templist = [10, 20, 30, 40, 50]
tempphase = 0
for i in range(5):
    tempphase += templist[i]
    feedback.append(oppositePhase.set_demodulation(mode='Internal',frequency=200000, phase=tempphase,strict=False))
    time.sleep(2)
res = oppositePhase.get_demodulation()
end_t = time.time()
print(end_t-start_t, res)
for feedbacki in feedback:
    print(feedbacki)
#%%
# disconnect
mim.relinquish_ownership()


# %%
