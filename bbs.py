import os.path
from time import time, sleep

from jetforce import GeminiServer, JetforceApplication, Response, Status

app = JetforceApplication()

def render(filename, quick=False):
    with open(filename, "rb") as file:
        col = 0
        ansiseq = ""
        nextbyte_ts = time()
        byte_interval = 10 / 19200
        while True:
            nextbyte_ts += byte_interval
            b = file.read(1)
            if len(b) == 0:
                # EOF
                return ''

            if b[0] == 27:
                # skip ANSI sequences from line length calculation
                ansiseq = b
                while not b.isalpha():
                    b = file.read(1)
                    ansiseq += b
                if b == b'C': # move right; an optimization technique
                    move = int(ansiseq[2:-1] or 1)
                    col += move
                    nextbyte_ts += (move - 1) * byte_interval
                yield ansiseq
                continue

            col += 1

            if not quick:
                sleeptime = nextbyte_ts - time()
                if sleeptime > 0:
                    sleep(sleeptime)

            yield b.decode("cp437").encode("utf-8")

            if b in (b'\r', b'\n'):
                col = 0
            if col >= 80:
                # Wrap to 80 cols
                yield b'\r\n'
                col = 0

ANSI_FILE = "ans/us-birth-of-mawu-liza.ans"

@app.route("")
def root(req):
    return Response(Status.SUCCESS, "text/x-ansi", render(ANSI_FILE))

@app.route("/ansi/(?P<filename>[^/]*)")
def ansi(req, filename):
    path = os.path.join("ans", filename)
    if os.path.isfile(path):
        return Response(Status.SUCCESS, "text/x-ansi", render(path))
    return Response(Status.NOT_FOUND, "Not found")

@app.route("/quick/(?P<filename>[^/]*")
def quick(req, filename):
    path = os.path.join("ans", filename)
    if os.path.isfile(path):
        return Response(Status.SUCCESS, "text/x-ansi", b"".join(render(path, quick=True)))
    return Response(Status.NOT_FOUND, "Not found")

if __name__ == "__main__":
    server = GeminiServer(app)
    server.run()
