import hashlib
from research.validate import artifact_errors


def test_manifest_check_detects_missing_and_tampered_output(tmp_path):
    path=tmp_path/'report.csv';path.write_bytes(b'original')
    manifest=dict(status='complete',artifacts={'report.csv':hashlib.sha256(b'original').hexdigest()})
    assert artifact_errors(tmp_path,manifest)==[]
    path.write_bytes(b'changed')
    assert artifact_errors(tmp_path,manifest)==['Artifact hash mismatch: report.csv']
    path.unlink()
    assert artifact_errors(tmp_path,manifest)==['Missing artifact: report.csv']


def test_empty_publication_is_not_a_pass(tmp_path):
    assert artifact_errors(tmp_path,{'status':'complete','artifacts':{}})
