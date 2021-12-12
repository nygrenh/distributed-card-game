from werkzeug.wrappers import Request


class middleware:
    """
    Middleware that does extra logging to make it more transparent what happens in the system
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        request = Request(environ)
        print(f"Starting processing request {request} from {request.remote_addr}")
        res = self.app(environ, start_response)
        print(f"Finished processing request {request} from {request.remote_addr}")
        return res
