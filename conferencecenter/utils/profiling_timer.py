import time


class ProfilingTimer:
    def __init__(self):
        super().__init__()
        self.start_time = self.last_time = time.time()

    def time(self, name):
        now = time.time()
        delta = now - self.last_time
        self.last_time = now
        print(('PROFILING_TIMER: {} took {} seconds'.format(name, delta)))

    def total(self):
        now = time.time()
        print(('PROFILING_TIMER TOTAL: {} seconds'.format(now - self.start_time)))