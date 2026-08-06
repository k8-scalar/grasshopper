"""
Verifies setup_gh()'s ordering: it (re-)attaches "default" to workers before
creating masterSG/workerSG, and it never detaches "default" itself - that's a
separate, later step (see openstackfiles/detach_defaultSG.py) that's only
safe once Grasshopper is deployed and has processed the relevant
NetworkPolicies. Confirmed live: detaching unconditionally right after
bootstrap (the old behavior) left a real ingress gap - see the Typha 5473
test in README_v2.md's Route Reflector section.

Run with: python verify_setup_gh_ordering.py
"""
import unittest.mock as mock

import _bootstrap
from _bootstrap import check, report_and_exit

calls = []

with mock.patch("openstackfiles.attach_defaultSG.attach_defaultSG", side_effect=lambda: calls.append("attach")), \
     mock.patch("openstackfiles.create_master_and_workerSG.create_master_and_workerSG", side_effect=lambda: calls.append("create")), \
     mock.patch("openstackfiles.detach_defaultSG.detach_defaultSG", side_effect=lambda: calls.append("detach")) as mock_detach:
    import setup_gh
    setup_gh.setup_gh()

check("attach_defaultSG ran before create_master_and_workerSG", calls == ["attach", "create"])
check("setup_gh() never calls detach_defaultSG - that's a separate later step", not mock_detach.called)

report_and_exit()
