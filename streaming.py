# Copyright 2020 Sanggyu Lee. All rights reserved.
# sanggyu.developer@gmail.com

import time
import zmq
from imutils.video import VideoStream
import imagezmq
import cv2
import socket
import traceback
from config import config
import pigpio
import adafruit_vl53l0x
import busio
import board
import threading

#s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#try:
#    s.connect(('10.255.255.255', 1))
#    ip = s.getsockname()[0]
#except:
#    ip = '192.168.0.10'
#finally:
#    s.close()
#print("Server IP:", ip)

frontX = config.XSHUT_FRONT
rearX = config.XSHUT_REAR
pi = pigpio.pi()
pi.set_mode(frontX, pigpio.OUTPUT)
pi.set_mode(rearX, pigpio.OUTPUT)
i2c = busio.I2C(board.SCL, board.SDA)
class constLiDAR:
    def __init__(self):
        pass
    @property
    def range(self):
        raise ValueError("LiDAR not available")


class LiDAR:
    def __init__(self):

        self._thread = threading.Thread(target=self._run, args=())
        self._thread.daemon = True
        self.front = 0
        self.rear = 0
        self.halt = False
        self._thread.start()
    def _run(self):
        pi.write(frontX, 0)
        pi.write(rearX, 0)
        time.sleep(0.1)
        pi.write(frontX, 1)
        time.sleep(0.1)
        # https://github.com/adafruit/Adafruit_CircuitPython_VL53L0X/blob/master/examples/vl53l0x_simpletest.py
        try:
            self.frontL = adafruit_vl53l0x.VL53L0X(i2c)
            self.frontL.set_address(0x2c)
        except (OSError, ValueError):
            print("Front Lidar not available")
            self.frontL = constLiDAR()
        pi.write(rearX, 1)
        time.sleep(0.1)
        try:
            self.rearL = adafruit_vl53l0x.VL53L0X(i2c)
            self.rearL.set_address(0x2d)
        except (OSError, ValueError):
            print("Rear Lidar not available")
            self.rearL = constLiDAR()
        while not self.halt:
            try:
                self.front = self.frontL.range
            except (OSError, ValueError):
                print("Front LiDAR Error")
                self.front = 0
                try:
                    pi.write(frontX, 0)
                    pi.write(rearX, 0)
                    time.sleep(0.1)
                    pi.write(frontX, 1)
                    time.sleep(0.1)
                    self.frontL = adafruit_vl53l0x.VL53L0X(i2c)
                    self.frontL.set_address(0x2c)
                    pi.write(rearX, 1)
                    time.sleep(0.1)
                    self.rearL = adafruit_vl53l0x.VL53L0X(i2c)
                    self.rearL.set_address(0x2d)
                except:
                    pass
            try:
                self.rear = self.rearL.range
            except (OSError, ValueError):
                self.rear = 0
                print("Rear LiDAR Error")
                try:
                    pi.write(rearX, 0)
                    pi.write(frontX, 0)
                    time.sleep(0.1)
                    pi.write(frontX, 1)
                    time.sleep(0.1)
                    self.frontL = adafruit_vl53l0x.VL53L0X(i2c)
                    self.frontL.set_address(0x2c)
                    pi.write(rearX, 1)
                    time.sleep(0.1)
                    self.rearL = adafruit_vl53l0x.VL53L0X(i2c)
                    self.rearL.set_address(0x2d)
                except:
                    pass
        pi.write(frontX, 0)
        pi.write(rearX, 0)
    def quit(self):
        self.halt = True
        self._thread.join(1)


class Publisher:
    lkg = None
    front = None
    back = None
    def __init__(self):
        try:
            if Publisher.front is None:
                Publisher.front = VideoStream(usePiCamera=True, resolution=(640, 480), framerate=30)
                camera = Publisher.front.stream.camera
                # https://picamera.readthedocs.io/en/release-1.12/recipes1.html
                if config.fix_camera_setting:
                    camera.iso = 100
                    #time.sleep(2)
                    #print('exposure', repr(camera.exposure_speed))
                    camera.shutter_speed = 26083
                    camera.exposure_mode = 'off'
                    #g = camera.awb_gains
                    #print('awb', repr(g))
                    camera.awb_mode = 'off'
                    camera.awb_gains = ((341./256), (197./128))
                Publisher.front = Publisher.front.start()
            if Publisher.back is None:
                Publisher.back = VideoStream(usePiCamera=False, src=0, resolution=(640, 480), framerate=30).start()
        except:
            print("Camera not Available")
            raise RuntimeError()
        self.quality = config.quality
        self.halt = False
        self._thread = threading.Thread(target=self._run, args=())
        self._thread.daemon = True
        self._thread.start()
        Publisher.lkg = self
    def _run(self):
        print("Preparing Camera and LiDAR")
        try:
            self.lidar = LiDAR()
            print("Starting Image/LiDAR Publisher at %d"%config.camera_port)
            self.sender = imagezmq.ImageSender(connect_to="tcp://*:%d" % (config.camera_port), REQ_REP=False)
            time.sleep(2)
            while not self.halt:
                # head = time.time()
                front_frame = self.front.read()
                back_frame = self.back.read()
                #if (front_frame.empty() or back_frame.empty()):
                #    print("Image Empty!")
                #    continue
                start = time.time()
                #print("loading", start - head)
                _, front_jpg = cv2.imencode(".jpg", front_frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
                self.sender.send_jpg("%f %d %d,front"%(start, self.lidar.front, self.lidar.rear), front_jpg)
                _, back_jpg = cv2.imencode(".jpg", back_frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
                self.sender.send_jpg("%f %d %d,rear"%(start, self.lidar.front, self.lidar.rear), back_jpg)
        except Exception as e:
            print("Error In Image Publisher", e)
            traceback.print_exc()
        finally:
            try:
                self.lidar.quit()
                self.sender.close()
            except:
                pass

    def quit(self):
        self.halt = True
        self._thread.join(1)

def quit():
    if Publisher.lkg is not None:
        Publisher.lkg.quit()
    if Publisher.front is not None:
        Publisher.front.stop()
    if Publisher.back is not None:
        Publisher.back.stop()
    pi.stop()

if __name__ == '__main__':
    try:
        p = Publisher()
        time.sleep(10)
        p.quit()
    except (KeyboardInterrupt, SystemExit):
        print("Exitting..")
    except Exception as e:
        print("Traceback:", e)
        traceback.print_exc()
    finally:
        pi.stop()
