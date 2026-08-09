from dotenv import load_dotenv
from keystoneauth1.identity import v3
from keystoneauth1 import session
from neutronclient.v2_0 import client as neutclient
from novaclient import client as novaclient
import os
import json

DEFAULT_PROJECT_KEY = "default"


class OpenStackClient:
    """
    Per-project OpenStack (Neutron/Nova) client registry.

    Credentials come from OS_PROJECTS_JSON - a JSON list of per-project credential
    dicts, each shaped like {"key", "auth_url", "application_credential_id",
    "application_credential_secret", "neutron_endpoint", "nova_endpoint"}. If
    OS_PROJECTS_JSON is not set (or doesn't define a "default" entry), falls back
    to the legacy flat OS_* env vars as a single implicit "default" project, so
    existing single-project deployments need no migration.
    """

    _instances: dict[str, "OpenStackClient"] = {}
    _credentials_by_key: dict[str, dict] = None  # lazily parsed, cached

    def __new__(cls, project_key: str = DEFAULT_PROJECT_KEY):
        if project_key not in cls._instances:
            instance = super(OpenStackClient, cls).__new__(cls)
            instance._initialize(project_key)
            cls._instances[project_key] = instance
        return cls._instances[project_key]

    @classmethod
    def for_project(cls, project_key: str = DEFAULT_PROJECT_KEY) -> "OpenStackClient":
        return cls(project_key)

    @classmethod
    def known_project_keys(cls) -> list[str]:
        """All project keys with configured credentials: either every key
        defined in OS_PROJECTS_JSON, or - only when OS_PROJECTS_JSON is absent
        entirely - the single implicit "default" project built from the legacy
        flat OS_* env vars. Code that iterates "every configured project" (e.g.
        initialize_security_groups) relies on this never containing a
        credential-less phantom entry."""
        return list(cls._load_credentials().keys())

    @classmethod
    def _load_credentials(cls) -> dict[str, dict]:
        """Parses OS_PROJECTS_JSON once, caches the result keyed by project key."""
        if cls._credentials_by_key is not None:
            return cls._credentials_by_key

        load_dotenv()
        credentials_by_key = {}

        projects_json = os.environ.get("OS_PROJECTS_JSON")
        if projects_json:
            for entry in json.loads(projects_json):
                credentials_by_key[entry["key"]] = entry
        else:
            # No multi-project config at all: single implicit "default" project
            # from the legacy flat env vars - existing single-project
            # deployments need no changes.
            credentials_by_key[DEFAULT_PROJECT_KEY] = {
                "key": DEFAULT_PROJECT_KEY,
                "auth_url": os.environ.get("OS_AUTH_URL"),
                "application_credential_id": os.environ.get("OS_APPLICATION_CREDENTIAL_ID"),
                "application_credential_secret": os.environ.get("OS_APPLICATION_CREDENTIAL_SECRET"),
                "neutron_endpoint": os.environ.get("OS_NEUTRON_ENDPOINT"),
                "nova_endpoint": os.environ.get("OS_NOVA_ENDPOINT"),
            }

        cls._credentials_by_key = credentials_by_key
        return credentials_by_key

    def _initialize(self, project_key: str):
        print(f"Initializing Openstack Client for project '{project_key}'!")

        creds = OpenStackClient._load_credentials().get(project_key)
        if creds is None or not creds.get("auth_url"):
            raise Exception(
                f"No OpenStack credentials configured for project '{project_key}'. "
                f"Add an entry with \"key\": \"{project_key}\" to OS_PROJECTS_JSON."
            )

        nova_api_version = "2.0"

        # Authenticating with keystone. (Starting a session)
        auth = v3.ApplicationCredential(
            auth_url=creds.get("auth_url"),
            application_credential_id=creds.get("application_credential_id"),
            application_credential_secret=creds.get("application_credential_secret"),
        )
        mysession = session.Session(auth=auth)

        self.project_key = project_key

        # Starting session with neutron service.
        self.neutron = neutclient.Client(
            session=mysession,
            endpoint_override=creds.get("neutron_endpoint"),
        )

        # Starting session with nova service.
        self.nova = novaclient.Client(
            nova_api_version,
            session=mysession,
            endpoint_override=creds.get("nova_endpoint"),
        )

    def get_neutron(self) -> neutclient.Client:
        return self.neutron

    def get_nova(self) -> novaclient.Client:
        return self.nova
