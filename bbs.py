# Copyright 2020 Hannu Hartikainen
# Licensed under GNU AGPL, v3 or later
#
# NOTE: Put art files in ans/

import os.path
from time import time, sleep

from jetforce import GeminiServer, JetforceApplication, Response, Status

app = JetforceApplication()

def render(filename, quick=False):
    with open(filename, "rb") as file:
        col = 0
        linebuf = b""
        ansiseq = ""
        nextline_ts = time()
        line_interval = (80 * (1 + 8 + 1)) / 19200
        while True:
            b = file.read(1)
            if len(b) == 0:
                # EOF
                return linebuf

            if b[0] == 27:
                # skip ANSI sequences from line length calculation
                ansiseq = b
                while not b.isalpha():
                    b = file.read(1)
                    ansiseq += b
                if b == b'C': # move right; an optimization technique
                    move = int(ansiseq[2:-1] or 1)
                    col += move
                    nextline_ts += (move - 1) * line_interval
                linebuf += ansiseq
                continue

            col += 1

            if not quick:
                sleeptime = nextline_ts - time()
                if sleeptime > 0:
                    sleep(sleeptime)

            linebuf += b.decode("cp437").encode("utf-8")

            if b == b'\r':
                col = 0
            if b == b'\n':
                yield linebuf
                nextline_ts += line_interval
                col = 0
                linebuf = b""
            if col >= 80:
                # Wrap to 80 cols
                yield linebuf + b'\r\n'
                nextline_ts += line_interval
                col = 0
                linebuf = b""

FRONT_CONTENT = """# Welcome to the ANSI art archive

This site mirrors ANSI art from https://16colo.rs. Modem-like download speed is emulated, and some magic is done to render mostly correctly in modern wide unicode terminals. The originals tend to be CP437, 80 columns.

For best experience, please use a streaming-capable client.

## Example: the birth of mawu-liza / alpha king & h7 / blocktronics 2019-07-29

=> /us-birth-of-mawu-liza.ans Streaming
=> /quick/us-birth-of-mawu-liza.ans Instant display

More generally, substitute /ansi/ to /quick/ if you want to show the file without modem download emulation.

## List of all pieces

=> list/

## About this site

Created one night in 2020 by Hannu Hartikainen
=> source/ Source code
"""

@app.route("")
def root(req):
    return Response(Status.SUCCESS, "text/gemini", FRONT_CONTENT)

@app.route("/source")
def source(req):
    with open(__file__) as source_file:
        return Response(Status.SUCCESS, "text/x-python", source_file.read())

@app.route("/list")
def files(req):
    files = os.listdir("ans")
    files.sort()
    links = "\n".join(f"=> /{f}" for f in files)
    response = f"""# {len(files)} works of art

{links}"""
    return Response(Status.SUCCESS, "text/gemini", response)

@app.route("/(?P<filename>[^/]*\.ans)")
def ansi(req, filename):
    path = os.path.join("ans", filename)
    if os.path.isfile(path):
        return Response(Status.SUCCESS, "text/x-ansi", render(path))
    return Response(Status.NOT_FOUND, "Not found")

@app.route("/quick/(?P<filename>[^/]*)")
def quick(req, filename):
    path = os.path.join("ans", filename)
    if os.path.isfile(path):
        return Response(Status.SUCCESS, "text/x-ansi", b"".join(render(path, quick=True)))
    return Response(Status.NOT_FOUND, "Not found")

if __name__ == "__main__":
    server = GeminiServer(app, port=2020)
    server.run()
