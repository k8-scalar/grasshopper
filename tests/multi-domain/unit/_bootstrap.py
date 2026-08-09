"""
Shared setup for the verify_*.py scripts in this directory - not a test
itself. Computes grasshopper-pod/code's path relative to this file (so these
scripts work from any checkout, no path editing needed) and stubs out the
OpenStack SDK packages (keystoneauth1/neutronclient/novaclient/dotenv) so the
real, unmodified grasshopper-pod/code modules can be imported and exercised
directly, with only the actual Neutron/Nova network calls mocked. No live
OpenStack project or Kubernetes cluster is needed to run any of these.
"""
import sys
import os
import types
import unittest.mock as mock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CODE_DIR = os.path.join(REPO_ROOT, "grasshopper-pod", "code")
sys.path.insert(0, CODE_DIR)

# On Windows, stdout's default encoding (cp1252) can't encode emoji some of
# the real modules print (e.g. main_operator.py's startup banner) - reconfigure
# rather than let an unrelated UnicodeEncodeError crash a verify_*.py script.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def _stub_module(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def _install_stubs():
    _stub_module("dotenv", load_dotenv=lambda *a, **kw: None)
    _stub_module("keystoneauth1")
    _stub_module("keystoneauth1.identity", v3=mock.MagicMock())
    _stub_module("keystoneauth1.session", Session=mock.MagicMock())
    sys.modules["keystoneauth1"].session = sys.modules["keystoneauth1.session"]
    sys.modules["keystoneauth1"].identity = sys.modules["keystoneauth1.identity"]
    _stub_module("neutronclient")
    _stub_module("neutronclient.v2_0", client=mock.MagicMock(
        Client=mock.MagicMock(side_effect=lambda *a, **kw: mock.MagicMock())
    ))
    sys.modules["neutronclient"].v2_0 = sys.modules["neutronclient.v2_0"]
    _stub_module("novaclient", client=mock.MagicMock(
        Client=mock.MagicMock(side_effect=lambda *a, **kw: mock.MagicMock())
    ))


_install_stubs()

FAILURES = []


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        FAILURES.append(label)


def report_and_exit():
    print("\n" + "=" * 60)
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
