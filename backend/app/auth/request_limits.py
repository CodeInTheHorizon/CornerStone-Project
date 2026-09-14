"""Limit actual inbound bytes before JSON/multipart parsing, including chunked bodies."""
from starlette.responses import JSONResponse
from app.config import settings
from app.auth.rate_limits import check_limit

class RequestLimitsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"].rstrip("/")
        prefix = settings.API_PREFIX.rstrip("/")
        if scope["method"] == "POST" and path in {prefix + "/auth/login", prefix + "/auth/register"}:
            category = path.rsplit("/", 1)[1]
            identity = (scope.get("client") or ("unknown", 0))[0]
            retry = check_limit(category, identity)
            if retry:
                return await JSONResponse({"detail": "Too many requests. Please retry later."}, 429,
                                          headers={"Retry-After": str(retry)})(scope, receive, send)
        limit = settings.IMPORT_REQUEST_MAX_BYTES if path == prefix + "/data/import" else settings.REQUEST_MAX_BYTES
        async def reject():
            await JSONResponse({"detail": f"Request body exceeds the {limit}-byte limit."}, 413)(scope, receive, send)
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    if int(value) > limit:
                        return await reject()
                except ValueError:
                    return await JSONResponse({"detail": "Invalid Content-Length."}, 400)(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > limit:
                return await reject()
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False
        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}
        await self.app(scope, replay, send)
