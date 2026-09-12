import hashlib
import json
import sys
import types
from typing import ClassVar

import pytest

from iip.harvest import patria


class Nodes:
    def __init__(self, items):
        self.items = items

    def count(self):
        return len(self.items)

    def nth(self, index):
        return self.items[index]

    def all_text_contents(self):
        return [item.text for item in self.items]

    def evaluate_all(self, _script):
        return [item.value for item in self.items]


class Option:
    def __init__(self, text, value=None):
        self.text = text
        self.value = value if value is not None else text

    def inner_text(self):
        return self.text

    def get_attribute(self, name):
        return self.value if name == "value" else None


class YearSelect:
    def __init__(self, options, fail_select=False):
        self.options = Nodes(options)
        self.selected = []
        self.fail_select = fail_select
        self.evaluated = []

    def locator(self, query):
        assert query == "option"
        return self.options

    def select_option(self, value):
        if self.fail_select:
            raise RuntimeError("native selection unavailable")
        self.selected.append(value)

    def evaluate(self, script, value):
        self.evaluated.append((script, value))


class SelectPage:
    def __init__(self, selects):
        self.selects = Nodes(selects)

    def locator(self, query):
        assert query == "select"
        return self.selects


def test_find_year_select_uses_candidate_with_most_years():
    short = YearSelect([Option("2024")])
    long = YearSelect([Option("Selecione", ""), Option("2023"), Option("2024")])

    assert patria._find_year_select(SelectPage([short, long])) is long


def test_find_year_select_returns_none_when_options_are_not_years():
    assert patria._find_year_select(SelectPage([YearSelect([Option("Todos")])])) is None


class VisibleItem:
    def __init__(self, visible):
        self.visible = visible

    def is_visible(self, timeout):
        assert timeout == 500
        if isinstance(self.visible, Exception):
            raise self.visible
        return self.visible


class VisiblePage:
    def __init__(self, items):
        self.items = Nodes(items)

    def get_by_text(self, text, exact):
        assert text == "2024" and exact is True
        return self.items


def test_visible_year_controls_filters_hidden_and_broken_items():
    visible = VisibleItem(True)
    page = VisiblePage(
        [visible, VisibleItem(False), VisibleItem(RuntimeError("stale"))]
    )

    assert patria._visible_year_controls(page, 2024) == [visible]


class Link:
    def __init__(self, attrs, text="", headings=()):
        self.attrs = attrs
        self.text = text
        self.headings = headings

    def get_attribute(self, name):
        return self.attrs.get(name)

    def inner_text(self):
        return self.text

    def locator(self, query):
        if query.startswith("xpath="):
            return CategoryNode(self.headings)
        return Nodes([])


class CategoryNode:
    def __init__(self, headings):
        self.headings = headings

    def locator(self, tag):
        return HeadingLocator(
            self.headings[0] if self.headings and tag == "h2" else None
        )


class HeadingLocator:
    def __init__(self, text):
        self.text = text

    @property
    def first(self):
        return self

    def count(self):
        return int(self.text is not None)

    def inner_text(self):
        return self.text


class LinksPage:
    url = "https://example.test/documentos/"

    def __init__(self, links):
        self.links = Nodes(links)

    def wait_for_timeout(self, timeout):
        assert timeout == 500

    def locator(self, query):
        if query == "a[href], [data-href], [data-url], [data-link], [onclick]":
            return self.links
        return Nodes([])


def test_collect_links_accepts_files_and_mziq_urls_and_deduplicates():
    page = LinksPage(
        [
            Link({"href": "relatorio.pdf"}, " Relatório ", ("Relatórios",)),
            Link(
                {"data-url": "https://api.mziq.com/mzfilemanager/uuid"}, "", ("Fatos",)
            ),
            Link({"href": "relatorio.pdf"}, "duplicado"),
            Link({"onclick": "window.open('https://example.test/ata.docx')"}, "Ata"),
            Link({"href": "https://example.test/pagina"}, "ignorar"),
        ]
    )

    docs = patria._collect_links(page, "TEST3", 2024)

    assert [(doc.title, doc.category) for doc in docs] == [
        ("Relatório", "Relatórios"),
        ("uuid", "Fatos"),
        ("Ata", "Outros"),
    ]


def test_capture_document_meta_payload_filters_non_mziq_and_reads_text_json():
    class Response:
        url = "https://api.mziq.com/filter/categories/year/meta"
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

        def json(self):
            raise ValueError("json unavailable")

        def text(self):
            return json.dumps(
                {"data": {"document_metas": [{"file_url": "https://x/a.pdf"}]}}
            )

    assert patria._capture_document_meta_payload(Response(), "TEST3") == [
        {"file_url": "https://x/a.pdf"}
    ]


