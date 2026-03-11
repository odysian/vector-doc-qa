from unittest.mock import patch


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
