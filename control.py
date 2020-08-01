import time
import zmq
import traceback
import motorLib
import streaming
import os
from config import config

class Server:
    def __init__(self):
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.REP)
        self.sock.bind("tcp://*:%d"%config.command_port)
        print("Starting Command Server at %d"%config.command_port)
        motorLib.setServo(0)
        self._busy = False
        self._id = 1
        self._auth_id = 0
        self.halt = False
        self.run()
    def run(self):
        while not self.halt:
            msg = self.sock.recv_string()
            # Do Error Handling + Timeout sending
            msg = msg.split()
            if msg[0] == 'HI':
                print("New Visitor", end=" ")
                if self._busy:
                    self.sock.send_string('NO')
                    print("Denied")
                else:
                    self._busy = True
                    print(self._id)
                    self.p = streaming.Publisher()
                    motorLib.motor.engine_on()
                    self._auth_id = str(self._id)
                    self.sock.send_string('OK %d'%self._id)
            elif msg[0] == 'BYE':
                if msg[1] == self._auth_id:
                    print("Visitor %s leaving"%self._auth_id)
                    self.p.quit()
                    motorLib.motor.setFreq(0)
                    motorLib.motor.engine_off()
                    self._auth_id = 0
                    self._id += 1
                    self._busy = False
                    self.sock.send_string('OK')
                else:
                    self.sock.send_string('NO')
            elif msg[0] == 'DO':
                if msg[1] == self._auth_id:
                    # print(msg)
                    try:
                        steer = int(msg[2])
                        velocity = float(msg[3])
                        motorLib.setServo(steer)
                        if velocity > 300: velocity = 300
                        if velocity < -300: velocity = -300
                        if velocity >= 0:
                            motorLib.motor.setDir(True)
                            motorLib.motor.setFreq(round(velocity/0.333))
                        else:
                            motorLib.motor.setDir(False)
                            motorLib.motor.setFreq(round(-velocity/0.333))
                    except:
                        self.sock.send_string('FAIL')
                        print("Invalid Do Command")
                    else:
                        self.sock.send_string('OK')
                else:
                    self.sock.send_string('NO')
            elif msg[0] == 'EXIT':
                if msg[1] != self._auth_id:
                    self.sock.send_string('NO')
                    continue
                try:
                    print("SYSTEM HALT")
                    self.sock.send_string('BYE')
                    self.halt = True
                    motorLib.quit()
                    streaming.quit()
                finally:
                    os.system("sudo halt")
                    break
            else:
                sock.send_string('INVALID')
                print("Invalid Command")

try:
    s = Server()
except (KeyboardInterrupt, SystemExit):
    print("Exitting..")
    pass
except Exception as e:
    print("Traceback:", e)
    traceback.print_exc()
finally:
    motorLib.quit()
    streaming.quit()
