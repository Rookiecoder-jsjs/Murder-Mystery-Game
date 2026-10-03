"""Map shared engine failures at the HTTP boundary, including test routers."""
from fastapi import HTTPException, Request
from fastapi.routing import APIRoute
from app.core.errors import GameError


class GameRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def mapped(request: Request):
            try:
                return await handler(request)
            except GameError as error:
                raise HTTPException(error.status_code, error.detail) from error

        return mapped
