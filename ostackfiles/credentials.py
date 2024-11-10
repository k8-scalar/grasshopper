#!/usr/bin/env python
from keystoneauth1.identity import v3
from keystoneauth1 import session
from neutronclient.v2_0 import client as neutclient
from novaclient import client as novaclient
import os

auth_url = os.environ.get("OS_AUTH_URL")
region_name = os.environ.get("OS_REGION_NAME")
cr_id = os.environ.get("OS_APPLICATION_CREDENTIAL_ID")
cr_secret = os.environ.get("OS_APPLICATION_CREDENTIAL_SECRET")
nova_api_version = "2.0"


auth = v3.ApplicationCredential(
    auth_url=auth_url,
    application_credential_id=cr_id,
    application_credential_secret=cr_secret,
)
mysession = session.Session(auth=auth)

neutron = neutclient.Client(session=mysession, region_name=region_name)
nova = novaclient.Client(nova_api_version, session=mysession, region_name=region_name)
