import asyncio
from unittest.mock import patch

from app.config import settings
from app.main import app
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient
from starlette.responses import StreamingResponse


class TestRequestContextMiddleware:
    async def test_generates_request_id_header_when_missing(self, client) -> None:
        response = await client.get("/")

        assert response.status_code == 200
        assert response.headers["X-Request-ID"]

    async def test_propagates_request_id_and_logs_request_completion(
        self,
        client,
    ) -> None:
        request_id = "req-123"
        with patch("app.main.logger.info") as mock_info:
            response = await client.get("/", headers={"X-Request-ID": request_id})

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == request_id

        matching_calls = [
            call
            for call in mock_info.call_args_list
            if call.args and call.args[0] == "request.completed"
        ]
        assert len(matching_calls) == 1
        completion_extra = matching_calls[0].kwargs["extra"]
        assert completion_extra["event"] == "request.completed"
        assert completion_extra["request_id"] == request_id
        assert completion_extra["status_code"] == 200
        assert isinstance(completion_extra["duration_ms"], int)

    async def test_propagates_request_id_for_unhandled_500_response(self, client) -> None:
        router = APIRouter()
        route_path = "/__request-id-unhandled-error"

        @router.get(route_path)
        async def _raise_unhandled_error() -> None:
            raise RuntimeError("boom")

        app.include_router(router)
        try:
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as asgi_client:
                response = await asgi_client.get(
                    route_path,
                    headers={"X-Request-ID": "req-500"},
                )
        finally:
            app.router.routes = [
                route
                for route in app.router.routes
                if getattr(route, "path", None) != route_path
            ]

        assert response.status_code == 500
        assert response.headers["X-Request-ID"] == "req-500"

    async def test_logs_exception_for_unhandled_500_response(self) -> None:
        router = APIRouter()
        route_path = "/__request-id-unhandled-error-log"

        @router.get(route_path)
        async def _raise_unhandled_error() -> None:
            raise RuntimeError("boom")

        app.include_router(router)
        try:
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            with patch("app.main.logger.exception") as mock_exception:
                async with AsyncClient(
                    transport=transport,
                    base_url="http://test",
                ) as asgi_client:
                    response = await asgi_client.get(
                        route_path,
                        headers={"X-Request-ID": "req-500-log"},
                    )
        finally:
            app.router.routes = [
                route
                for route in app.router.routes
                if getattr(route, "path", None) != route_path
            ]

        assert response.status_code == 500
        matching_calls = [
            call
            for call in mock_exception.call_args_list
            if call.args and call.args[0] == "request.unhandled_exception"
        ]
        assert len(matching_calls) == 1
        exception_call = matching_calls[0]
        assert exception_call.kwargs["extra"]["request_id"] == "req-500-log"
        assert exception_call.kwargs["extra"]["path"] == route_path
        assert isinstance(exception_call.kwargs["exc_info"], RuntimeError)

    async def test_streaming_completion_duration_includes_stream_body_time(self) -> None:
        router = APIRouter()
        route_path = "/__request-id-streaming-completion"

        async def _stream_payload():
            yield b"first\n"
            await asyncio.sleep(0.05)
            yield b"second\n"

        @router.get(route_path)
        async def _stream_response() -> StreamingResponse:
            return StreamingResponse(_stream_payload(), media_type="text/plain")

        app.include_router(router)
        try:
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            with patch("app.main.logger.info") as mock_info:
                async with AsyncClient(
                    transport=transport,
                    base_url="http://test",
                ) as asgi_client:
                    response = await asgi_client.get(
                        route_path,
                        headers={"X-Request-ID": "req-stream"},
                    )

            assert response.status_code == 200
            assert response.text == "first\nsecond\n"
            matching_calls = [
                call
                for call in mock_info.call_args_list
                if call.args and call.args[0] == "request.completed"
            ]
            assert len(matching_calls) == 1
            completion_extra = matching_calls[0].kwargs["extra"]
            assert completion_extra["request_id"] == "req-stream"
            assert completion_extra["status_code"] == 200
            assert completion_extra["duration_ms"] >= 40
        finally:
            app.router.routes = [
                route
                for route in app.router.routes
                if getattr(route, "path", None) != route_path
            ]

    async def test_cors_preflight_allows_x_request_id_header(self, client) -> None:
        response = await client.options(
            "/",
            headers={
                "Origin": settings.frontend_url,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Request-ID",
            },
        )

        assert response.status_code == 200
        allow_headers = response.headers["access-control-allow-headers"]
        assert "x-request-id" in allow_headers.lower()

    async def test_cors_exposes_x_request_id_header_for_browser_clients(self, client) -> None:
        response = await client.get(
            "/",
            headers={
                "Origin": settings.frontend_url,
                "X-Request-ID": "browser-correlation-id",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == settings.frontend_url
        exposed_headers = response.headers["access-control-expose-headers"]
        assert "x-request-id" in exposed_headers.lower()
