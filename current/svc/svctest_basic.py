from svc.start_svc import *
from svc.svcparser import ConfigParser
from pprint import pprint

import unittest


class BasicTestSuite(unittest.TestCase):

    def test_reachability_matrix(self):

        cp = ConfigParser('data/')
        containers, policies, services = cp.parse() 

        matrix = ServiceReachability.build_svc_matrix(containers, services)#, build_transpose_matrix=True)
        print("=====================================================================================")
        pprint (vars(matrix), sort_dicts=False)
        print("=====================================================================================")
        pprint (containers)
        print("=====================================================================================")
        pprint(services)
        

if __name__ == '__main__':
    unittest.main()