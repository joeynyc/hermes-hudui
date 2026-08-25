"""Plugin hub endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.collectors.plugins import (
    collect_plugins,
    install_plugin,
    set_dashboard_plugin_hidden,
    set_plugin_enabled,
    update_plugin,
)

from .serialize import to_dict

router = APIRouter()


class PluginInstallRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=2048)


@router.get("/plugins")
def get_plugins():
    state = collect_plugins()
    result = to_dict(state)
    result["by_source"] = to_dict(state.by_source())
    return result


@router.post("/plugins/rescan")
def rescan_plugins():
    state = collect_plugins()
    return {"ok": True, "count": state.total_plugins}


@router.post("/plugins/install")
def install_plugin_endpoint(body: PluginInstallRequest):
    try:
        return install_plugin(body.identifier)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/plugins/{name}/enable")
def enable_plugin(name: str):
    try:
        return set_plugin_enabled(name, True)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/plugins/{name}/disable")
def disable_plugin(name: str):
    try:
        return set_plugin_enabled(name, False)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/plugins/{name}/show")
def show_plugin(name: str):
    try:
        return set_dashboard_plugin_hidden(name, False)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/plugins/{name}/hide")
def hide_plugin(name: str):
    try:
        return set_dashboard_plugin_hidden(name, True)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/plugins/{name}/update")
def update_plugin_endpoint(name: str):
    try:
        return update_plugin(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
