from .model_svc import *

def redundant_policy(added_policy, policies: List[Policy]):
    pol_red_with = []
    
    for statepol in policies:
        for allow_added_pol in added_policy.allow:
            for allow_state_pol in statepol.allow:
                if added_policy.direction == statepol.direction:
                    if (
                        added_policy.selector.labels.items() == statepol.selector.labels.items()
                        and allow_added_pol.labels.items() == allow_state_pol.labels.items() 
                        and statepol!=added_policy                       
                    ) or (
                        added_policy.selector.labels.items() == statepol.selector.labels.items()
                        and allow_added_pol.labels.items() > allow_state_pol.labels.items()
                    ) or (
                        added_policy.selector.labels.items() > statepol.selector.labels.items()
                        and allow_added_pol.labels.items() == allow_state_pol.labels.items()
                    ) or (
                        added_policy.selector.labels.items() > statepol.selector.labels.items()
                        and allow_added_pol.labels.items() > allow_state_pol.labels.items()
                    ):
                        if statepol.name not in pol_red_with:  
                            pol_red_with.append(statepol.name)
    return pol_red_with


def conflicting_policy(added_policy, policies: List[Policy]):
    pol_conf_with = []
    
    for statepol in policies:
        for allow_added_pol in added_policy.allow:
            for allow_state_pol in statepol.allow:
                if added_policy.direction == statepol.direction:
                    if (
                        added_policy.selector.labels.items() == statepol.selector.labels.items()
                        and allow_added_pol.labels.items() < allow_state_pol.labels.items()
                    ) or (
                        added_policy.selector.labels.items() < statepol.selector.labels.items()
                        and allow_added_pol.labels.items() == allow_state_pol.labels.items()
                    ) or (
                        added_policy.selector.labels.items() < statepol.selector.labels.items()
                        and allow_added_pol.labels.items() < allow_state_pol.labels.items()
                    ):
                        if statepol.name not in pol_conf_with:  
                            pol_conf_with.append(statepol.name)
    return pol_conf_with

def over_permissive(added_policy) -> bool:
    return not added_policy.selector.labels



