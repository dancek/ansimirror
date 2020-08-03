# Copyright 2020 Hannu Hartikainen
# Licensed under GNU AGPL, v3 or later
#
# NOTE: Get art files with `rsync -a rsync://16colo.rs/pack pack`

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

def render(filename, quick=False):
    with open(filename, "rb") as file:
        col = 0
        linebuf = b""
        ansiseq = ""
        nextline_ts = time()
        line_interval = (80 * (1 + 8 + 1)) / 9600
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
                linebuf += ansiseq
                continue

            col += 1

            if quick:
                sleeptime = 0
            else:
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

FRONT_CONTENT = """# Welcome to the ANSI art archive

This site mirrors ANSI art from https://16colo.rs. Modem-like download speed is emulated, and some magic is done to render mostly correctly in modern wide unicode terminals. The originals tend to be CP437, 80 columns.

For best experience, please use a streaming-capable client. If not, add /quick/ in front of urls to skip the modem download emulation.

## Picks from the curator

=> /us-birth-of-mawu-liza.ans the birth of mawu-liza / alpha king & h7 / blocktronics 2019
=> /ungenannt-darkness.ans darkness / ungenannt / blocktronics 2019
=> /us-plague-doctor.ans plague doctor / whazzit ober alpha king tainted x avenging angel / blocktronics 2020
=> /ungenannt_1453.ans 1453 / ungenannt / blocktronics 2016
=> /LU-TL_DR.ans TL;DR / luciano ayres / blocktronics 2015
=> /LU-GLITCH.ans Glitch (8-bit) / luciano ayres / blocktronics 2015
=> /ungenannt_motherofsorrows.ans mother of sorrows / ungenannt / blocktronics 2014
=> /bym-motherf4.ans motherf4 / bym / blocktronics 2014
=> /2m-history.ans history / mattmatthew / blocktronics 2013

## List of all (50K+) pieces

=> list/
Recommendation: browse https://16colo.rs/, then use direct links when you know the filename...

## About this site

=> source/ Source code (AGPLv3)
=> gemini://hannuhartikainen.fi/ Copyright 2020 by Hannu Hartikainen
"""


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
        return render(path)
    return None

@route("/quick/(?P<filename>[^/]*)", "text/x-ansi")
def quick(filename):
    if filename in filename_to_path:
        path = filename_to_path[filename]
        return render(path, quick=True)
    return None

@route("/list", "text/gemini")
def file_list():
    def link_generator():
        yield f"# {len(filename_to_path)} works of art\r\n\r\n"
        for filename, path in sorted(filename_to_path.items(), key=lambda kv: kv[1]):
            yield f"=> /{filename} {path[5:]}\r\n"

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
