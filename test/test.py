#%%
from moku.instruments import MultiInstrument
from moku.instruments import WaveformGenerator, LockInAmp, PIDController

# init mokupro as mim, platform_id indicate number of slots to use
mim = MultiInstrument('192.168.50.8', platform_id=4, persist_state=True)
print("success")

#%%
# config slots
try:
    aomDriver = mim.set_instrument(1, WaveformGenerator)
    oppositePhase = mim.set_instrument(2, LockInAmp)
    tweezerPhase = mim.set_instrument(4, LockInAmp)
    pid = mim.set_instrument(3, PIDController)
except Exception as e:
    print(e)

#%%
# config connections
try:
    temp = mim.set_connections(connections=[
        # feedback to AOM freq tuning
        dict(source="Slot3OutB", destination="Slot1InB"),
        # AOM Drive
        dict(source="Slot1OutA", destination="Output3"),
        dict(source="Slot1OutB", destination="Output4"),
        # opposite balance input
        dict(source="Input2", destination="Slot2InA"),
        # pid phase input
        dict(source="Slot2OutA", destination="Slot3InA"),
        dict(source="Slot4OutA", destination="Slot3InB"),
        # pid output piezo
        dict(source="Slot3OutA", destination="Output2"),
        # tweezer balance input
        dict(source="Input1", destination="Slot4InA")
    ])
    print(temp)
except Exception as e:
    print(e)

#%%
# config I/O
mim.set_frontend(1, '1MOhm', 'AC', '0dB')
mim.set_frontend(2, '1MOhm', 'AC', '0dB')
mim.set_output(2, '14dB')
mim.set_output(3, '0dB')
mim.set_output(4, '0dB')
# sync TODO: determin where to put sync()
mim.sync()
#%%
# test clock
print(mim.get_external_clock())

#%%
# config aomDriver
aomDriver.generate_waveform(
    channel=1, type='Sine', amplitude=1, frequency=110.2e6
)
aomDriver.disable_modulation(1)
aomDriver.generate_waveform(
    channel=2, type='Sine', amplitude=0.5, frequency=110e6
)
aomDriver.set_modulation(
    channel=2, type='Frequency', source='Input2', depth=50,
)

#%%


#%%
# disconnect
mim.relinquish_ownership()
# %%
