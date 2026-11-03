from app.api.router import build_api_router
from app.api.v1 import admin, agent_rpc, auth, dashboard, games


def signature(routes):
    return [(route.path, frozenset(route.methods), route.endpoint) for route in routes]


def test_composition_preserves_feature_paths_methods_and_handlers():
    expected = [route for feature in (auth, games, dashboard, agent_rpc, admin)
                for route in feature.router.routes]
    assert signature(build_api_router().routes) == signature(expected)


def test_legacy_routes_remain_explicit_opt_in():
    from app.api.v1 import ai_agent, chat, data_files

    current = build_api_router().routes
    legacy = [route for feature in (ai_agent, chat, data_files)
              for route in feature.router.routes]
    assert signature(build_api_router(enable_legacy_ai=True).routes) == signature(current + legacy)
