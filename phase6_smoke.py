"""Smoke-test the actual cloud view with a persisted journal, no external API."""
import sys,json
from pathlib import Path
from unittest.mock import patch
import requests
from streamlit.testing.v1 import AppTest
from phase6_journal import Journal

def check(path):
    doc=Journal(path).read();assert len([r for r in doc['events'] if r['kind']=='prediction'])==1
    assert len([r for r in doc['events'] if r['kind']=='result'])==1
    code='import phase6_ui\nphase6_ui.render_document('+repr(doc)+',"fixture-read")'
    with patch.object(requests,'get',side_effect=AssertionError('Rendering must not fetch providers')):
        at=AppTest.from_string(code).run(timeout=30)
        assert not at.exception,list(at.exception)
        assert any('TEST FIXTURES ONLY' in w.value for w in at.warning)
        assert at.dataframe
    print('Persisted fixture model, immutable forecast/result and mobile dashboard smoke passed.')
if __name__=='__main__':check(Path(sys.argv[1]))
