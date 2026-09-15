from app.services.conversation import ConversationAnalysisService, SIGNAL_FIELDS


service = ConversationAnalysisService()


def _full_reasons():
    # A complete GPT-OSS response for the classic "initiated transfer" attack.
    return (
        '{"urgency": 0.85, "authority_impersonation": 0.0, "financial_request": 0.7, '
        '"credential_request": 0.0, "otp_request": 0.0, "threat": 0.1, '
        '"secrecy": 0.8, "persuasion": 0.75, "repeated_confirmation": 0.9, '
        '"confidence": 0.8, "reasons": ["time sensitive", "trust me", "confirm the transfer", "don\'t discuss this"]}'
    )


def test_parse_valid_json():
    content = '{"urgency": 0.8, "authority_impersonation": 0.9, "financial_request": 0.4, "credential_request": 0.1, "otp_request": 0.0, "threat": 0.7, "secrecy": 0.6, "persuasion": 0.5, "repeated_confirmation": 0.0, "confidence": 0.85, "reasons": ["bank impersonation", "urgent"]}'
    result = service._parse_response(content)
    assert result["urgency"] == 0.8
    assert result["authority_impersonation"] == 0.9
    assert result["secrecy"] == 0.6
    assert result["persuasion"] == 0.5
    assert result["repeated_confirmation"] == 0.0
    assert result["reasons"] == ["bank impersonation", "urgent"]


def test_parse_markdown_codefence():
    content = '```json\n{"urgency": 0.5, "authority_impersonation": 0.1, "financial_request": 0.0, "credential_request": 0.0, "otp_request": 0.0, "threat": 0.0, "secrecy": 0.0, "persuasion": 0.0, "repeated_confirmation": 0.0, "confidence": 0.4, "reasons": []}\n```'
    result = service._parse_response(content)
    assert result["urgency"] == 0.5
    assert result["confidence"] == 0.4


def test_parse_malformed_json_returns_empty():
    content = "this is not json at all {{{{"
    result = service._parse_response(content)
    assert result == {}


def test_parse_non_dict_json_returns_empty():
    result = service._parse_response("[1, 2, 3]")
    assert result == {}


def test_parse_clamps_out_of_range_values():
    content = '{"urgency": 5.0, "authority_impersonation": -1.2, "financial_request": 0.5, "credential_request": 0.0, "otp_request": 0.0, "threat": 0.0, "secrecy": 0.0, "persuasion": 0.0, "repeated_confirmation": 0.0, "confidence": 99.0, "reasons": []}'
    result = service._parse_response(content)
    assert result["urgency"] == 1.0
    assert result["authority_impersonation"] == 0.0
    assert result["confidence"] == 1.0


def test_parse_missing_fields_are_not_forced_to_zero():
    # THE critical regression: an analysis that omits a signal must NOT report
    # that signal as 0.0 — 0.0 would erase established evidence downstream.
    content = '{"urgency": 0.3}'
    result = service._parse_response(content)
    assert result == {"urgency": 0.3}
    assert "financial_request" not in result
    assert "secrecy" not in result
    assert "reasons" not in result


def test_parse_invalid_field_is_dropped_not_zeroed():
    content = '{"urgency": "not-a-number", "persuasion": 0.9}'
    result = service._parse_response(content)
    assert result == {"persuasion": 0.9}


def test_parse_bool_scores():
    content = '{"urgency": true, "threat": false}'
    result = service._parse_response(content)
    assert result["urgency"] == 1.0
    assert result["threat"] == 0.0


def test_parse_non_string_reasons():
    content = '{"urgency": 0.1, "authority_impersonation": 0.0, "financial_request": 0.0, "credential_request": 0.0, "otp_request": 0.0, "threat": 0.0, "secrecy": 0.0, "persuasion": 0.0, "repeated_confirmation": 0.0, "confidence": 0.0, "reasons": [123, null, 4.5, "ok"]}'
    result = service._parse_response(content)
    assert all(isinstance(r, str) for r in result["reasons"])
    assert result["reasons"] == ["ok"]


def test_signal_fields_cover_all_engine_channels():
    assert set(SIGNAL_FIELDS) == {
        "urgency", "authority_impersonation", "financial_request",
        "credential_request", "otp_request", "threat",
        "secrecy", "persuasion", "repeated_confirmation",
    }