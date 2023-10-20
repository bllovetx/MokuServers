import logging
logging.basicConfig(
        level=logging.INFO, filename="./logs/serverlog",
        format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
)
# set up logging to console
console = logging.StreamHandler()
console.setLevel(logging.WARNING)
# set a format which is simpler for console use
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger('').addHandler(console)
logger = logging.getLogger(__name__)

class TestLogging:
    def __init__(self) -> None:
        self.logger = logger

    def info(self):
        self.logger.info("info-log")

    def warning(self):
        self.logger.warning("warning-log")

temptest = TestLogging()
temptest.info()
temptest.warning()