import math, operator
import time
import os
import datetime
import dropbox
import threading
import picamera
import ConfigParser
import logging
from pushbullet import PushBullet
from PIL import Image
from PIL import ImageChops

CONFIG = ConfigParser.ConfigParser()
CONFIG.read("defaults.cfg")
PUSH_BULLET_API_KEY = CONFIG.get("ApiKeys", "PushBullet")
DROPBOX_ACCESS_KEY = CONFIG.get("ApiKeys", "Dropbox")
SLEEP_TIMER = 30
logging.basicConfig(format = '%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

class KaunAaya():

    def __init__(self):
        self.p = PushBullet(PUSH_BULLET_API_KEY)
        self.clickPicture = False
        self.prevPhoto = ""
        self.startCameraThread = None

    def uploadPhoto(self, file):
        logging.info("Uploading " + str(file) + " to dropbox..")
        client = dropbox.client.DropboxClient(DROPBOX_ACCESS_KEY)
        logging.info("Account Details: " + str(client.account_info()))

        while(os.path.isfile(file) == False):
            logging.info("File [" + str(file) +"] not present")
            time.sleep(5)          
            
        f = open(file, "rb")
        size = os.fstat(f.fileno()).st_size
        uploader = client.get_chunked_uploader(f, size)
        logging.info("Uploading: " + str(size))
        while uploader.offset < size:
            try:
                upload = uploader.upload_chunked(1024 * 20)
            except rest.ErrorResponse, e:
                logging.info("Exception!")
        uploader.finish("/" + file)    
        logging.info("Finished uploading: " + str(file))
        #response = client.put_file("/" + file, f)
        #print "Finished uploading file: ", response

    def compare(self, prevPhoto, newPhoto):
        if not prevPhoto:
            return False

        image1 = Image.open(prevPhoto)
        image2 = Image.open(newPhoto)
        diff = ImageChops.difference(image1, image2)
        h = diff.histogram()
        sq = (value*(idx**2) for idx, value in enumerate(h))
        sum_of_squares = sum(sq)
        rms = math.sqrt(sum_of_squares/float(image1.size[0] * image1.size[1]))

        logging.info("RMS [" + str(rms) + "]")
        
        if rms < 600:
            return True

        return False

    def stopCamera(self):
        logging.info("Stopping camera..")
        self.clickPicture = False
        logging.info("Camera stopped")

    def startCamera(self):
        if self.clickPicture == True:
            logging.info("Camera already started")
            return

        logging.info("Starting camera..")
        self.clickPicture = True
        while(self.clickPicture):
            logging.info("Clicking picture")
            newPhoto = None
            with picamera.PiCamera() as camera:
                camera.resolution = (320,240)
                camera.rotation = 180
                newPhoto = str(time.time()) + ".jpg";
                camera.capture(newPhoto)

            # Click photo using rpi
            isSimilarPhoto = self.compare(self.prevPhoto, newPhoto)

            if isSimilarPhoto == False:
                self.uploadPhoto(newPhoto)

            if self.prevPhoto != None:
                if(os.path.isfile(self.prevPhoto)):
                    os.remove(self.prevPhoto)

            self.prevPhoto = newPhoto

            logging.info("Sleeping for [" + str(SLEEP_TIMER) + "] secs")
            time.sleep(SLEEP_TIMER)

    def callback(self, data):
        logging.info("Received message with subtype [" + str(data["subtype"]) + "]")

        if data["subtype"] != "push":
            return

        history = self.p.getPushHistory()
        if history is None or history[0] is None:
            return

        latestPush = history[0]
        logging.info("Received event: [" + str(latestPush["title"]) + "]")
        title = latestPush["title"]

        if title == "Entered":
            self.stopCamera()

            if self.startCameraThread is None:
                logging.info("Camera thread not initialized")
                return

            self.startCameraThread.join()
            if self.startCameraThread.isAlive() == True:
                logging.info("Camera thread still running.")
            else:
                logging.info("Camera thread completed.")
        elif title == "Exited":
            if self.startCameraThread != None and self.startCameraThread.isAlive() == True:
                logging.info("Camera thread already running.")
                return
            logging.info("Starting camera thread..")
            self.startCameraThread = threading.Thread(target=self.startCamera)
            self.startCameraThread.start()
            logging.info("Starting camera thread started..")
        else:
            logging.info("Unknown event received [" + str(title) + "]")


    def listen(self):
        logging.info("Starting camera thread..")
        self.startCameraThread = threading.Thread(target=self.startCamera)
        self.startCameraThread.start()
        logging.info("Starting camera thread started..")
        logging.info("Listening for messages from PushBullet...")
        self.p.realtime(self.callback)

def main():
    logging.info("======= Starting Kaun Aaya ============")
    k = KaunAaya()
    k.listen()

if __name__=="__main__":
    main()