def test_capture_document_meta_payload_ignores_irrelevant_response():
    class Response:
        url = "https://example.test/page"
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

    assert patria._capture_document_meta_payload(Response(), "TEST3") == []


def test_capture_document_meta_payload_ignores_non_json_mziq_response():
    class Response:
        url = "https://api.mziq.com/file"
        headers: ClassVar[dict[str, str]] = {"content-type": "application/pdf"}

    assert patria._capture_document_meta_payload(Response(), "TEST3") == []


class NetworkResponse:
    def __init__(self, url, payload):
        self.url = url
        self._payload = payload

    def text(self):
        return self._payload


class SelectFlowPage(SelectPage):
    url = "https://example.test/documentos/"

    def __init__(self, select, response=None):
        super().__init__([select])
        self.callbacks = {}
        self.response = response

    def on(self, event, callback):
        self.callbacks[event] = callback

    def wait_for_timeout(self, timeout):
        assert timeout == 5000
        if self.response:
            self.callbacks["response"](self.response)

    def content(self):
        return "<html></html>"

    def locator(self, query):
        if query == "select":
            return self.selects
        if query == "body":
            return type("Body", (), {"inner_text": lambda self: "body"})()
        return Nodes([])


def test_select_year_selects_matching_option_and_captures_api(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    select = YearSelect([Option("2023"), Option("2024", "year-2024")])
    response = NetworkResponse(
        "https://api.mziq.com/filter/categories/year/meta", '{"data": []}'
    )

    assert patria._select_year(SelectFlowPage(select, response), 2024) is True
    assert select.selected == ["year-2024"]
    assert list((tmp_path / "data" / "patria" / "debug").glob("2024_*.html"))


def test_select_year_uses_dom_event_fallback_when_native_selection_fails(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    select = YearSelect([Option("2024")], fail_select=True)

    assert patria._select_year(SelectFlowPage(select), 2024) is True
    assert select.evaluated[0][1] == "2024"


def test_select_year_returns_false_when_no_select_or_no_matching_year():
    assert patria._select_year(SelectPage([]), 2024) is False
    assert (
        patria._select_year(SelectFlowPage(YearSelect([Option("2023")])), 2024) is False
    )


class DownloadResponse:
    ok = True
    headers: ClassVar[dict[str, str]] = {"content-type": "application/pdf"}

    def body(self):
        return b"pdf-content"


class RequestApi:
    def __init__(self):
        self.get_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return DownloadResponse()


class HarvestPage:
    def __init__(self, initial_response):
        self.context = types.SimpleNamespace(request=RequestApi())
        self.initial_response = initial_response
        self.callbacks = {}
        self.url = "https://example.test/documentos/"

    def on(self, event, callback):
        self.callbacks[event] = callback

    def goto(self, *_args, **_kwargs):
        self.callbacks["response"](self.initial_response)

    def wait_for_load_state(self, *_args, **_kwargs):
        pass

    def wait_for_timeout(self, *_args, **_kwargs):
        pass


class InitialResponse:
    url = "https://api.mziq.com/filter/categories/year/meta"
    headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

    def json(self):
        return {
            "data": {
                "document_metas": [
                    {
                        "file_year": 2024,
                        "file_url": "https://api.mziq.com/mzfilemanager/document-uuid",
                        "file_name_original": "Relatório anual",
                        "category_name": "Relatórios",
                    }
                ]
            }
        }


def install_fake_playwright(monkeypatch, page):
    class Browser:
        def new_page(self, **_kwargs):
            return page

        def close(self):
            pass

    class Manager:
        def __enter__(self):
            return types.SimpleNamespace(
                chromium=types.SimpleNamespace(launch=lambda **_kwargs: Browser())
            )

        def __exit__(self, *_args):
            pass

    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: Manager()
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)


def test_harvest_uses_initial_api_meta_downloads_file_and_writes_manifest(
    monkeypatch, tmp_path
):
    page = HarvestPage(InitialResponse())
    install_fake_playwright(monkeypatch, page)

    docs = patria.harvest("test3", range(2024, 2025), tmp_path)

    assert len(docs) == 1
    assert docs[0].ticker == "TEST3"
    assert docs[0].sha256 == hashlib.sha256(b"pdf-content").hexdigest()
    saved = tmp_path / "TEST3" / "2024" / "Relatório anual.pdf"
    assert saved.read_bytes() == b"pdf-content"
    assert "sha256" in (tmp_path / "TEST3" / "manifest.csv").read_text(
        encoding="utf-8-sig"
    )


def test_hash_file_and_progress_pulse_run_once(monkeypatch, tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"hash me")
    assert patria._hash_file(source) == hashlib.sha256(b"hash me").hexdigest()

    class StopAfterOneWait:
        def __init__(self):
            self.calls = 0

        def wait(self, _interval):
            self.calls += 1
            return self.calls > 1

    pulse = patria._ProgressPulse("test", interval=0)
    pulse._stop = StopAfterOneWait()
    monkeypatch.setattr(patria, "print", lambda *_args, **_kwargs: None, raising=False)
    pulse._run()
    assert pulse._stop.calls == 2


def test_documents_from_meta_keeps_items_with_an_unparseable_year():
    docs = patria._documents_from_mziq_meta(
        [{"file_year": "desconhecido", "file_url": "https://example.test/a.pdf"}],
        "TEST3",
        2024,
    )
    assert [doc.url for doc in docs] == ["https://example.test/a.pdf"]


class FailedDownloadResponse:
    ok = False
    headers: ClassVar[dict[str, str]] = {}

    def body(self):
        return b""


class FailedRequestApi(RequestApi):
    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return FailedDownloadResponse()


def test_harvest_registers_url_when_download_and_click_fallback_fail(
    monkeypatch, tmp_path
):
    page = HarvestPage(InitialResponse())
    page.context.request = FailedRequestApi()
    install_fake_playwright(monkeypatch, page)
    monkeypatch.setattr(
        patria,
        "_documents_from_mziq_meta",
        lambda *_args: [
            patria.Document(
                "TEST3", 2024, "Outros", "sem download", "https://example.test/file.pdf"
            )
        ],
    )
    monkeypatch.setattr(patria, "_api_documents_for_year", lambda *_args: [])
    monkeypatch.setattr(patria, "_select_year", lambda *_args: False)
    monkeypatch.setattr(patria, "_collect_links", lambda *_args: [])
    page.locator = lambda _query: Nodes([])

    docs = patria.harvest("test3", range(2024, 2025), tmp_path)

    assert len(docs) == 1
    assert docs[0].sha256 is None
    assert "https://example.test/file.pdf" in (
        tmp_path / "TEST3" / "manifest.csv"
    ).read_text(encoding="utf-8-sig")


def test_parse_years_and_main_delegate_to_harvest(monkeypatch, tmp_path, capsys):
    assert list(patria._parse_years("2022-2024")) == [2022, 2023, 2024]
    assert list(patria._parse_years("2024")) == [2024]
    received = {}

    def fake_harvest(**kwargs):
        received.update(kwargs)
        return [patria.Document("TEST3", 2024, "Outros", "ok", "https://x", "a" * 64)]

    monkeypatch.setattr(patria, "harvest", fake_harvest)
    assert (
        patria.main(
            [
                "--ticker",
                "test3",
                "--years",
                "2024",
                "--output",
                str(tmp_path),
                "--headed",
            ]
        )
        == 0
    )
    assert received["ticker"] == "test3"
    assert received["headed"] is True
    assert "Downloads concluídos: 1" in capsys.readouterr().out


def test_harvest_raises_helpful_error_when_playwright_is_unavailable(
    monkeypatch, tmp_path
):
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.delitem(sys.modules, "playwright.sync_api", raising=False)

    with pytest.raises(RuntimeError, match="Playwright não está instalado"):
        patria.harvest("TEST3", range(2024, 2025), tmp_path)


class ApiFetchResponse:
    status = 200
    ok = True

    def json(self):
        return {
            "data": {
                "document_metas": [
                    {
                        "file_year": 2024,
                        "file_url": "https://api.mziq.com/mzfilemanager/from-template",
                        "file_name_original": "Por template",
                    }
                ]
            }
        }


class TemplateRequestApi(RequestApi):
    def __init__(self):
        super().__init__()
        self.fetch_calls = []

    def fetch(self, url, **kwargs):
        self.fetch_calls.append((url, kwargs))
        return ApiFetchResponse()


class EmptyInitialResponse:
    url = "https://api.mziq.com/initial"
    headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

    def json(self):
        return {"data": {}}


class TemplateHarvestPage(HarvestPage):
    def __init__(self):
        super().__init__(EmptyInitialResponse())
        self.context.request = TemplateRequestApi()

    def goto(self, *_args, **_kwargs):
        request = types.SimpleNamespace(
            url="https://api.mziq.com/filter/categories/year/meta",
            method="POST",
            post_data='{"year":2023}',
            headers={"content-type": "application/json"},
        )
        self.callbacks["request"](request)
        self.callbacks["response"](self.initial_response)


def test_harvest_uses_captured_request_template_when_initial_meta_is_empty(
    monkeypatch, tmp_path
):
    page = TemplateHarvestPage()
    install_fake_playwright(monkeypatch, page)

    docs = patria.harvest("test3", range(2024, 2025), tmp_path)

    assert len(docs) == 1
    assert page.context.request.fetch_calls[0][1]["data"] == '{"year":2024}'
    assert docs[0].sha256 == hashlib.sha256(b"pdf-content").hexdigest()
