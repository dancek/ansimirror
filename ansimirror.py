# Copyright 2020 Hannu Hartikainen
# Licensed under GNU AGPL, v3 or later
#
# NOTE: Get art files with `rsync -a rsync://16colo.rs/pack pack`

FRONT_CONTENT = """gemini://ansi.hrtk.in/ – http://ansi.hrtk.in/

# Welcome to the ANSI art archive

This site mirrors ANSI art from https://16colo.rs. Modem-like download speed is emulated, and some magic is done to render mostly correctly in modern wide unicode terminals. The originals tend to be CP437, 80 columns.

The mirror is Gemini first, but a naive HTTP mirror is also available for the unenlightened. For best experience, please use a streaming-capable client. To bypass modem emulation, add /quick/ in front of the URL.

## Usage examples

```
gemget -o- gemini://ansi.hrtk.in/us-birth-of-mawu-liza.ans
amfora gemini://ansi.hrtk.in/quick/us-birth-of-mawu-liza.ans
curl http://ansi.hrtk.in/us-birth-of-mawu-liza.ans
```

## URL scheme

For any ANSI artwork in the 16colo.rs repository with the basename FILENAME.ANS the following URLs are available:

* /quick/FILENAME.ANS -- just output the file in a format suitable for modern terminals
* /FILENAME.ANS -- modem emulation with default settings (9600 bps, constant time per line)
* /b=14400/FILENAME.ANS -- modem emulation at 14400 bps, constant time per line
* /s=9600/FILENAME.ANS -- more realistic simulation of 9600 bps

The speed for b=<bitrate> and s=<bitrate> are configurable and must be positive integers. A perfect line and 8-N-1 is assumed for calculations.

### Simulation mode -- /s=<bitrate>/FILENAME.ANS

The simulation mode calculates transmission time per character. This practically means that empty lines are very fast and complicated ANSI sequences are slow. The current implementation still only sends full lines as TCP packets add considerable overhead (but I might use something like animation frames instead of lines later). I also have some ideas about line noise etc.

The simulation mode is not the default as I personally prefer the smoothness of constant time per line for just *viewing* ANSI art.

## Picks from the curator

=> /quick/us-birth-of-mawu-liza.ans the birth of mawu-liza / alpha king & h7 / blocktronics 2019
=> /quick/ungenannt-darkness.ans darkness / ungenannt / blocktronics 2019
=> /quick/us-plague-doctor.ans plague doctor / whazzit ober alpha king tainted x avenging angel / blocktronics 2020
=> /quick/ungenannt_1453.ans 1453 / ungenannt / blocktronics 2016
=> /quick/LU-TL_DR.ans TL;DR / luciano ayres / blocktronics 2015
=> /quick/LU-GLITCH.ans Glitch (8-bit) / luciano ayres / blocktronics 2015
=> /quick/ungenannt_motherofsorrows.ans mother of sorrows / ungenannt / blocktronics 2014
=> /quick/bym-motherf4.ans motherf4 / bym / blocktronics 2014
=> /quick/2m-history.ans history / mattmatthew / blocktronics 2013

## List of all (50K+) pieces

=> list/
Recommendation: browse https://16colo.rs/, then use direct links when you know the filename...

## About this site

=> source/ Source code (AGPLv3)
=> gemini://hannuhartikainen.fi/ Copyright 2020 by Hannu Hartikainen
"""

import os
import os.path
from time import time, sleep

from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.task import deferLater
from twisted.web.server import Site

from jetforce import GeminiServer, JetforceApplication, Response, Status

from http_application import HackyHttpApplication


filename_to_path = {}
for root, dirs, files in os.walk("pack"):
    for f in files:
        filename_to_path[f] = os.path.join(root, f)

