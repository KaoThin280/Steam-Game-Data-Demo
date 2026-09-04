from app.db.session import _normalize_db_url


def test_raw_at_sign_in_password_is_encoded_once():
    result = _normalize_db_url(
        "postgresql://steam_readonly:alpha@beta@db.example.com:5432/postgres"
    )
    assert result == (
        "postgresql+asyncpg://steam_readonly:alpha%40beta@"
        "db.example.com:5432/postgres"
    )


def test_pre_encoded_password_is_not_double_encoded():
    result = _normalize_db_url(
        "postgresql://steam_readonly:alpha%40beta@db.example.com:5432/postgres"
    )
    assert "alpha%40beta" in result
    assert "%2540" not in result
