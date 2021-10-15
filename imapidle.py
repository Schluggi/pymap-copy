from threading import Thread
from time import sleep, time


class IMAPIdle(Thread):
    def __init__(self, client, interval=1680):
        self.client = client
        self.interval = interval
        self._idle = False
        self._exit = False
        super(IMAPIdle, self).__init__(daemon=True)

    def run(self):
        while self._exit is False:
            if self._idle and (time()-self._idle) > self.interval:
                self.restart_idle()
            sleep(0.1)

    def exit(self):
        self._exit = True

    def start_idle(self):
        """
        start imap idle to hold the connection alive
        """
        if self._idle is False:
            #: must select a folder before invoking idle. we simply select the first folder to idle on
            _, _, some_folder = self.client.list_folders()[0]
            self.client.select_folder(some_folder, readonly=True)
            self.client.idle()
            self._idle = time()

    def stop_idle(self):
        """
        stop idle mode to allow normal commands
        """
        if self._idle:
            self.client.idle_done()
            self._idle = False

    def restart_idle(self):
        self.stop_idle()
        self.start_idle()
