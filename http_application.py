# A hacky implementation of HTTP in addition to Gemini

import re

from jetforce import RoutePattern
from twisted.internet.defer import Deferred, ensureDeferred
from twisted.web.resource import Resource
from twisted.web.server import Site, NOT_DONE_YET

class HackyHttpApplication(Site):
    def __init__(self):
        super().__init__(self, None)
        self.routes = []

    def getResourceFor(self, *_):
        return self

    def route(self, path):
        """Register route (decorator)"""
        def wrap(fn):
            self.routes.append((path, fn))
            return fn
        return wrap

    def render(self, request):
        ensureDeferred(self._render_content(request))
        return NOT_DONE_YET

    async def _render_content(self, request):
        for data in self._generate_content(request):
            if isinstance(data, Deferred):
                data = await data
            if isinstance(data, str):
                data = data.encode('utf-8')
            request.write(data)
        request.finish()

    def _generate_content(self, request):
        for path, callback in self.routes[::-1]:
            match = re.fullmatch(path, request.path.decode("utf-8").rstrip("/"))
            if match:
                callback_kwargs = match.groupdict()
                break
        else:
            callback = self._default_callback
            callback_kwargs = {}

        response = callback(request, **callback_kwargs)

        if isinstance(response, (bytes, str, Deferred)):
            yield response
        elif response:
            yield from response

    def _default_callback(self, request, **_):
        request.setResponseCode(404)
        return "Not found"
