from dotenv import load_dotenv
from keystoneauth1.identity import v3
from keystoneauth1 import session
from neutronclient.v2_0 import client as neutclient
from novaclient import client as novaclient
import os


class OpenStackClient:
    _instance = None
    neutron = None
    nova = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OpenStackClient, cls).__new__(cls)
            cls._initialize()
        return cls._instance

    @staticmethod
    def _initialize():
        print("Initializing Openstack Client!")

        # Getting environment variables.
        load_dotenv()
        auth_url = os.environ.get("OS_AUTH_URL")
        region_name = os.environ.get("OS_REGION_NAME")
        interface = os.environ.get("OS_INTERFACE", "public")  # default fallback
        cr_id = os.environ.get("OS_APPLICATION_CREDENTIAL_ID")
        cr_secret = os.environ.get("OS_APPLICATION_CREDENTIAL_SECRET")
        nova_api_version = "2.0"
        neutron_endpoint = os.environ.get("OS_NEUTRON_ENDPOINT")
        nova_endpoint = os.environ.get("OS_NOVA_ENDPOINT")

        # Authenticating with keystone. (Starting a session)
        auth = v3.ApplicationCredential(
            auth_url=auth_url,
            application_credential_id=cr_id,
            application_credential_secret=cr_secret,
        )
        mysession = session.Session(auth=auth)

        # Starting session with neutron service.
        OpenStackClient.neutron = neutclient.Client(
            session=mysession,
            endpoint_override=(neutron_endpoint)
        )

        # Starting session with nova service.
        OpenStackClient.nova = novaclient.Client(
            nova_api_version,
            session=mysession,
            endpoint_override=(nova_endpoint)
        )

        # OpenStackClient.neutron = neutclient.Client(
        #     session=mysession,
        #     region_name=region_name,
        #     interface=interface
        # )
        # OpenStackClient.nova = novaclient.Client(
        #     nova_api_version,
        #     session=mysession,
        #     region_name=region_name,
        #     interface=interface
        # )

    @staticmethod
    def get_neutron() -> neutclient.Client:
        return OpenStackClient().neutron

    @staticmethod
    def get_nova() -> novaclient.Client:
        return OpenStackClient().nova
