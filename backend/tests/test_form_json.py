from app.models.cad import CadAnalyzeOptions
from app.utils.form_json import parse_optional_json_form


def test_swagger_string_placeholder_ignored():
    opts = parse_optional_json_form("string", CadAnalyzeOptions, field_name="options_json")
    assert opts.work_plane.value == "auto"
