# Copyright 2020 Sanggyu Lee. All rights reserved.
# sanggyu.developer@gmail.com

import pigpio
from time import sleep
import threading
import logging
from bisect import bisect_left
# import atexit
from config import config

logger = logging.getLogger('motor')
logger.setLevel(logging.DEBUG)  # DEBUG INFO WARNING ERROR CRITICAL
stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)
#file_handler = logging.FileHandler('motor.log')
#logger.addHandler(file_handler)

pi = pigpio.pi()
SERVO = config.SERVO
DIR = config.DIR
STEP = config.STEP
MS = (config.MS1, config.MS2, config.MS3)
ENABLE = config.ENABLE
SLEEP = config.SLEEP
MS_SET = {
'1': (0, 0, 0),
'1/2': (1, 0, 0),
'1/4': (0, 1, 0),
'1/8': (1, 1, 0),
'1/16': (1, 1, 1)
}

ACCELERATION = 3000 # Hz / s
DELAY = 1./100
FREQ_INC = round(ACCELERATION * DELAY)

FREQ = (125, 300, 400, 800)
FACTOR = (16, 8, 4, 2, 1)
MS_SELECT = ('1/16', '1/8', '1/4', '1/2', '1')
for p in (SERVO, DIR, STEP, ENABLE, SLEEP)+MS:
    pi.set_mode(p, pigpio.OUTPUT)

def setServo(steer = 0):
    if steer > 100: steer = 100
    elif steer < -100: steer = -100
    pi.set_servo_pulsewidth(SERVO, 1500+int(5*steer))
    # pi.hardware_PWM(SERVO, 50, 75000+int(angle*25000/90))

class StepMotor(threading.Thread):
    FREQ = FREQ
    def __init__(self):
        threading.Thread.__init__(self)
        self.halt = threading.Event()
        self.go = False # if enable pin is low
        self.dir = True # dir pin status
        self.freq = 0 #for open loop control
        self.desired_freq = 0
        self.on = False # if sleep pin is high
        self.Micro = '1/8'
        self.setMicro('1/8')
        pi.write(SLEEP, 0)
        pi.write(DIR, 1)
        pi.write(ENABLE, 1)
    def run(self):
        while not self.halt.is_set():
            if self.desired_freq > self.freq:
                if self.freq == 0: self.full_start()
                self.freq = min(self.freq + FREQ_INC, self.desired_freq)
                self.hardware_drive(self.freq)
                logger.debug('Freq: %d< Desired: %d'%(self.freq, self.desired_freq))
            elif self.desired_freq < self.freq:
                self.freq = max(self.freq - FREQ_INC, self.desired_freq)
                if self.freq == 0:
                    self.full_stop()
                    continue
                self.hardware_drive(self.freq)
                logger.debug('Freq: %d> Desired: %d'%(self.freq, self.desired_freq))
            sleep(DELAY)
    def engine_on(self):
        pi.write(SLEEP, 1)
        self.on = True
        sleep(0.001)
        logger.info('engine now ready')
    def engine_off(self):
        pi.write(SLEEP, 0)
        self.on = False
        sleep(0.001)
        logger.info('engine now off')
    def full_stop(self):
        self.hardware_drive(0)
        pi.write(ENABLE, 1)
        self.go = False
        logger.info('now disabled')
    def full_start(self):
        pi.write(ENABLE, 0)
        self.setMicro('1/8')
        self.go = True
        logger.info('now enabled')
    def setDir(self, dir):
        if dir != self.dir:
            pi.write(DIR, 1 if dir else 0)
            self.dir = dir
            logger.debug('dir set to %d'%dir)
    def setMicro(self, Micro):
        """set '1', '1/2', '1/4', '1/8', '1/16'"""
        if self.Micro == Micro: return
        for i in range(3):
            pi.write(MS[i], MS_SET[Micro][i])
        self.Micro = Micro
        logger.info('micro: '+self.Micro)
    def setFreq(self, freq):
        self.desired_freq = min(freq, 1000)
    def hardware_drive(self, freq):
        freq = min(freq, 1000)
        i = bisect_left(self.FREQ, freq)
        self.setMicro(MS_SELECT[i])
        pi.hardware_PWM(STEP, freq*FACTOR[i], 500000)
    def stop(self):
        self.desired_freq = 0
    def _disable_after_time(self):
        if self.desired_freq == 0:
            pi.write(ENABLE, 0)
            logger.info('now disabled')
    def emergency_stop(self):
        stopping_time = float(self.freq) / ACCELERATION
        self.freq = 0
        self.desired_freq = 0
        pi.hardware_PWM(STEP, 0, 0)
        self.go = False
        pi.write(ENABLE, 1)
        logger.info('emergency stopped')
        threading.Timer(stopping_time, self._disable_after_time).start()



motor = StepMotor()
motor.start()

if __name__ == '__main__':
    setServo(0)
    motor.engine_on()
    motor.setFreq(60)
    sleep(1)
    motor.setFreq(30)
    sleep(1)
    motor.engine_off()
    motor.halt.set()
    motor.join()


stop = motor.stop
def quit():
    motor.emergency_stop()
    sleep(0.1)
    motor.full_stop()
    motor.engine_off()
    motor.halt.set()
    motor.join()
    pi.stop()

# atexit.register(quit)
