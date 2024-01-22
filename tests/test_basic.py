from agcp.model_svc import *
from agcp.parser import ConfigParser
from pprint import pprint
import unittest


class BasicTestSuite(unittest.TestCase):
    """Basic test cases."""

    def testing(self):
        cp = ConfigParser('data/')
        containers, policies, services = cp.parse() 

        svc_map = ServiceReachability.build_svc(containers, services)

        map = NP_object.build_sgs(containers, policies, InterNode=False)
        fg_map= NP_object.concate(map)
        pprint(fg_map, sort_dicts=False)
        print("=====================================================================================")
        pprint (svc_map.all_map)
        print("=====================================================================================")

        ServiceReachability.svc_add_rules(svc_map.all_map)
        print(services)





if __name__ == '__main__':
    unittest.main()