def render_ansi(filename, speed=9600, simulation=False):
    """Render ANSI file with modem speed emulation

    Arguments:
    filename   -- Filename of the ANSI art file to display
    speed      -- The bitrate to emulate, or 0 to run as fast as possible.
                  Default: 9600
    simulation -- Consider non-printed characters (ie. ANSI sequences) for
                  bitrate computation. More realistic, but less smooth.
                  Default: False
    """
    with open(filename, "rb") as file:
        col = 0
        linebuf = b""
        ansiseq = ""
        nextline_ts = time()

        line_interval = 0
        char_interval = 0
        if speed > 0:
            if simulation:
                char_interval = (8 + 1) / speed
            else:
                line_interval = (80 * (8 + 1)) / speed
        while True:
            b = file.read(1)
            if len(b) == 0:
                # EOF
                return linebuf

            nextline_ts += char_interval

            if b[0] == 27:
                # skip ANSI sequences from line length calculation
                ansiseq = b
                while not b.isalpha():
                    b = file.read(1)
                    ansiseq += b
                if b == b'C': # move right; an optimization technique
                    move = int(ansiseq[2:-1] or 1)
                    col += move
                linebuf += ansiseq
                continue

            col += 1

            sleeptime = max(nextline_ts - time(), 0)

            linebuf += b.decode("cp437").encode("utf-8")

            if b == b'\r':
                yield deferLater(reactor, sleeptime, lambda: b'')
                col = 0
            if b == b'\n':
                yield deferLater(reactor, sleeptime, lambda: linebuf)
                nextline_ts += line_interval
                col = 0
                linebuf = b""
            if col >= 80:
                # Wrap to 80 cols
                yield deferLater(reactor, sleeptime, lambda: linebuf + b'\r\n')
                nextline_ts += line_interval
                col = 0
                linebuf = b""


gemini_app = JetforceApplication()
http_app = HackyHttpApplication()

def route(path, mimetype, http_path=None):
    """Route for both Gemini and HTTP"""
    def wrap(fn):
        @gemini_app.route(path)
        def gemini_route(req, *args, **kwargs):
            content = fn(*args, **kwargs)
            if content is None:
                return Response(Status.NOT_FOUND, "Not found")
            return Response(Status.SUCCESS, mimetype, content)

        @http_app.route(http_path or path)
        def http_route(req, *args, **kwargs):
            content = fn(*args, **kwargs)
            if content is None:
                req.setResponseCode(404)
                return "Not found"
            req.setHeader("Content-Type", mimetype)
            return content

        return fn

    return wrap


@route("", "text/gemini")
def front():
    return FRONT_CONTENT

@route("/(?P<filename>[^/]*)", "text/x-ansi")
def ansi(filename):
    if filename in filename_to_path:
        path = filename_to_path[filename]
        return render_ansi(path)
    return None

@route("/quick/(?P<filename>[^/]*)", "text/x-ansi")
def quick(filename):
    if filename in filename_to_path:
        path = filename_to_path[filename]
        return render_ansi(path, 0)
    return None

@route("/(?P<type>[bs])=(?P<bitrate>[0-9]*)/(?P<filename>[^/]*)", "text/x-ansi")
def ansi_with_options(filename, bitrate, type):
    if filename in filename_to_path:
        path = filename_to_path[filename]
        return render_ansi(path, int(bitrate), type == 's')
    return None

@route("/list", "text/gemini")
def file_list():
    def link_generator():
        yield f"""# {len(filename_to_path)} works of art

Note that I stopped linking to the pieces because a misbehaving bot was crawling all of them. Just use /<filename> for modem emulation or /quick/<filename> to download. If you ever write gemini crawlers, please respect robots.txt and crawl slowly!

"""
        for filename in sorted(filename_to_path.keys()):
            yield f"* {filename}\n"

    return link_generator()

@route("/source", "text/x-python")
def source():
    with open(__file__) as source_file:
        return source_file.read()

@route("/robots.txt", "text/plain")
def robots():
    return "User-agent: *\nDisallow: /\n"


if __name__ == "__main__":
    http_endpoint = TCP4ServerEndpoint(reactor=reactor, port=2080)
    http_endpoint.listen(http_app)

    gemini_server = GeminiServer(gemini_app, reactor=reactor, port=2020)
    gemini_server.run()
